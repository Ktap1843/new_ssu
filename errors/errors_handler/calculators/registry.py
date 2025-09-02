from __future__ import annotations
from importlib import import_module
from typing import Any, Dict, Type


_CALC_CLASS_PATHS: Dict[str, str] = {
    "pressure": "errors.errors_handler.calculators.calc_pressure_abs:AbsPressureCalc",
    "temperature":  "errors.errors_handler.calculators.calc_temperature:TemperatureCalc",
    "density_st":   "errors.errors_handler.calculators.calc_density_st:DensityStCalc",
    "flow_primary": "errors.errors_handler.calculators.calc_flow_primary:PrimaryFlowCalc",
    "corrector":    "errors.errors_handler.calculators.calc_corrector:CorrectorCalc",
}


_CALC_CACHE: Dict[str, Any] = {}


def get_calculator_class(calc_id: str):
    if calc_id in _CALC_CACHE:
        return _CALC_CACHE[calc_id]

    path = _CALC_CLASS_PATHS.get(calc_id)
    if not path:
        raise KeyError(f"Unknown calculator id '{calc_id}'. "
                       f"Known: {', '.join(sorted(_CALC_CLASS_PATHS))}")

    try:
        module_path, class_name = path.split(":")
        mod = import_module(module_path)
        cls = getattr(mod, class_name)
    except Exception as e:
        raise ImportError(f"Failed to import '{path}' for '{calc_id}': {e}") from e

    _CALC_CACHE[calc_id] = cls
    return cls


def has(calc_id: str) -> bool:
    return calc_id in _CALC_CLASS_PATHS


def all_ids() -> list[str]:
    return list(_CALC_CLASS_PATHS.keys())
