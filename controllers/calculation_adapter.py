# file: controllers/calculation_adapter.py
"""
Адаптер вызова CalculationController:
- Создаёт контроллер с разными конструкторами (__init__).
- Совместимость: если нужен data["flowdata"], собираем legacy-вид (включая straightness_params) и пробуем снова.
- Порядок вызовов:
    1) run_calculations()
    2) run()/dispatch()/calculate()/process()
    3) Ручные шаги (по умолчанию: ["create_orifice","calculate_flow"]) — гарантированно вызываем _create_orifice() и _calculate_flow().
- Возвращает расширенную диагностику adapter_debug.construct_attempts.
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


def _is_keyerror(exc: BaseException, key: str) -> bool:
    return isinstance(exc, KeyError) and bool(exc.args) and exc.args[0] == key


def _build_straightness_params(raw: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """Собираем flowdata.straightness_params из lenPackage.* с дефолтами.
    Почему так: CalculationController запрашивает этот блок ещё в __init__.
    """
    len_pkg = (raw.get("lenPackage") or {})
    lp = (len_pkg.get("lenProperties") or {})
    req = (len_pkg.get("request") or {})

    # Из lenProperties переносим как есть, если есть
    params: Dict[str, Any] = {
        "D": lp.get("D") or lp.get("D20") or {"real": float(getattr(prepared, "D", 0.0)) * 1000.0, "unit": "mm"},
        "DN": lp.get("DN"),
        "measSection": lp.get("measSection"),
        "localResistance": lp.get("localResistance"),
        "lensCompliance": lp.get("lensCompliance"),
    }
    # Флаги из lenPackage.request
    params["calc"] = bool(req.get("calc", False))
    params["check"] = bool(req.get("check", False))

    # Минимальные тех.поля, если контроллер их ждёт (безопасные дефолты)
    # при необходимости расширим: H/E/R/a/h/mu/p/peaLocation/r/usingCorrectionFactor/...
    params.setdefault("usingCorrectionFactor", True)
    params.setdefault("DLessThan1p", True)

    return params


def _build_legacy_data(raw: Dict[str, Any], parsed: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """Строит legacy-структуру {"flowdata": {...}} из нашего формата."""
    len_props = (((raw.get("lenPackage") or {}).get("lenProperties")) or {})
    phys_props = (((raw.get("physPackage") or {}).get("physProperties")) or {})
    flow_props = (((raw.get("flowPackage") or {}).get("flowProperties")) or {})

    d20_node = len_props.get("d20") or {"real": float(prepared.d) * 1000.0, "unit": "mm"}
    D20_node = (len_props.get("D") or len_props.get("D20")) or {"real": float(prepared.D) * 1000.0, "unit": "mm"}

    p_node  = phys_props.get("p_abs") or float(prepared.p1)  # Па
    dp_node = phys_props.get("dp")    or float(prepared.dp)  # Па
    T_node  = phys_props.get("T")     or float(prepared.t1)  # °C

    flowdata = {
        "constrictor_params": {"d20": d20_node, "D20": D20_node},
        "environment_parameters": {"p": p_node, "dp": dp_node, "T": T_node},
        "physical_properties": {"R": phys_props.get("R"), "Z": phys_props.get("Z")},
        "flow_properties": {"q_v": flow_props.get("q_v"), "q_st": flow_props.get("q_st")},
        # КРИТИЧНО: добавили straightness_params (раньше из-за отсутствия падало)
        "straightness_params": _build_straightness_params(raw, prepared),
    }
    return {"flowdata": flowdata}


def _build_init_kwargs(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Подбираем kwargs под сигнатуру __init__ (игнорируя self)."""
    if CalculationController is None:
        return {}
    try:
        sig = inspect.signature(CalculationController.__init__)
    except Exception:
        return {}

    candidates = {
        # сырой вход
        "data": raw, "raw": raw, "input": raw, "input_data": raw, "request": raw,
        # подготовленные параметры
        "prepared": prepared, "prepared_params": prepared, "prepared_data": prepared, "params": prepared,
        # распарсенные SI-значения
        "parsed": parsed, "values": parsed, "values_si": parsed, "parsed_values": parsed,
        # общий контекст
        "context": {"prepared": prepared, "parsed": parsed, "raw": raw},
    }

    kwargs: Dict[str, Any] = {}
    for name in sig.parameters.keys():
        if name == "self":
            continue
        if name in candidates:
            kwargs[name] = candidates[name]
    return kwargs


def _try_construct(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    return CalculationController(*args, **kwargs)  # type: ignore[misc]


def _instantiate_controller(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any], debug: Dict[str, Any]) -> Optional[Any]:
    """Создаёт экземпляр; на KeyError('flowdata'|'straightness_params') подменяем raw → legacy."""
    if not _HAVE_CALC_CTRL or CalculationController is None:
        debug["construct_attempts"].append("CalculationController not importable")
        return None

    legacy = _build_legacy_data(raw, parsed, prepared)

    # 1) __init__() без аргументов
    try:
        debug["construct_attempts"].append("try: __init__()")
        return _try_construct((), {})
    except TypeError as e:
        debug["construct_attempts"].append(f"__init__() TypeError: {e}")
    except Exception as e:
        debug["construct_attempts"].append(f"__init__() Exception: {e}")
        if _is_keyerror(e, "flowdata") or _is_keyerror(e, "straightness_params"):
            try:
                debug["construct_attempts"].append("try: __init__(data=legacy)")
                return _try_construct((), {"data": legacy, "prepared_params": prepared})
            except Exception as e2:
                debug["construct_attempts"].append(f"__init__(data=legacy) Exception: {e2}")

    # 2) kwargs по сигнатуре
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

    # 3) позиционные сигнатуры
    combos = [
        (("raw", "prepared"), {}),              # (data, prepared_params)
        (("prepared", "raw"), {}),              # (prepared_params, data) — на всякий
        (("raw",), {}),                         # (data,)
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
                args_legacy = tuple(( _build_legacy_data(raw, parsed, prepared) if n == "raw" else valmap[n]) for n in names)
                try:
                    debug["construct_attempts"].append(f"try: __init__{names}_legacy(raw→legacy)")
                    # если позиционные — порядок должен быть (data, prepared_params)
                    if names == ("prepared", "raw"):
                        # переставим в ожидаемый (data, prepared_params)
                        args_legacy = (args_legacy[1], args_legacy[0])
                    return _try_construct(args_legacy, kwd)
                except Exception as e2:
                    debug["construct_attempts"].append(f"__init__{names}_legacy Exception: {e2}")

    return None


def _collect_state(ctrl: Any) -> Dict[str, Any]:
    """Собираем возможные результаты из контроллера (если атрибуты есть)."""
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


def run_calculation(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    debug: Dict[str, Any] = {"construct_attempts": []}

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

    # 1) Полный сценарий, если есть run_calculations()
    if hasattr(ctrl, "run_calculations"):
        try:
            return ctrl.run_calculations()
        except TypeError:
            try:
                return ctrl.run_calculations(prepared=prepared, parsed=parsed, raw=raw)
            except TypeError:
                pass

    # 2) API-методы
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

    # 3) Ручной сценарий: гарантированно вызываем _create_orifice → _calculate_flow
    steps = (raw.get("ctrlRequest") or {}).get("steps") or ["create_orifice", "calculate_flow"]
    status = {"status": "ok", "steps": []}

    def _call(name: str) -> None:
        if hasattr(ctrl, name):
            getattr(ctrl, name)()
            status["steps"].append(name)
        else:
            status["steps"].append(f"{name}:missing")

    if "calculate_physics" in steps and hasattr(ctrl, "_calculate_physics"):
        _call("_calculate_physics")

    _call("_create_orifice")  # важно: этот шаг обязателен
    _call("_calculate_flow")  # и этот тоже

    status.update(_collect_state(ctrl))
    status["adapter_debug"] = debug
    return status
