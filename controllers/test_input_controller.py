# file: tests/test_input_controller.py
"""
Pytest-набор для controllers/input_controller.py.
Покрывает:
 - базовый happy-path
 - разные единицы (MPa/kPa, mm_Hg, m3/h, m3/s, l/min, K→°C)
 - альтернативные пути
 - вложенный формат {value: {real, unit}}
 - отсутствующие поля/ошибки единиц (мягкая деградация parse, жёсткая в prepare)
 - лишние поля: type: sharp, methodic: otHER
"""

from __future__ import annotations

import os
import sys
from math import isclose
from typing import Dict, Any

import pytest

# Добавим корень проекта в sys.path для импорта контроллера
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from controllers.input_controller import InputController  # noqa: E402


# --------------------------- Хелперы ---------------------------

def base_input() -> Dict[str, Any]:
    return {
        "type": "sharp",  # лишнее поле
        "flowPackage": {
            "flowProperties": {
                "q_v": {"real": 50, "unit": "m3_h"},
            },
            "request": {"extraTypeOfCalc": "Direct", "typeOfCalc": "pTZ"},
        },
        "physPackage": {
            "physProperties": {
                "methodic": "otHER",  # произвольное поле/регистр
                "T": {"real": 15, "unit": "C"},
                "T_st": {"real": 20, "unit": "C"},
                "p_abs": {"real": 4, "unit": "MPa"},
                "p_atm": {"real": 760, "unit": "mm_Hg"},
                "p_st": {"real": 0.101325, "unit": "MPa"},
                "dp": {"real": 20, "unit": "kPa"},
            }
        },
        "lenPackage": {
            "lenProperties": {
                "d20": {"real": 100, "unit": "mm"},
                "D": {"real": 300, "unit": "mm"},
            }
        },
    }


def approx(a: float, b: float, rel: float = 1e-9, abs_tol: float = 0.0) -> None:
    assert isclose(a, b, rel_tol=rel, abs_tol=abs_tol), f"{a} != {b}"


# --------------------------- Тесты ---------------------------

def test_prepare_params_ok_baseline():
    data = base_input()
    ic = InputController()
    prepared = ic.prepare_params(data)

    approx(prepared.d, 0.1)        # 100 мм → 0.1 м
    approx(prepared.D, 0.3)        # 300 мм → 0.3 м
    approx(prepared.p1, 4e6)       # 4 МПа → 4e6 Па
    approx(prepared.dp, 2e4)       # 20 кПа → 2e4 Па
    approx(prepared.t1, 15.0)      # 15 °C


def test_temperature_kelvin_input():
    data = base_input()
    data["physPackage"]["physProperties"]["T"] = {"real": 288.15, "unit": "K"}
    ic = InputController()
    prepared = ic.prepare_params(data)
    approx(prepared.t1, 15.0)


def test_qv_units_m3s_and_m3h_and_lmin_parse():
    data = base_input()
    # m3/s вариант
    data["flowPackage"]["flowProperties"]["q_v"] = {"real": 0.0138888889, "unit": "m3/s"}
    ic = InputController()
    parsed = ic.parse(data)
    qv = float(parsed.values_si["q_v"])  # уже м3/с
    approx(qv, 0.0138888889, rel=1e-7)

    # l/min вариант (~ 50 м3/ч = 833.333... л/мин)
    data = base_input()
    data["flowPackage"]["flowProperties"]["q_v"] = {"real": 833.3333333, "unit": "l/min"}
    parsed = ic.parse(data)
    qv2 = float(parsed.values_si["q_v"])  # м3/с
    approx(qv2, 50 / 3600, rel=1e-6)


def test_p_atm_mmhg_to_pa():
    data = base_input()
    ic = InputController()
    parsed = ic.parse(data)
    patm = float(parsed.values_si["p_atm"])  # Па
    # 760 * 133.32 = 101323.2 Па (по таблице); допускаем крохотное расхождение
    approx(patm, 101323.2, rel=1e-6)


def test_missing_dp_raises_in_prepare():
    data = base_input()
    del data["physPackage"]["physProperties"]["dp"]
    ic = InputController()
    parsed = ic.parse(data)
    # parse не падает, просто предупреждения
    assert parsed.values_si  # что-то распарсилось

    with pytest.raises(ValueError) as ei:
        ic.prepare_params(data)
    msg = str(ei.value)
    assert "dp" in msg


def test_bad_diameters_raises():
    data = base_input()
    data["lenPackage"]["lenProperties"]["d20"] = {"real": 400, "unit": "mm"}
    ic = InputController()
    with pytest.raises(ValueError) as ei:
        ic.prepare_params(data)
    assert "диаметры" in str(ei.value).lower()


def test_extra_field_type_sharp_ignored():
    data = base_input()
    data["type"] = "sharp"
    ic = InputController()
    prepared = ic.prepare_params(data)
    approx(prepared.p1, 4e6)


def test_methodic_case_insensitive_ignored():
    data = base_input()
    data["physPackage"]["physProperties"]["methodic"] = "otHER"
    ic = InputController()
    prepared = ic.prepare_params(data)
    approx(prepared.p1, 4e6)


def test_nested_value_object_supported():
    data = base_input()
    data["physPackage"]["physProperties"]["p_abs"] = {"value": {"real": 4, "unit": "MPa"}}
    ic = InputController()
    prepared = ic.prepare_params(data)
    approx(prepared.p1, 4e6)


def test_unknown_unit_in_nonrequired_field_does_not_block_parse():
    data = base_input()
    data["physPackage"]["physProperties"]["p_atm"] = {"real": 1, "unit": "foo"}
    ic = InputController()
    parsed = ic.parse(data)
    # ищем сообщение об ошибке по p_atm
    assert any("[ERR] p_atm" in r for r in parsed.remarks)


def test_alias_path_D20_alternative():
    data = base_input()
    # Зададим D20 вместо D
    data["lenPackage"]["lenProperties"].pop("D")
    data["lenPackage"]["lenProperties"]["D20"] = {"real": 300, "unit": "mm"}
    ic = InputController()
    prepared = ic.prepare_params(data)
    approx(prepared.D, 0.3)


def test_qv_default_unit_when_plain_number():
    data = base_input()
    # Положим просто число — по спецификации для q_v default_unit = m3/h
    data["flowPackage"]["flowProperties"]["q_v"] = 50
    ic = InputController()
    parsed = ic.parse(data)
    qv = float(parsed.values_si["q_v"])  # м3/с
    approx(qv, 50 / 3600, rel=1e-9)
