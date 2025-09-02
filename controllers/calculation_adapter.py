# file: controllers/calculation_adapter.py
"""
Адаптер вызова CalculationController:
- Создаёт контроллер с разными конструкторами (__init__).
- Совместимость: если контроллер ждёт data["flowdata"], строим legacy-вид из raw/prepared/parsed.
- Ищем метод run/dispatch/calculate/process и пробуем разные сигнатуры.
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

def _is_flowdata_keyerror(exc: BaseException) -> bool:
    """True, если это KeyError('flowdata')."""
    return isinstance(exc, KeyError) and bool(exc.args) and exc.args[0] == "flowdata"


def _build_legacy_data(raw: Dict[str, Any], parsed: Dict[str, Any], prepared: Any) -> Dict[str, Any]:
    """
    Строит legacy-структуру {"flowdata": {...}} из нашего формата.
    Значения берём из raw, а при отсутствии — из prepared/parsed (в SI).
    """
    len_props = (((raw.get("lenPackage") or {}).get("lenProperties")) or {})
    phys_props = (((raw.get("physPackage") or {}).get("physProperties")) or {})
    flow_props = (((raw.get("flowPackage") or {}).get("flowProperties")) or {})

    # Диаметры: если нет узлов с unit в исходнике — подставляем из prepared в мм.
    d20_node = len_props.get("d20") or {"real": float(prepared.d) * 1000.0, "unit": "mm"}
    D20_node = (len_props.get("D") or len_props.get("D20")) or {"real": float(prepared.D) * 1000.0, "unit": "mm"}

    # Давления/температуры: оставляем «как есть» из исходника, иначе подставляем значения SI
    p_node  = phys_props.get("p_abs") or float(prepared.p1)       # Па
    dp_node = phys_props.get("dp")    or float(prepared.dp)       # Па
    T_node  = phys_props.get("T")     or float(prepared.t1)       # °C

    flowdata = {
        "constrictor_params": {
            "d20": d20_node,
            "D20": D20_node,
        },
        "environment_parameters": {
            "p": p_node,
            "dp": dp_node,
            "T": T_node,
        },
        "physical_properties": {
            "R": phys_props.get("R"),
            "Z": phys_props.get("Z"),
        },
        "flow_properties": {
            "q_v": flow_props.get("q_v"),
            "q_st": flow_props.get("q_st"),
        },
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
    for name, param in sig.parameters.items():
        if name == "self":
            continue
        if name in candidates:
            kwargs[name] = candidates[name]
    return kwargs


def _try_construct(args: Tuple[Any, ...], kwargs: Dict[str, Any]) -> Any:
    """Вспомогательный конструктор с пробросом KeyError наверх."""
    return CalculationController(*args, **kwargs)  # type: ignore[misc]


def _instantiate_controller(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Optional[Any]:
    """Создаёт экземпляр контроллера: 0-арг, kwargs, популярные позиционные; при KeyError('flowdata') подменяем raw→legacy."""
    if not _HAVE_CALC_CTRL or CalculationController is None:
        return None

    legacy = _build_legacy_data(raw, parsed, prepared)

    # 1) 0-арг
    try:
        return _try_construct((), {})
    except TypeError:
        pass
    except Exception as e:
        if _is_flowdata_keyerror(e):
            # Пробуем передать legacy как data через kwargs
            try:
                return _try_construct((), {"data": legacy})
            except Exception:
                pass

    # 2) kwargs по сигнатуре
    kw = _build_init_kwargs(prepared, parsed, raw)
    if kw:
        try:
            return _try_construct((), kw)
        except TypeError:
            pass
        except Exception as e:
            if _is_flowdata_keyerror(e):
                # Подменяем все возможные ключи «сырого входа» на legacy
                for key in ("data", "raw", "input", "input_data", "request"):
                    if key in kw:
                        kw[key] = legacy
                try:
                    return _try_construct((), kw)
                except Exception:
                    pass

    # 3) частые позиционные подписи (и их legacy-варианты)
    combos = [
        (("raw", "prepared"), {}),              # (data, prepared_params)
        (("prepared", "raw"), {}),              # (prepared_params, data)
        (("prepared", "parsed", "raw"), {}),    # (prepared, parsed, raw)
        (("raw",), {}),                         # (data,)
        (("prepared",), {}),                    # (prepared_params,)
    ]
    valmap = {"raw": raw, "prepared": prepared, "parsed": parsed}
    for names, kwd in combos:
        args = tuple(valmap[n] for n in names)
        try:
            return _try_construct(args, kwd)
        except TypeError:
            continue
        except Exception as e:
            if _is_flowdata_keyerror(e):
                # Подменяем raw на legacy и пробуем ещё раз
                args_legacy = tuple(legacy if n == "raw" else valmap[n] for n in names)
                try:
                    return _try_construct(args_legacy, kwd)
                except Exception:
                    continue

    return None


# ----------------- public API -----------------

def run_calculation(prepared: Any, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    ctrl = _instantiate_controller(prepared, parsed, raw)
    if ctrl is None:
        return {
            "status": "stub",
            "error": "CalculationController не обнаружен или не удалось сконструировать.",
            "prepared": {
                "d": prepared.d, "D": prepared.D, "p1": prepared.p1, "t1": prepared.t1, "dp": prepared.dp,
                "R": prepared.R, "Z": prepared.Z,
            },
            "used_values_si": {k: float(v) for k, v in parsed.items()},
        }

    # поддержка нескольких API-методов
    for meth_name in ("run", "dispatch", "calculate", "process"):
        if hasattr(ctrl, meth_name):
            meth = getattr(ctrl, meth_name)
            # именованные:
            try:
                return meth(prepared=prepared, parsed=parsed, raw=raw)
            except TypeError:
                pass
            # позиционные:
            for args in ((prepared, parsed, raw), (prepared, raw), (prepared,)):
                try:
                    return meth(*args)
                except TypeError:
                    continue

    return {"status": "error", "error": "Метод CalculationController не найден (run/dispatch/calculate/process)."}
