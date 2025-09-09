"""Единообразные конвертеры единиц для проекта new_ssu.

Покрытие:
- Давление: Pa, kPa, MPa, bar, kgf/cm2, kgf/m2, mmHg (мм рт.ст.), mmH2O (мм вод.ст.), atm, torr.
- Длина: m, mm, cm, um/µm, in, ft.
- Температура: K ↔ °C.

Принципы:
- Явные словари коэффициентов к SI, устойчивые к синонимам/регистру/пробелам.
- Валидные ошибки при неизвестных единицах.
- Без внешних зависимостей.
"""
from __future__ import annotations

from typing import Dict

# --- helpers -----------------------------------------------------------------

def _norm_unit(u: str | None) -> str:
    if not u:
        return ""
    s = str(u).strip().lower()
    # унифицируем символы
    s = (
        s.replace("°", "")
         .replace("·", "_")
         .replace("*", "_")
         .replace(" ", "")
         .replace("-", "")
         .replace("/", "_")
    )
    # кириллица → латиница для спец. случаев
    trans = str.maketrans({
        "р": "p", "т": "t", "с": "c", "м": "m", "в": "v", "о": "o", "д": "d", ".": "",
        "Р": "p", "Т": "t", "С": "c", "М": "m", "В": "v", "О": "o", "Д": "d",
        "х": "x", "Х": "x",
    })
    s = s.translate(trans)
    # унификация распространённых форм
    aliases: Dict[str, str] = {
        "ммртст": "mmhg",
        "mmrtst": "mmhg",
        "mmrtst": "mmhg",
        "ммводст": "mmh2o",
        "mmvodst": "mmh2o",
        "mmhg": "mmhg",
        "mm_hg": "mmhg",
        "mmhg_": "mmhg",
        "ммртст_": "mmhg",
        "mmh2o": "mmh2o",
        "mm_h2o": "mmh2o",
        "ммводст_": "mmh2o",
        "кгс_см2": "kgf_cm2",
        "kgscm2": "kgf_cm2",
        "кгс_м2": "kgf_m2",
        "kgs_m2": "kgf_m2",
        "micrometer": "um",
        "micrometre": "um",
        "µm": "um",
    }
    return aliases.get(s, s)


# --- pressure ----------------------------------------------------------------

# коэффициенты перевода ИЗ единицы В паскали (Pa per unit)
_P_TO_PA: Dict[str, float] = {
    "pa": 1.0,
    "pascal": 1.0,
    "pascals": 1.0,
    "kpa": 1e3,
    "mpa": 1e6,
    "bar": 1e5,
    "bars": 1e5,
    "atm": 101325.0,
    "torr": 133.32,   # ~mmHg
    "mmhg": 133.32,   # 1 мм рт.ст.
    "mmh2o": 9.80665, # 1 мм вод.ст.
    "kgf_cm2": 9.80665e4,
    "kgf_m2": 9.80665,
}


def convert_pressure(value: float, from_unit: str, to_unit: str = "Pa") -> float:
    """Перевод давления между единицами.

    Всегда идём через Pa. Бросает ValueError при неизвестных единицах.
    """
    fu = _norm_unit(from_unit)
    tu = _norm_unit(to_unit)
    if fu not in _P_TO_PA:
        raise ValueError(f"Неизвестная единица давления: '{from_unit}'")
    if tu not in _P_TO_PA:
        raise ValueError(f"Неизвестная целевая единица давления: '{to_unit}'")
    pa = float(value) * _P_TO_PA[fu]
    return pa / _P_TO_PA[tu]


# --- length ------------------------------------------------------------------

# коэффициенты ИЗ единицы В метры
_L_TO_M: Dict[str, float] = {
    "m": 1.0,
    "meter": 1.0,
    "metre": 1.0,
    "mm": 1e-3,
    "millimeter": 1e-3,
    "millimetre": 1e-3,
    "cm": 1e-2,
    "centimeter": 1e-2,
    "centimetre": 1e-2,
    "um": 1e-6,
    "micrometer": 1e-6,
    "micrometre": 1e-6,
    "in": 0.0254,
    "inch": 0.0254,
    "ft": 0.3048,
    "foot": 0.3048,
}


def convert_length(value: float, from_unit: str, to_unit: str = "m") -> float:
    """Перевод длины между единицами.
    Через метры. Бросает ValueError при неизвестных единицах.
    """
    fu = _norm_unit(from_unit)
    tu = _norm_unit(to_unit)
    if fu not in _L_TO_M:
        raise ValueError(f"Неизвестная единица длины: '{from_unit}'")
    if tu not in _L_TO_M:
        raise ValueError(f"Неизвестная целевая единица длины: '{to_unit}'")
    m = float(value) * _L_TO_M[fu]
    return m / _L_TO_M[tu]


# --- temperature -------------------------------------------------------------

def kelvin_to_celsius(T_k: float) -> float:
    """K → °C"""
    return float(T_k) - 273.15


def celsius_to_kelvin(T_c: float) -> float:
    """°C → K"""
    return float(T_c) + 273.15
