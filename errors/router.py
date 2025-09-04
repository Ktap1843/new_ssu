from __future__ import annotations
from typing import Dict, Any, Optional
from logger_config import get_logger

from errors.errors_handler.calculators.pressure_abs import PressureCalculator as PressureCalc
from errors.errors_handler.calculators.temperature import TemperatureCalculator as TemperatureCalc
from errors.errors_handler.calculators.density import DensityStCalculator as DensityCalc
from errors.errors_handler.calculators.composition import CompositionCalculator as CompositionCalc
from errors.errors_handler.standards import STANDARD_REGISTRY

log = get_logger("ErrorRouter")

# ------------------- helpers -------------------

def _preferred_standard_id(big: dict) -> str:
    """
    Выбираем ID стандарта:
      1) если во входном пакете явно задан (data.errorPackage.standard | standardId) и он есть в реестре — используем его;
      2) иначе пробуем набор известных имён в порядке предпочтения;
      3) иначе берём первый попавшийся из STANDARD_REGISTRY;
      4) если пусто — бросаем исключение.
    """
    # 1) из входа
    errors_pkg = ((big.get("data") or {}).get("errorPackage") or {})
    cand = errors_pkg.get("standard") or errors_pkg.get("standardId")
    if isinstance(cand, str) and cand in STANDARD_REGISTRY:
        return cand

    # 2) предпочтительный список (подставь свои реальные ID, если отличаются)
    for name in ("RelOnly", "Default", "GOST_30319_2_2015", "GOST", "ISO"):
        if name in STANDARD_REGISTRY:
            return name

    # 3) первый доступный
    try:
        return next(iter(STANDARD_REGISTRY.keys()))
    except StopIteration:
        pass

    # 4) критическая ситуация
    raise ValueError("STANDARD_REGISTRY пуст или не содержит подходящих стандартов.")

def _read_real_percent(node: Optional[dict]) -> Optional[float]:
    if not node:
        return None
    v = node.get("value") or {}
    unit = str(v.get("unit", "")).lower()
    if unit not in ("percent", "%", "percents"):
        return None
    try:
        return float(v.get("real"))
    except Exception:
        return None

def _map_converters_from(node: dict) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    def copy_if_present(src_key: str, dst_key: Optional[str] = None):
        val = node.get(src_key)
        if val is not None:
            out[dst_key or src_key] = val
    for i in (1, 2, 3):
        copy_if_present(f"converter{i}IntrError")
        copy_if_present(f"converter{i}ComplError")
        copy_if_present(f"converter{i}Range")
        copy_if_present(f"converter{i}Enabled")
    options = node.get("options") or {}
    if options:
        out["options"] = options
    else:
        if node.get("converter2IntrError") is not None and out.get("options") is None:
            out["options"] = {"conv2_func": "quadratic"}
    return out

# ------------------- payload builders -------------------

def _build_pressure_payload(big: dict):
    std_id = _preferred_standard_id(big)

    errors = ((big.get("data") or {}).get("errorPackage") or {}).get("errors") or {}
    phys   = ((big.get("data") or {}).get("physPackage") or {}).get("physProperties") or {}
    node = errors.get("absPressureErrorProState") or errors.get("izbPressureErrorProState") or errors.get("atmPressureErrorProState")
    if not node:
        return None, "pressure: no errorProState block"
    err_type = (node.get("intrError") or {}).get("errorTypeId") or (node.get("complError") or {}).get("errorTypeId") or "RelErr"
    main  = _read_real_percent(node.get("intrError")) or 0.0
    addit = _read_real_percent(node.get("complError")) or 0.0
    value = None
    vnode = phys.get("p_abs") or phys.get("p") or phys.get("pressure") or phys.get("P")
    if isinstance(vnode, dict) and vnode.get("real") is not None:
        value = float(vnode["real"])
    rng = node.get("measInstRange") or {}
    rr  = (rng.get("range") or {})
    p_min = rr.get("min"); p_max = rr.get("max")
    payload = {
        "standard": std_id,
        "error_type": err_type,
        "main": float(main),
        "additional": float(addit),
    }
    if value is not None:
        payload["value"] = value
    if p_min is not None:
        payload["p_min"] = float(p_min)
    if p_max is not None:
        payload["p_max"] = float(p_max)
    qv = node.get("quantityValue")
    if qv:
        payload["by_formula"] = True
        payload["formula"] = {
            "quantityValue": qv,
            "constValue": float(node.get("constValue") or 0.0),
            "slopeValue": float(node.get("slopeValue") or 0.0),
        }
    payload.update(_map_converters_from(node))
    return payload, None

def _build_temperature_payload(big: dict):
    std_id = _preferred_standard_id(big)

    errors = ((big.get("data") or {}).get("errorPackage") or {}).get("errors") or {}
    phys   = ((big.get("data") or {}).get("physPackage") or {}).get("physProperties") or {}
    node = errors.get("temperatureErrorProState")
    if not node:
        return None, "temperature: no errorProState block"
    t_c_node = phys.get("T") or {}
    if not isinstance(t_c_node, dict) or t_c_node.get("real") is None:
        return None, "temperature: physProperties.T is required"
    t_k = float(t_c_node["real"]) + 273.15
    err_type = (node.get("intrError") or {}).get("errorTypeId") or (node.get("complError") or {}).get("errorTypeId") or "RelErr"
    main  = _read_real_percent(node.get("intrError")) or 0.0
    addit = _read_real_percent(node.get("complError")) or 0.0
    rng = node.get("measInstRange") or {}
    rr  = (rng.get("range") or {})
    rmin = rr.get("min"); rmax = rr.get("max")
    payload = {
        "standard": std_id,
        "error_type": err_type,
        "value": t_k,
        "main": float(main),
        "additional": float(addit),
    }
    if rmin is not None:
        payload["range_min"] = float(rmin)
    if rmax is not None:
        payload["range_max"] = float(rmax)
    qv = node.get("quantityValue")
    if qv == "t_abs" or (node.get("constValue") is not None or node.get("slopeValue") is not None):
        payload["by_formula"] = True
        payload["formula"] = {
            "quantityValue": "t_abs",
            "constValue": float(node.get("constValue") or 0.0),
            "slopeValue": float(node.get("slopeValue") or 0.0),
        }
    payload.update(_map_converters_from(node))
    return payload, None

def _build_density_payload(big: dict):
    std_id = _preferred_standard_id(big)

    errors = ((big.get("data") or {}).get("errorPackage") or {}).get("errors") or {}
    phys   = ((big.get("data") or {}).get("physPackage") or {}).get("physProperties") or {}
    node = errors.get("stDensityErrorProState") or errors.get("densityErrorProState")
    if not node:
        return None, "density: no errorProState block"
    rho_node = phys.get("rho_st") or phys.get("rho")
    rho_value = None
    if isinstance(rho_node, dict) and rho_node.get("real") is not None:
        rho_value = float(rho_node["real"])
    err_type = (node.get("intrError") or {}).get("errorTypeId") or \
               (node.get("complError") or {}).get("errorTypeId") or \
               (node.get("uppError")  or {}).get("errorTypeId") or "RelErr"
    main = _read_real_percent(node.get("intrError")) or 0.0
    addt = _read_real_percent(node.get("complError")) or 0.0
    payload = {
        "standard": std_id,
        "error_type": err_type,
        "main": float(main),
        "additional": float(addt),
    }
    if rho_value is not None:
        payload["value"] = rho_value
    payload.update(_map_converters_from(node))
    return payload, None

# ---- helper: упаковать Result в dict ----
def _res_to_dict(res) -> Dict[str, float]:
    return {
        "main_rel": float(res.main_rel),
        "additional_rel": float(res.additional_rel),
        "total_rel": float(res.total_rel),
    }

# ------------------- router -------------------

class ErrorRouter:
    def __init__(self, big_payload: Dict[str, Any]):
        self.big = big_payload

    def run(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {}

        # PRESSURE
        try:
            p_payload, p_reason = _build_pressure_payload(self.big)
            if not p_payload:
                out["pressure"] = {"status": "skipped", "reason": p_reason}
            else:
                res = PressureCalc(p_payload).compute()
                out["pressure"] = {"status": "ok", "result": _res_to_dict(res)}
        except Exception as e:
            log.exception("pressure error")
            out["pressure"] = {"status": "error", "reason": str(e)}

        # TEMPERATURE
        try:
            t_payload, t_reason = _build_temperature_payload(self.big)
            if not t_payload:
                out["temperature"] = {"status": "skipped", "reason": t_reason}
            else:
                res = TemperatureCalc(t_payload).compute()
                out["temperature"] = {"status": "ok", "result": _res_to_dict(res)}
        except Exception as e:
            log.exception("temperature error")
            out["temperature"] = {"status": "error", "reason": str(e)}

        # DENSITY
        try:
            d_payload, d_reason = _build_density_payload(self.big)
            if not d_payload:
                out["density"] = {"status": "skipped", "reason": d_reason}
            else:
                res = DensityCalc(d_payload).compute()
                out["density"] = {"status": "ok", "result": _res_to_dict(res)}
        except Exception as e:
            log.exception("density error")
            out["density"] = {"status": "error", "reason": str(e)}

        # COMPOSITION
        try:
            comp_pkg = (self.big.get("data") or {}).get("compositionErrorPackage")
            if not comp_pkg:
                out["composition"] = {"status": "skipped", "reason": "composition: no compositionErrorPackage"}
            else:
                res = CompositionCalc({"compositionErrorPackage": comp_pkg}).compute(mode="auto", methane_name="Methane")
                out["composition"] = {"status": "ok", "result": res}
        except Exception as e:
            log.exception("composition error")
            out["composition"] = {"status": "error", "reason": str(e)}

        return out
