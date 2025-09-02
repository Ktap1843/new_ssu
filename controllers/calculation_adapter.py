# file: controllers/calculation_adapter.py
"""
Адаптер вызова CalculationController:
- Создаёт контроллер с разными конструкторами (__init__).
- Совместимость: если нужен data["flowdata"], собираем legacy-вид (включая straightness_params) и пробуем снова.
- Если methodic == "other" (без учета регистра) — физику не трогаем, сразу идём в ручные шаги:
    _create_orifice() → _calculate_flow()
- В результат кладём adapter_debug: попытки конструирования и входы для _create_orifice().
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Tuple

try:
    from controllers.calculation_controller import CalculationController  # type: ignore
    _HAVE_CALC_CTRL = True
except Exception:
    CalculationController = None  # type: ignore
    _HAVE_CALC_CTRL = False


# ------------ helpers ------------

def _is_keyerror(exc: BaseException, key: str) -> bool:
    return isinstance(exc, KeyError) and bool(exc.args) and exc.args[0] == key


def _build_straightness_params(raw: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """Собираем flowdata.straightness_params из lenPackage.* с безопасными дефолтами."""
    len_pkg = (raw.get("lenPackage") or {})
    lp = (len_pkg.get("lenProperties") or {})
    req = (len_pkg.get("request") or {})

    params: Dict[str, Any] = {
        "D": lp.get("D") or lp.get("D20") or {"real": float(getattr(prepared, "D", 0.0)) * 1000.0, "unit": "mm"},
        "DN": lp.get("DN"),
        "measSection": lp.get("measSection"),
        "localResistance": lp.get("localResistance"),
        "lensCompliance": lp.get("lensCompliance"),
        "calc": bool(req.get("calc", False)),
        "check": bool(req.get("check", False)),
        "usingCorrectionFactor": True,
        "DLessThan1p": True,
    }
    return params


def _build_legacy_data(raw: Dict[str, Any], parsed: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """Строит legacy-структуру {"flowdata": {...}} и дублирует пакеты верхнего уровня для совместимости."""
    len_props = (((raw.get("lenPackage") or {}).get("lenProperties")) or {})
    phys_props = (((raw.get("physPackage") or {}).get("physProperties")) or {})
    flow_props = (((raw.get("flowPackage") or {}).get("flowProperties")) or {})

    d20_node = len_props.get("d20") or {"real": float(prepared.d) * 1000.0, "unit": "mm"}
    D20_node = (len_props.get("D") or len_props.get("D20")) or {"real": float(prepared.D) * 1000.0, "unit": "mm"}

    # p/dp/T — если в исходнике узел {real, unit}, оставим его; иначе подставим число в SI
    p_node  = phys_props.get("p_abs") or float(prepared.p1)   # Па
    dp_node = phys_props.get("dp")    or float(prepared.dp)   # Па
    T_node  = phys_props.get("T")     or float(prepared.t1)   # °C

    flowdata = {
        "constrictor_params": {"d20": d20_node, "D20": D20_node},
        "environment_parameters": {"p": p_node, "dp": dp_node, "T": T_node},
        "physical_properties": {"R": phys_props.get("R"), "Z": phys_props.get("Z")},
        "flow_properties": {"q_v": flow_props.get("q_v"), "q_st": flow_props.get("q_st")},
        "straightness_params": _build_straightness_params(raw, prepared),
    }

    # Дополнительно положим исходные пакеты — если где-то обращаются напрямую
    legacy_top = {
        "flowdata": flowdata,
        "physPackage": raw.get("physPackage") or {},
        "lenPackage": raw.get("lenPackage") or {},
        "flowPackage": raw.get("flowPackage") or {},
    }
    return legacy_top


def _build_init_kwargs(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    if CalculationController is None:
        return {}
    try:
        sig = inspect.signature(CalculationController.__init__)
    except Exception:
        return {}

    candidates = {
        "data": raw, "raw": raw, "input": raw, "input_data": raw, "request": raw,
        "prepared": prepared, "prepared_params": prepared, "prepared_data": prepared, "params": prepared,
        "parsed": parsed, "values": parsed, "values_si": parsed, "parsed_values": parsed,
        "context": {"prepared": prepared, "parsed": parsed, "raw": raw},
    }
    kwargs: Dict[str, Any] = {}
    for name in sig.parameters.keys():
        if name != "self" and name in candidates:
            kwargs[name] = candidates[name]
    return kwargs


def _try_construct(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    return CalculationController(*args, **kwargs)  # type: ignore[misc]


def _instantiate_controller(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any], debug: Dict[str, Any]) -> Optional[Any]:
    """Создаёт экземпляр; на KeyError('flowdata'|'straightness_params') → подменяем raw→legacy."""
    if not _HAVE_CALC_CTRL or CalculationController is None:
        debug["construct_attempts"].append("CalculationController not importable")
        return None

    legacy = _build_legacy_data(raw, parsed, prepared)

    # 1) __init__()
    try:
        debug["construct_attempts"].append("try: __init__()")
        return _try_construct((), {})
    except TypeError as e:
        debug["construct_attempts"].append(f"__init__() TypeError: {e}")
    except Exception as e:
        debug["construct_attempts"].append(f"__init__() Exception: {e}")
        if _is_keyerror(e, "flowdata") or _is_keyerror(e, "straightness_params"):
            try:
                debug["construct_attempts"].append("try: __init__(data=legacy, prepared_params=prepared)")
                return _try_construct((), {"data": legacy, "prepared_params": prepared})
            except Exception as e2:
                debug["construct_attempts"].append(f"__init__(data=legacy,prepared_params=prepared) Exception: {e2}")

    # 2) kwargs
    kw = _build_init_kwargs(prepared, parsed, raw)
    if kw:
        try:
            debug["construct_attempts"].append(f"try: __init__(**kw:{list(kw.keys())})")
            return _try_construct((), kw)
        except TypeError as e:
            debug["construct_attempts"].append(f"__init__(**kw) TypeError: {e}")
        except Exception as e:
            debug["construct_attempts"].append(f"__init__(**kw) Exception: {e}")
            if _is_keyerror(e, "flowdata") or _is_keyerror(e, "straightness_params"):
                for key in ("data", "raw", "input", "input_data", "request"):
                    if key in kw:
                        kw[key] = legacy
                try:
                    debug["construct_attempts"].append(f"try: __init__(**kw_legacy:{list(kw.keys())})")
                    return _try_construct((), kw)
                except Exception as e2:
                    debug["construct_attempts"].append(f"__init__(**kw_legacy) Exception: {e2}")

    # 3) позиционные
    combos = [
        (("raw", "prepared"), {}),  # (data, prepared_params)
        (("prepared", "raw"), {}),  # (prepared_params, data) → переставим при legacy
        (("raw",), {}),
    ]
    valmap = {"raw": raw, "prepared": prepared}
    for names, kwd in combos:
        args = tuple(valmap[n] for n in names)
        try:
            debug["construct_attempts"].append(f"try: __init__{names}")
            return _try_construct(args, kwd)
        except TypeError as e:
            debug["construct_attempts"].append(f"__init__{names} TypeError: {e}")
        except Exception as e:
            debug["construct_attempts"].append(f"__init__{names} Exception: {e}")
            if _is_keyerror(e, "flowdata") or _is_keyerror(e, "straightness_params"):
                # подменим raw→legacy
                args_legacy = tuple((_build_legacy_data(raw, parsed, prepared) if n == "raw" else valmap[n]) for n in names)
                # если порядок (prepared, raw) — переставим (data, prepared)
                if names == ("prepared", "raw"):
                    args_legacy = (args_legacy[1], args_legacy[0])
                try:
                    debug["construct_attempts"].append(f"try: __init__{names}_legacy(raw→legacy)")
                    return _try_construct(args_legacy, kwd)
                except Exception as e2:
                    debug["construct_attempts"].append(f"__init__{names}_legacy Exception: {e2}")

    return None


def _collect_state(ctrl: Any) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for name in ("orifice", "orifice_data", "orifice_result"):
        if hasattr(ctrl, name):
            out["orifice"] = getattr(ctrl, name)
            break
    for name in ("flow", "flow_result", "flow_data"):
        if hasattr(ctrl, name):
            out["flow"] = getattr(ctrl, name)
            break
    for name in ("result", "output"):
        if hasattr(ctrl, name):
            out["summary"] = getattr(ctrl, name)
            break
    return out


# ------------ public ------------

def run_calculation(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    debug: Dict[str, Any] = {"construct_attempts": []}

    # решаем, скипать ли физику
    methodic = (
        (raw.get("physPackage") or {}).get("physProperties", {}).get("methodic")
    )
    skip_physics = isinstance(methodic, str) and methodic.strip().lower() == "other"
    debug["skip_physics_due_to_methodic"] = bool(skip_physics)
    debug["methodic_value"] = methodic

    ctrl = _instantiate_controller(prepared, parsed, raw, debug)
    if ctrl is None:
        return {
            "status": "stub",
            "error": "CalculationController не обнаружен или не удалось сконструировать.",
            "adapter_debug": debug,
            "prepared": {
                "d": prepared.d, "D": prepared.D, "p1": prepared.p1, "t1": prepared.t1, "dp": prepared.dp,
                "R": prepared.R, "Z": prepared.Z,
            },
            "used_values_si": {k: float(v) for k, v in parsed.items()},
        }

    # если НЕ нужно скипать физику — сначала пытаемся запустить «полный» сценарий
    if not skip_physics:
        if hasattr(ctrl, "run_calculations"):
            try:
                return ctrl.run_calculations()
            except TypeError:
                try:
                    return ctrl.run_calculations(prepared=prepared, parsed=parsed, raw=raw)
                except TypeError:
                    pass
        # пробуем run/dispatch/calculate/process (они могут внутри решать последовательность)
        for meth_name in ("run", "dispatch", "calculate", "process"):
            if hasattr(ctrl, meth_name):
                meth = getattr(ctrl, meth_name)
                try:
                    return meth(prepared=prepared, parsed=parsed, raw=raw)
                except TypeError:
                    for args in ((prepared, parsed, raw), (prepared, raw), (prepared,)):
                        try:
                            return meth(*args)
                        except TypeError:
                            continue

    # сюда попадаем, если физику надо скипнуть ИЛИ не нашлось подходящего «полного» метода
    status = {"status": "ok", "steps": []}

    # соберём вход для _create_orifice из ctrl.data (если есть) для диагностики
    inputs: Dict[str, Any] = {}
    if hasattr(ctrl, "data") and isinstance(ctrl.data, dict):
        fd = (ctrl.data.get("flowdata") or {})
        inputs = {
            "constrictor_params": fd.get("constrictor_params"),
            "environment_parameters": fd.get("environment_parameters"),
            "straightness_params": fd.get("straightness_params"),
        }
    debug["create_orifice_inputs"] = inputs

    # гарантированные вызовы
    def _call(name: str) -> None:
        if hasattr(ctrl, name):
            getattr(ctrl, name)()
            status["steps"].append(name)
        else:
            status["steps"].append(f"{name}:missing")

    _call("_create_orifice")
    _call("_calculate_flow")

    status.update(_collect_state(ctrl))
    status["adapter_debug"] = debug
    return status
