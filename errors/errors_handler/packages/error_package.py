# errors/errors_handler/packages/error_package.py
"""
Обработчик блока `errorPackage` из входных данных.

Задача:
- взять `errorPackage.errors` (узлы вида ...ProState),
- смаппить на нужные калькуляторы (registry),
- подготовить унифицированный payload под твой BaseCalculator,
- выполнить расчёт и выдать результат в формате:
    {"errorTypeId": "RelErr", "range": None, "value": {"real": <%, unit: "percent"}}.
"""

from __future__ import annotations
from typing import Any, Dict, Optional
from errors.errors_handler.calculators.registry import get_calculator_class, has as calc_exists
from errors.errors_handler.error_types import Result

# ---------- Утилиты извлечения полей из узлов ----------
def _node(d: Optional[dict], key: str) -> dict:
    return (d or {}).get(key) or {}

def _val_real(err_node: Optional[dict]) -> Optional[float]:
    if not err_node:
        return None
    v = (err_node.get("value") or {})
    if v.get("real") is None:
        return None
    try:
        return float(v.get("real"))
    except Exception:
        return None

def _err_type(err_node: Optional[dict]) -> Optional[str]:
    if not err_node:
        return None
    return err_node.get("errorTypeId")

# если захочешь тащить id стандарта из более верхнего уровня — подставь тут
def _pick_standard_id(state: dict) -> str:
    return state.get("standardId") or "Default"

# Скопировать в payload «как пришли» поля конвертеров (UI-формат)
def _copy_converters_to_payload(state: dict, payload: dict) -> None:
    for name in (
        # первый преобразователь
        "converter1IntrError", "converter1ComplError", "converter1Range", "converter1Enabled",
        # второй преобразователь
        "converter2IntrError", "converter2ComplError", "converter2Range", "converter2Enabled",
        # на будущее — третий, если появится
        "converter3IntrError", "converter3ComplError", "converter3Range", "converter3Enabled",
        # общие параметры
        "errorInputMethod", "quantityValue", "slopeValue", "constValue",
        "measInstRange", "outSignalIntrError", "outSignalComplError",
        "options",  # любые опции для калькулятора
    ):
        if name in state:
            payload[name] = state[name]

# Унифицированный payload под твою базу (BaseCalculator)
def _to_payload_common(state: dict) -> dict:
    intr = _node(state, "intrError")
    compl = _node(state, "complError")

    payload = {
        "error_type": _err_type(intr) or "RelErr",
        "main": float(_val_real(intr) or 0.0),
        "additional": float(_val_real(compl) or 0.0),
        "standard": _pick_standard_id(state),
    }
    _copy_converters_to_payload(state, payload)
    return payload


# ---------- Маппинг ключей errorPackage.errors -> calc_id + адаптация payload ----------
def _map_key_to_calc_and_payload(key: str, state: dict, phys: Optional[dict]) -> tuple[str, dict] | None:
    """
    Возвращает (calc_id, payload) или None, если ключ пока не поддержан.
    Здесь же можно тонко адаптировать payload для конкретного калькулятора.
    """
    # Абсолютное давление
    if key == "absPressureErrorProState":
        payload = _to_payload_common(state)
        # Если error_type == AbsErr — калькулятору может понадобиться 'value' (p_abs) для пересчёта в относит.
        if payload["error_type"] == "AbsErr":
            # попробуем взять из physPackage, если передан
            p_abs = None
            if phys and "physProperties" in phys:
                pnode = (phys["physProperties"] or {}).get("p_abs") or {}
                try:
                    p_abs = float((pnode.get("real")))
                except Exception:
                    p_abs = None
            if p_abs is not None:
                payload["value"] = p_abs
        return "pressure_abs", payload

    # Температура
    if key == "temperatureErrorProState":
        payload = _to_payload_common(state)
        if payload["error_type"] == "AbsErr":
            t_val = None
            if phys and "physProperties" in phys:
                tnode = (phys["physProperties"] or {}).get("T") or {}
                try:
                    t_val = float((tnode.get("real")))
                except Exception:
                    t_val = None
            if t_val is not None:
                payload["value"] = t_val
        return "temperature", payload

    # Плотность при СУ (пример из твоего JSON с UppErr диапазоном)
    if key == "stDensityErrorProState":
        payload = {
            "error_type": "UppErr",          # в примере у тебя именно UppErr
            "main": 0.0,
            "additional": 0.0,
            "standard": _pick_standard_id(state),
            "uppError": state.get("uppError"),   # сам калькулятор прочитает min/max и переведёт в %
        }
        return "density_st", payload

    # Погрешность первичного расходомера (flowErrorProState)
    if key == "flowErrorProState":
        payload = _to_payload_common(state)
        # В state есть outSignalIntrError/outSignalComplError — реши как учитывать внутри калькулятора.
        # Пока просто пробрасываем — калькулятор сам применит.
        return "flow_primary", payload

    # Корректор (без преобразователей)
    if key == "calcCorrectorProState":
        payload = _to_payload_common(state)
        return "corrector", payload

    # Неизвестный/пока не реализованный — пропускаем
    return None


# ---------- Публичная функция пакета ----------
def process_error_package(pkg: dict, phys: Optional[dict] = None) -> dict:
    """
    На входе: поддерево из твоего JSON: data["errorPackage"].
    На выходе: dict по тем же ключам, где есть расчёт, в виде:
        {
            "<key>": {"errorTypeId": "RelErr", "range": None, "value": {"real": <percent>, "unit": "percent"}},
            ...
        }
    Ключи без данных или не поддержанные — пропускаются.
    """
    errors = (pkg or {}).get("errors") or {}
    results: Dict[str, Any] = {}

    for key, state in errors.items():
        if state is None:
            continue

        mapres = _map_key_to_calc_and_payload(key, state, phys)
        if not mapres:
            continue

        calc_id, payload = mapres
        if not calc_exists(calc_id):
            # калькулятор ещё не подключён — просто пропускаем
            continue

        CalcClass = get_calculator_class(calc_id)
        calc = CalcClass(payload)
        try:
            res: Result = calc.compute()
            results[key] = {
                "errorTypeId": "RelErr",
                "range": None,
                "value": {"real": res.total_rel, "unit": "percent"},
            }
        except Exception as e:
            # Можно вернуть текст ошибки по ключу, если тебе это нужно отображать
            results[key] = {
                "errorTypeId": "RelErr",
                "range": None,
                "value": {"real": None, "unit": "percent"},
                "errorString": f"{type(e).__name__}: {e}",
            }

    return results


incoming = data["data"]["errorPackage"]  # из твоего большого JSON
phys      = data["data"].get("physPackage")  # чтобы подхватить p_abs, T и пр. для AbsErr→Rel

errors_out = process_error_package(incoming, phys=phys)
print(errors_out)