# file: controllers/calculation_adapter.py
"""
Адаптер вызова CalculationController:
- Создаёт контроллер с разными конструкторами (__init__).
- Совместимость: если нужен data["flowdata"], собираем legacy-вид.
  ВАЖНО: environment_parameters → ЧИСЛА в SI (p, dp — Па; T — °C),
  чтобы внутренняя математика контроллера не падала на узлах {real, unit}.
  d20/D20/straightness_params.D оставляем узлами {real, unit} (мм).
  physical_properties: Ro, mu → ЧИСЛА (mu в μPa·s), R/Z — как в исходнике.
  ПРОБРАСЫВАЕМ МАРКИ СТАЛЕЙ: d20_steel и D20_steel (строки) в constrictor_params.
- Если methodic == "other" — физику не трогаем, запускаем _create_orifice() → _calculate_flow().
- В result.adapter_debug возвращаем подробности конструирования и вход для _create_orifice().
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


# ----------------- helpers -----------------

def _is_keyerror(exc: BaseException, key: str) -> bool:
    return isinstance(exc, KeyError) and bool(exc.args) and exc.args[0] == key


def _node(val: float | int, unit: str) -> Dict[str, Any]:
    return {"real": float(val), "unit": unit}


def _extract_real(node: Any) -> Optional[float]:
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict):
        if "real" in node and isinstance(node["real"], (int, float)):
            return float(node["real"])
        if "value" in node and isinstance(node["value"], dict) and isinstance(node["value"].get("real"), (int, float)):
            return float(node["value"]["real"])
    return None


def _pick_or(node: Any, default: Dict[str, Any]) -> Dict[str, Any]:
    if isinstance(node, dict) and ("real" in node or ("value" in node and isinstance(node["value"], dict))):
        return node
    return default


def _to_micro_pa_s(mu: Any) -> Optional[float]:
    """Переводит узел/число вязкости в микропаскаль-секунды (μPa·s) числом."""
    if mu is None:
        return None
    if isinstance(mu, (int, float)):
        return float(mu)
    if isinstance(mu, dict):
        if "value" in mu and isinstance(mu["value"], dict):
            mu = mu["value"]
        val = _extract_real(mu)
        unit = str(mu.get("unit", "")).replace(" ", "").replace("·", "_").replace("/", "_").lower()
        if val is None:
            return None
        if unit in {"pa_s", "pa*s", "pa_s_"}:
            return val * 1_000_000.0
        if unit in {"mpa_s", "mpa*s"}:
            return val * 1_000.0
        if unit in {"upa_s", "µpa_s", "micro_pa_s", "micropa_s"}:
            return val
        return val
    return None


def _build_straightness_params(raw: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    len_pkg = (raw.get("lenPackage") or {})
    lp = (len_pkg.get("lenProperties") or {})
    req = (len_pkg.get("request") or {})

    D_node = lp.get("D") or lp.get("D20") or _node(float(getattr(prepared, "D", 0.0)) * 1000.0, "mm")

    params: Dict[str, Any] = {
        "D": D_node,
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
    """Формирует legacy-структуру для контроллера.
    environment_parameters → ЧИСЛА (SI), остальное как описано выше. Прокидываем d20_steel/D20_steel.
    """
    len_props = (((raw.get("lenPackage") or {}).get("lenProperties")) or {})
    phys_props = (((raw.get("physPackage") or {}).get("physProperties")) or {})
    flow_props = (((raw.get("flowPackage") or {}).get("flowProperties")) or {})

    # d20/D20 — узлы мм
    d20_node = _pick_or(len_props.get("d20"), _node(float(prepared.d) * 1000.0, "mm"))
    D20_src = len_props.get("D") or len_props.get("D20")
    D20_node = _pick_or(D20_src, _node(float(prepared.D) * 1000.0, "mm"))

    # steel grades (strings) with safe fallbacks
    steel_d = (
        len_props.get("d20_steel")
        or len_props.get("d_steel")
        or len_props.get("d_20_steel")
        or len_props.get("D20_steel")
        or "20"
    )
    steel_D = (
        len_props.get("D20_steel")
        or len_props.get("D_steel")
        or len_props.get("D_20_steel")
        or len_props.get("d20_steel")
        or steel_d
        or "20"
    )

    # environment_parameters → числа SI из prepared
    p_pa: float = float(prepared.p1)
    dp_pa: float = float(prepared.dp)
    t_c: float = float(prepared.t1)

    # физсвойства как числа
    ro_num = None
    if "Ro" in phys_props:
        ro_num = _extract_real(phys_props["Ro"]) or _extract_real(phys_props.get("rho"))
    elif "rho" in phys_props:
        ro_num = _extract_real(phys_props["rho"])  # альтернативное имя

    mu_num = None
    if "mu" in phys_props:
        mu_num = _to_micro_pa_s(phys_props["mu"])  # μPa·s

    physical_props: Dict[str, Any] = {
        "R": phys_props.get("R"),
        "Z": phys_props.get("Z"),
    }
    if ro_num is not None:
        physical_props["Ro"] = ro_num
    if mu_num is not None:
        physical_props["mu"] = mu_num

    flowdata = {
        "constrictor_params": {
            "d20": d20_node,
            "D20": D20_node,
            "d20_steel": steel_d,
            "D20_steel": steel_D,
        },
        # КЛЮЧЕВОЕ: только числа в SI
        "environment_parameters": {"p": p_pa, "dp": dp_pa, "T": t_c},
        "physical_properties": physical_props,
        "flow_properties": {"q_v": flow_props.get("q_v"), "q_st": flow_props.get("q_st")},
        "straightness_params": _build_straightness_params(raw, prepared),
    }

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
    if not _HAVE_CALC_CTRL or CalculationController is None:
        debug["construct_attempts"].append("CalculationController not importable")
        return None

    legacy = _build_legacy_data(raw, parsed, prepared)

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

    combos = [
        (("raw", "prepared"), {}),
        (("prepared", "raw"), {}),
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
                args_legacy = tuple((_build_legacy_data(raw, parsed, prepared) if n == "raw" else valmap[n]) for n in names)
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


# ----------------- public -----------------

def run_calculation(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    debug: Dict[str, Any] = {"construct_attempts": []}

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

    if not skip_physics:
        if hasattr(ctrl, "run_calculations"):
            try:
                return ctrl.run_calculations()
            except TypeError:
                try:
                    return ctrl.run_calculations(prepared=prepared, parsed=parsed, raw=raw)
                except TypeError:
                    pass
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

    status = {"status": "ok", "steps": []}

    inputs: Dict[str, Any] = {}
    if hasattr(ctrl, "data") and isinstance(ctrl.data, dict):
        fd = (ctrl.data.get("flowdata") or {})
        inputs = {
            "constrictor_params": fd.get("constrictor_params"),
            "environment_parameters": fd.get("environment_parameters"),
            "straightness_params": fd.get("straightness_params"),
            "physical_properties": fd.get("physical_properties"),
        }
    debug["create_orifice_inputs"] = inputs

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
