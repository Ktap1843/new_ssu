from __future__ import annotations
from copy import deepcopy
from .ivk_branch import apply_ivk_branch, ivk_enabled
from typing import Dict, Any, Optional

from logger_config import get_logger
from errors.router import ErrorRouter

# для corrector'а
from errors.errors_handler.standards import STANDARD_REGISTRY
from errors.errors_handler.geom_sum import geometric_sum
from errors.errors_handler.error_types  import Result
from .ivk_branch import apply_ivk_branch, ivk_enabled


log = get_logger("HandleEntry")


def _rel_percent_block(x: float) -> Dict[str, Any]:
    return {
        "errorTypeId": "RelErr",
        "range": None,
        "value": {"real": float(x), "unit": "percent"},
    }

def _ensure_path(d: dict, *path: str) -> dict:
    cur = d
    for key in path:
        if key not in cur or cur[key] is None:
            cur[key] = {}
        cur = cur[key]
    return cur

def _write_pressure(target_errors: dict, res_block: dict) -> None:
    if not res_block or res_block.get("status") != "ok":
        return
    total = float(res_block["result"]["total_rel"])
    target_errors["error_p"] = _rel_percent_block(total)

def _write_temperature(target_errors: dict, res_block: dict) -> None:
    if not res_block or res_block.get("status") != "ok":
        return
    total = float(res_block["result"]["total_rel"])
    target_errors["error_T"] = _rel_percent_block(total)

def _write_density(target_errors: dict, res_block: dict) -> None:
    if not res_block or res_block.get("status") != "ok":
        return
    total = float(res_block["result"]["total_rel"])
    target_errors["error_rho_st"] = _rel_percent_block(total)

def _write_composition(pkg: dict, res_block: dict) -> None:
    if not res_block or res_block.get("status") != "ok":
        return
    res = res_block["result"]
    comp_pkg = _ensure_path(pkg, "data", "compositionErrorPackage")
    comp_pkg["result"] = {
        "policy": res.get("policy"),
        "upp": res.get("upp") or [],
        "theta_by_component": res.get("theta_by_component") or {},
        "delta_pp_by_component": res.get("delta_pp_by_component") or {},
        "delta_rho_1029": res.get("delta_rho_1029"),
        "delta_rho_1028": res.get("delta_rho_1028"),
        "begin_check_issues": res.get("begin_check_issues") or [],
        "end_check_issues": res.get("end_check_issues") or [],
        "final_comp_example": res.get("final_comp_example") or {},
    }


def process_package(big_payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Главный «вход»: прокидывает пакет через ErrorRouter и
    складывает результаты обратно в структуру payload.
    """
    data = deepcopy(big_payload)
    data = apply_ivk_branch(data)
    routed = ErrorRouter(data).run()

    errors_node = _ensure_path(data, "data", "errorPackage", "errors")
    _write_pressure(errors_node, routed.get("pressure"))
    _write_temperature(errors_node, routed.get("temperature"))
    _write_density(errors_node, routed.get("density"))
    _write_composition(data, routed.get("composition"))

    data.setdefault("diagnostics", {})
    data["diagnostics"]["router_status"] = {
        k: {"status": v.get("status"), "reason": v.get("reason")}
        for k, v in routed.items()
    }

    errs = data.get("data", {}).get("errorPackage", {}).get("errors", {})
    if errs.get("has_ivk_priority") and isinstance(errs.get("error_ivk"), dict):
        try:
            ivk_val = errs["error_ivk"]["value"]["real"]
        except Exception:
            ivk_val = None
        data["diagnostics"]["total_error"] = {
            "source": "IVK",
            "value_percent": ivk_val,
        }
    else:
        data["diagnostics"]["total_error"] = {
            "source": "router",
            "value_percent": None,  # сюда поставишь свою обычную сводную сумму, если нужна
        }

    return data


def _get_span_from_block(err_block: Optional[dict]) -> Optional[float]:
    """
    Пытаемся достать диапазон из самого блока ошибки вида:
    {"range":{"range":{"min":..., "max":...}, "unit":"..."}, ...}
    Возвращаем (max - min) или None.
    """
    if not err_block:
        return None
    r = (err_block.get("range") or {}).get("range") or {}
    mn = r.get("min")
    mx = r.get("max")
    if mn is None or mx is None:
        return None
    try:
        return float(mx) - float(mn)
    except Exception:
        return None

def _to_rel(std_id: str, err_block: Optional[dict],
            *, value: Optional[float], fallback_span: Optional[float]) -> float:
    """
    Перевод одной ошибки (intr/compl) в ОТНОСИТЕЛЬНУЮ, %.
    - std_id: идентификатор стандарта (например, 'рд-2025')
    - err_block: словарь с полями errorTypeId/value/range...
    - value: измеренное значение (нужно для AbsErr/FidErr)
    - fallback_span: range_max - range_min из контекста (если нет в err_block)
    """
    if not err_block:
        return 0.0

    std = STANDARD_REGISTRY.get(std_id)
    if not std:
        raise ValueError(f"Неизвестный стандарт: {std_id}")

    err_type = err_block.get("errorTypeId") or "RelErr"
    val_node = err_block.get("value") or {}
    try:
        raw = float(val_node.get("real", 0.0))
    except Exception:
        raw = 0.0

    # приоритет: диапазон из самого блока → из контекста
    span = _get_span_from_block(err_block)
    if span is None:
        span = fallback_span

    # std.to_rel_percent сам учтет err_type:
    # - RelErr: вернет как есть (в %)
    # - AbsErr: пересчитает через value
    # - FidErr: через span (percent-of-range)
    return float(std.to_rel_percent(err_type, raw, value=value, range_span=span))

def compute_corrector_from_state(
    state: Dict[str, Any],
    standard: str,
    *,
    value: Optional[float] = None,
    range_min: Optional[float] = None,
    range_max: Optional[float] = None,
) -> Result:
    """
    Универсальный «корректор» для пары ошибок (intr/compl) из state.
    Возвращает Result(main_rel, additional_rel, total_rel) в процентах.

    Примеры state:
    {
      "intrError":  {"errorTypeId":"RelErr","value":{"real":0.02,"unit":"percent"}},
      "complError": {"errorTypeId":"RelErr","value":{"real":0.01,"unit":"percent"}},
      # или:
      "intrError":  {"errorTypeId":"AbsErr","value":{"real":0.005,"unit":"same_as_value"}},
      # или:
      "intrError":  {"errorTypeId":"FidErr","value":{"real":0.5,"unit":"percent_of_range"},
                     "range":{"range":{"min":0.0,"max":100.0},"unit":"same_as_value"}}
    }
    """
    # span из контекста (если что)
    span_ctx: Optional[float] = None
    if range_min is not None and range_max is not None:
        try:
            span_ctx = float(range_max) - float(range_min)
        except Exception:
            span_ctx = None

    intr = state.get("intrError") or {}
    compl = state.get("complError") or {}

    main_rel = _to_rel(standard, intr, value=value, fallback_span=span_ctx)
    add_rel  = _to_rel(standard, compl, value=value, fallback_span=span_ctx)
    total_rel = geometric_sum(main_rel, add_rel)

    return Result(main_rel=main_rel, additional_rel=add_rel, total_rel=total_rel)

# --- Auto-added IVK hook ---
def apply_ivk_if_any(payload: dict) -> dict:
    """
    Вызывай это в начале сводного расчёта погрешности.
    Если присутствует ivkProState — посчитает error_ivk и проставит has_ivk_priority.
    """
    return apply_ivk_branch(payload)
