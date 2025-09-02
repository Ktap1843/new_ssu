# file: controllers/calculation_adapter.py
"""
Адаптер вызова CalculationController:
- Создаёт контроллер с разными конструкторами (__init__).
- Совместимость с легаси: если контроллер ждёт data["flowdata"], собираем legacy-вид и пробуем снова.
- Порядок вызовов:
    1) run_calculations()
    2) run() / dispatch() / calculate() / process()
    3) Явная последовательность шагов по ctrlRequest.steps
       (по умолчанию: ["create_orifice", "calculate_flow"]).
- Возвращает расширенную диагностику adapter_debug при неудачах.
"""
from __future__ import annotations

import inspect
from typing import Any, Dict, Optional, Tuple

try:
    from controllers.calculation_controller import CalculationController  # type: ignore
    _HAVE_CALC_CTRL = True
except Exception:  # контроллер отсутствует в проекте
    CalculationController = None  # type: ignore
    _HAVE_CALC_CTRL = False


# ----------------- helpers -----------------

def _is_flowdata_keyerror(exc: BaseException) -> bool:
    """True, если это KeyError('flowdata')."""
    return isinstance(exc, KeyError) and bool(exc.args) and exc.args[0] == "flowdata"


def _build_legacy_data(raw: Dict[str, Any], parsed: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """
    Строит legacy-структуру {"flowdata": {...}} из нашего формата.
    d20/D20 — узлы с unit в мм (если нет в сыром JSON), p/dp/T — как в сыром, иначе значения SI.
    """
    len_props = (((raw.get("lenPackage") or {}).get("lenProperties")) or {})
    phys_props = (((raw.get("physPackage") or {}).get("physProperties")) or {})
    flow_props = (((raw.get("flowPackage") or {}).get("flowProperties")) or {})

    d20_node = len_props.get("d20") or {"real": float(prepared.d) * 1000.0, "unit": "mm"}
    D20_node = (len_props.get("D") or len_props.get("D20")) or {"real": float(prepared.D) * 1000.0, "unit": "mm"}

    p_node  = phys_props.get("p_abs") or float(prepared.p1)  # Па (число допустимо — _num_or_unit справится)
    dp_node = phys_props.get("dp")    or float(prepared.dp)  # Па
    T_node  = phys_props.get("T")     or float(prepared.t1)  # °C

    flowdata = {
        "constrictor_params": {"d20": d20_node, "D20": D20_node},
        "environment_parameters": {"p": p_node, "dp": dp_node, "T": T_node},
        "physical_properties": {"R": phys_props.get("R"), "Z": phys_props.get("Z")},
        "flow_properties": {"q_v": flow_props.get("q_v"), "q_st": flow_props.get("q_st")},
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
    """Обёртка конструктора (не глотаем исключения)."""
    return CalculationController(*args, **kwargs)  # type: ignore[misc]


def _instantiate_controller(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any], debug: Dict[str, Any]) -> Optional[Any]:
    """
    Создаёт экземпляр контроллера. При KeyError('flowdata') подменяем raw → legacy и повторяем попытки.
    В debug['construct_attempts'] сохраняем шаги и исключения.
    """
    if not _HAVE_CALC_CTRL or CalculationController is None:
        debug["construct_attempts"].append("CalculationController not importable")
        return None

    legacy = _build_legacy_data(raw, parsed, prepared)

    # 1) 0-арг
    try:
        debug["construct_attempts"].append("try: __init__()")
        return _try_construct((), {})
    except TypeError as e:
        debug["construct_attempts"].append(f"__init__() TypeError: {e}")
    except Exception as e:
        debug["construct_attempts"].append(f"__init__() Exception: {e}")
        if _is_flowdata_keyerror(e):
            try:
                debug["construct_attempts"].append("try: __init__(data=legacy)")
                return _try_construct((), {"data": legacy})
            except Exception as e2:
                debug["construct_attempts"].append(f"__init__(data=legacy) Exception: {e2}")

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
            if _is_flowdata_keyerror(e):
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
        (("raw", "prepared"), {}),
        (("prepared", "raw"), {}),
        (("prepared", "parsed", "raw"), {}),
        (("raw",), {}),
        (("prepared",), {}),
    ]
    valmap = {"raw": raw, "prepared": prepared, "parsed": parsed}
    for names, kwd in combos:
        args = tuple(valmap[n] for n in names)
        try:
            debug["construct_attempts"].append(f"try: __init__{names}")
            return _try_construct(args, kwd)
        except TypeError as e:
            debug["construct_attempts"].append(f"__init__{names} TypeError: {e}")
        except Exception as e:
            debug["construct_attempts"].append(f"__init__{names} Exception: {e}")
            if _is_flowdata_keyerror(e):
                args_legacy = tuple(legacy if n == "raw" else valmap[n] for n in names)
                try:
                    debug["construct_attempts"].append(f"try: __init__{names}_legacy(raw→legacy)")
                    return _try_construct(args_legacy, kwd)
                except Exception as e2:
                    debug["construct_attempts"].append(f"__init__{names}_legacy Exception: {e2}")

    return None


def _collect_state(ctrl: Any) -> Dict[str, Any]:
    """Пытаемся собрать итог из контроллера после ручных шагов."""
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


# ----------------- public API -----------------

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

    # 2) API-методы run/dispatch/calculate/process
    for meth_name in ("run", "dispatch", "calculate", "process"):
        if hasattr(ctrl, meth_name):
            meth = getattr(ctrl, meth_name)
            # именованные
            try:
                return meth(prepared=prepared, parsed=parsed, raw=raw)
            except TypeError:
                pass
            # позиционные
            for args in ((prepared, parsed, raw), (prepared, raw), (prepared,)):
                try:
                    return meth(*args)
                except TypeError:
                    continue

    # 3) Ручной сценарий: обязательно включаем _create_orifice и _calculate_flow
    steps = (raw.get("ctrlRequest") or {}).get("steps") or ["create_orifice", "calculate_flow"]
    status = {"status": "ok", "steps": []}

    def _call(name: str) -> None:
        if hasattr(ctrl, name):
            getattr(ctrl, name)()
            status["steps"].append(name)
        else:
            status["steps"].append(f"{name}:missing")

    # по запросу можно включить calculate_physics
    if "calculate_physics" in steps and hasattr(ctrl, "_calculate_physics"):
        _call("_calculate_physics")

    # ГАРАНТИРОВАННО вызываем _create_orifice и _calculate_flow, если они существуют
    _call("_create_orifice") if "_create_orifice" in dir(ctrl) else status["steps"].append("_create_orifice:missing")
    _call("_calculate_flow") if "_calculate_flow" in dir(ctrl) else status["steps"].append("_calculate_flow:missing")

    state = _collect_state(ctrl)
    status.update(state)
    status["adapter_debug"] = debug
    return status
