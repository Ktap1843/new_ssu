from typing import Any, Dict, Optional, Tuple
import math

# ------------- утилиты -------------

def _get(d: Optional[dict], *path, default=None):
    cur = d or {}
    for p in path:
        if cur is None:
            return default
        cur = cur.get(p)
    return cur if cur is not None else default

def _is_nonempty_mapping(m) -> bool:
    return isinstance(m, dict) and any(v is not None for v in m.values())

def ivk_enabled(payload: Dict[str, Any]) -> bool:
    """IVK == True, если блок ivkProState существует и не пуст."""
    ivk = _get(payload, "data", "errorPackage", "errors", "ivkProState", default=None)
    return _is_nonempty_mapping(ivk)

def _normalize_to_percent(err_obj: Optional[dict],
                          base_value: Optional[float] = None) -> Optional[float]:
    """
    Привести значение ошибки к % (float).
    Поддержка:
      - errorTypeId == 'RelErr' с unit in {'percent','fraction','ppm'}
      - errorTypeId == 'AbsErr' -> нужен base_value (относительная = abs/base*100)
    """
    if not err_obj:
        return None

    etype = err_obj.get("errorTypeId")
    val = _get(err_obj, "value", default=None)
    if not isinstance(val, dict) or "real" not in val:
        return None

    real = val["real"]
    unit = val.get("unit", "percent")

    if etype == "RelErr":
        if unit == "percent":
            return float(real)
        elif unit in ("fraction", "share"):
            return float(real) * 100.0
        elif unit == "ppm":
            return float(real) / 10000.0
        else:
            return float(real)

    elif etype == "AbsErr":
        if base_value is None or base_value == 0:
            return None
        return abs(float(real)) / abs(float(base_value)) * 100.0

    return None

def _geom_sum_percent(values_percent) -> Optional[float]:
    vals = [v for v in values_percent if isinstance(v, (int, float))]
    if not vals:
        return None
    return math.sqrt(sum((float(v) ** 2 for v in vals)))

# ------------- расчёт ИВК -------------

def calc_ivk_error(payload: Dict[str, Any]) -> Tuple[Optional[float], Dict[str, Optional[float]]]:
    """Считаем только complError и intrError из ivkProState (в %), геом. суммой."""
    ivk = _get(payload, "data", "errorPackage", "errors", "ivkProState", default=None)
    if not _is_nonempty_mapping(ivk):
        return None, {}

    base_value = _get(ivk, "quantityValue", "real", default=None)

    compl = _normalize_to_percent(_get(ivk, "complError", default=None), base_value=base_value)
    intr  = _normalize_to_percent(_get(ivk, "intrError",  default=None), base_value=base_value)

    breakdown = {"ivk_compl_%": compl, "ivk_intr_%": intr}
    total = _geom_sum_percent([compl, intr])
    return total, breakdown

def apply_ivk_branch(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Если активен ИВК — пишем error_ivk и ставим has_ivk_priority=True."""
    if not ivk_enabled(payload):
        return payload

    total_ivk, breakdown = calc_ivk_error(payload)

    errors = _get(payload, "data", "errorPackage", "errors", default={})
    if errors is None:
        _get(payload, "data", "errorPackage")["errors"] = {}
        errors = _get(payload, "data", "errorPackage", "errors")

    errors["error_ivk"] = {
        "errorTypeId": "RelErr",
        "value": {"real": total_ivk or 0.0, "unit": "percent"},
        "breakdown": breakdown
    }
    errors["has_ivk_priority"] = True
    return payload
