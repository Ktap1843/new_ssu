# file: errors/error_adapter.py
from __future__ import annotations

import math
from typing import Any, Dict, Iterable, Optional, Tuple

from logger_config import get_logger

log = get_logger("ErrorsAdapter")

# --- Unit converters -------------------------------------------------------
# Приводим к долям/СИ, чтобы дальше не думать про единицы
_P_TO_SI = {
    "percent": 0.01,  # 1% → 0.01
}

_ABS_TO_SI = {
    # Temperature
    "C": 1.0,  # |ΔT| одинаково в K и °C
    "K": 1.0,
    # Pressure
    "Pa": 1.0,
    "kPa": 1_000.0,
    "MPa": 1_000_000.0,
    "mm_Hg": 133.322,  # ГОСТ ≈ 133.322 Па
}


def _rss(values: Iterable[float]) -> float:
    s = 0.0
    for v in values:
        s += float(v) ** 2
    return math.sqrt(s)


def _norm_err_node(node: Optional[Dict[str, Any]]) -> Optional[Tuple[str, float]]:
    """{errorTypeId, value:{real, unit}} → ("rel"|"abs", value_SI_or_fraction).
    Возвращает None, если данных нет.
    """
    if not node:
        return None
    v = (node.get("value") or {})
    if "real" not in v:
        return None
    real = float(v["real"])
    unit = (v.get("unit") or "").strip()
    etype = (node.get("errorTypeId") or "").strip()

    if etype == "RelErr":
        mul = _P_TO_SI.get(unit)
        if mul is None:
            raise ValueError(f"Неизвестная единица относительной погрешности: {unit}")
        return ("rel", real * mul)

    if etype == "AbsErr":
        mul = _ABS_TO_SI.get(unit)
        if mul is None:
            raise ValueError(f"Неизвестная единица абсолютной погрешности: {unit}")
        return ("abs", real * mul)

    raise ValueError(f"Неизвестный тип погрешности: {etype}")


def _collect_errors(pro_state: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Собираем intr/compl/converter*/outSignal* по RSS. Возвращаем {rel?, abs?}."""
    if not pro_state:
        return {}

    keys = (
        "intrError",
        "complError",
        "converter1IntrError",
        "converter1ComplError",
        "converter2IntrError",
        "converter2ComplError",
        "outSignalIntrError",
        "outSignalComplError",
    )

    rel: list[float] = []
    abs_: list[float] = []

    for k in keys:
        pair = _norm_err_node(pro_state.get(k))
        if not pair:
            continue
        kind, val = pair
        if kind == "rel":
            rel.append(val)
        else:
            abs_.append(val)

    out: Dict[str, float] = {}
    if rel:
        out["rel"] = _rss(rel)
    if abs_:
        out["abs"] = _rss(abs_)
    return out


# --- Public API ------------------------------------------------------------

def compute_errors(
    errors_dict: Dict[str, Any],
    values_si: Dict[str, float] | None = None,
    ssu_results: Dict[str, Any] | None = None,
    flow_results: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    """Главная точка входа для расчёта погрешностей.

    ВНИМАНИЕ: по договорённости сейчас учитываем ТОЛЬКО абсолютное давление.
    Узлы izbPressureErrorProState и atmPressureErrorProState игнорируются.

    Возвращает словарь:
    {
      "delta_T": <K|None>,
      "delta_p": <Pa|None>,        # ТОЛЬКО из absPressureErrorProState
      "delta_dp": <Pa|None>,       # из diffPressureErrorProState, если задано
      "delta_corrector": <frac|None>,
      "flow_rel": <frac|None>,
      "details": {...}             # раскладка по узлам
    }
    """
    details: Dict[str, Any] = {}

    # temperature
    t_state = errors_dict.get("temperatureErrorProState")
    t_errs = _collect_errors(t_state)
    delta_T = t_errs.get("abs")
    details["temperature"] = {"combined": t_errs, "raw": t_state}

    # absolute pressure (единственный источник для delta_p)
    p_abs_state = errors_dict.get("absPressureErrorProState")
    p_abs_errs = _collect_errors(p_abs_state)
    delta_p = p_abs_errs.get("abs")  # только Pa; никаких fallback'ов
    details["p_abs"] = {"combined": p_abs_errs, "raw": p_abs_state}

    # differential pressure (optional)
    dp_state = errors_dict.get("diffPressureErrorProState")
    dp_errs = _collect_errors(dp_state)
    delta_dp = dp_errs.get("abs")
    details["dp"] = {"combined": dp_errs, "raw": dp_state}

    # corrector (relative)
    corr_state = errors_dict.get("calcCorrectorProState")
    corr_errs = _collect_errors(corr_state)
    delta_corrector = corr_errs.get("rel")
    details["corrector"] = {"combined": corr_errs, "raw": corr_state}

    # flowmeter (relative)
    flow_state = errors_dict.get("flowErrorProState")
    flow_errs = _collect_errors(flow_state)
    flow_rel = flow_errs.get("rel")
    details["flow"] = {"combined": flow_errs, "raw": flow_state}

    return {
        "delta_T": delta_T,
        "delta_p": delta_p,
        "delta_dp": delta_dp,
        "delta_corrector": delta_corrector,
        "flow_rel": flow_rel,
        "details": details,
    }


def compute_errors_safe(errors_dict: Dict[str, Any], **ctx: Any) -> Dict[str, Any]:
    """Не роняет пайплайн: лог и пустой ответ при ошибке."""
    try:
        return compute_errors(errors_dict, **ctx)
    except Exception as e:
        log.warning("Ошибка расчёта погрешностей: %s", e)
        return {
            "delta_T": None,
            "delta_p": None,
            "delta_dp": None,
            "delta_corrector": None,
            "flow_rel": None,
            "details": {"error": str(e)},
        }


# file: controllers/calculation_adapter.py  (integration fragment)
# add near imports:
# from errors.error_adapter import compute_errors_safe

# inside run_calculation(...), после расчётов SSU/flow/straightness:
#
#     errors_block = None
#     err_pkg = (raw.get("errorPackage") or {})
#     if err_pkg.get("hasToCalcErrors") and err_pkg.get("errors"):
#         errors_block = compute_errors_safe(
#             err_pkg["errors"],
#             values_si=values_si,
#             ssu_results=ssu_results,
#             flow_results=flow_result,
#         )
#
#     return {
#         "ssu_results": ssu_results,
#         "flow_results": flow_result,
#         "straightness": straightness_result,
#         "errors": errors_block,
#     }
