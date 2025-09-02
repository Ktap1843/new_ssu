from typing import Optional, Dict, Any, List, Tuple
from logger_config import get_logger

from .error_types import Result
from .calculators import (CorrectorCalculator,
        TemperatureCalculator,
        PressureCalculator,
        DensityCalculator,
        CompositionCalculator)
from .calculators.base_converters import BaseConverter
from .standards import STANDARD_REGISTRY

log = get_logger("ErrorsAPI")


# --- 1. авто-детект типа по ключам верхнего уровня (можешь расширять) ---
def _guess_kind(state: Dict[str, Any]) -> Optional[str]:
    # Явный флаг лучше всего:
    k = state.get("kind") or state.get("type")
    if isinstance(k, str):
        return k.lower()

    # Авто-детект по ключам стейта:
    if "calcCorrectorProState" in state:
        return "corrector"
    if "calcTemperatureState" in state:
        return "temperature"
    if "calcPressureState" in state:
        return "pressure"
    if "calcDensityState" in state or "calcDensityProState" in state or "density" in state:
        return "density"
    if "calcCompositionState" in state or "composition" in state:
        return "composition"

    base_keys = {"error_type", "main", "additional"}
    if base_keys.issubset(state.keys()):
        return "corrector"

    return None


# --- 2. маленькие адаптеры state -> payload (минимум логики, только распаковка) ---
def _adapt_corrector(state: Dict[str, Any], standard_id: Optional[str]) -> Dict[str, Any]:
    # ожидаем вид:
    # state["calcCorrectorProState"]["intrError"/"complError"]...
    node = state.get("calcCorrectorProState", state)
    intr = node.get("intrError") or {}
    comp = node.get("complError") or {}

    def _take(err: Dict[str, Any]) -> Tuple[str, float]:
        et = err.get("errorTypeId")
        val = (err.get("value") or {}).get("real")
        return et, float(val) if val is not None else 0.0

    et_intr, v_intr = _take(intr)
    et_comp, v_comp = _take(comp)

    # проверим согласованность error_type — если разные, берём intr как «ведущий»
    err_type = et_intr or et_comp or "RelErr"

    payload = {
        "error_type": err_type,
        "main": v_intr,
        "additional": v_comp,
        "standard": standard_id or "611-2024",  # дефолтный флаг, при необходимости переопредели снаружи
        # CorrectorCalculator у тебя ожидает value → передаём 1.0 для RelErr, чтобы не падало;
        # для AbsErr/FidErr корректору не место — это ручит стандарт/другие калькуляторы.
        "value": state.get("value", 1.0),
    }
    log.debug(f"Corrector payload: {payload}")
    return payload


def _adapt_temperature(state: Dict[str, Any], standard_id: Optional[str]) -> Dict[str, Any]:
    node = state.get("calcTemperatureState", state)
    # допускаем разные ключи измеренного значения
    value = node.get("value") or node.get("t") or node.get("temperature")

    # диапазон для FidErr (если когда-нибудь понадобится)
    rmin = node.get("range_min")
    rmax = node.get("range_max")

    intr = node.get("intrError") or {}
    comp = node.get("complError") or {}

    def _val(err: Dict[str, Any]) -> Tuple[str, float]:
        et = err.get("errorTypeId")
        rv = (err.get("value") or {}).get("real")
        return et, float(rv) if rv is not None else 0.0

    et_intr, v_intr = _val(intr)
    et_comp, v_comp = _val(comp)
    err_type = et_intr or et_comp or "RelErr"

    payload = {
        "error_type": err_type,
        "main": v_intr,
        "additional": v_comp,
        "standard": standard_id or "611-2024",
        "value": float(value) if value is not None else None,
        "range_min": rmin,
        "range_max": rmax,
    }
    log.debug(f"Temperature payload: {payload}")
    return payload


def _adapt_pressure(state: Dict[str, Any], standard_id: Optional[str]) -> Dict[str, Any]:
    node = state.get("calcPressureState", state)

    value = node.get("value") or node.get("pressure") or node.get("P") or node.get("p")
    rmin = node.get("range_min") or node.get("pressure_min") or node.get("p_min")
    rmax = node.get("range_max") or node.get("pressure_max") or node.get("p_max")

    intr = node.get("intrError") or {}
    comp = node.get("complError") or {}

    def _val(err: Dict[str, Any]) -> Tuple[str, float]:
        et = err.get("errorTypeId")
        rv = (err.get("value") or {}).get("real")
        return et, float(rv) if rv is not None else 0.0

    et_intr, v_intr = _val(intr)
    et_comp, v_comp = _val(comp)
    err_type = et_intr or et_comp or "RelErr"

    payload = {
        "error_type": err_type,
        "main": v_intr,
        "additional": v_comp,
        "standard": standard_id or "611-2024",
        "value": float(value) if value is not None else None,
        "range_min": rmin,
        "range_max": rmax,
    }
    log.debug(f"Pressure payload: {payload}")
    return payload


def _adapt_density(state: Dict[str, Any], standard_id: Optional[str]) -> Dict[str, Any]:
    node = state.get("calcDensityState") or state.get("calcDensityProState") or state

    value = node.get("value") or node.get("rho") or node.get("density")
    rmin = node.get("range_min") or node.get("rho_min") or node.get("density_min")
    rmax = node.get("range_max") or node.get("rho_max") or node.get("density_max")

    intr = node.get("intrError") or {}
    comp = node.get("complError") or {}

    def _val(err: Dict[str, Any]) -> Tuple[str, float]:
        et = err.get("errorTypeId")
        rv = (err.get("value") or {}).get("real")
        return et, float(rv) if rv is not None else 0.0

    et_intr, v_intr = _val(intr)
    et_comp, v_comp = _val(comp)
    err_type = et_intr or et_comp or "RelErr"

    payload = {
        "error_type": err_type,
        "main": v_intr,
        "additional": v_comp,
        "standard": standard_id or "611-2024",
        "value": float(value) if value is not None else None,
        "range_min": rmin,
        "range_max": rmax,
    }
    log.debug(f"Density payload: {payload}")
    return payload


def _adapt_composition(state: Dict[str, Any], standard_id: Optional[str]) -> Dict[str, Any]:
    node = state.get("calcCompositionState") or state.get("composition") or state

    intr = node.get("intrError") or {}
    comp = node.get("complError") or {}

    def _val(err: Dict[str, Any]) -> Tuple[str, float]:
        et = err.get("errorTypeId")
        rv = (err.get("value") or {}).get("real")
        return et, float(rv) if rv is not None else 0.0

    et_intr, v_intr = _val(intr)
    et_comp, v_comp = _val(comp)
    err_type = et_intr or et_comp or "RelErr"

    payload = {
        "error_type": err_type,
        "main": v_intr,
        "additional": v_comp,
        "standard": standard_id or "611-2024",
        # пока контекст не нужен; если понадобится — добавим value/range
        "value": None,
        "range_min": None,
        "range_max": None,
    }
    log.debug(f"Composition payload: {payload}")
    return payload


# --- 3. реестр «тип -> (адаптер, калькулятор)» ---
REGISTRY = {
    "corrector": (_adapt_corrector, CorrectorCalculator),
    "temperature": (_adapt_temperature, TemperatureCalculator),
    "pressure": (_adapt_pressure, PressureCalculator),
    "density": (_adapt_density, DensityCalculator),
    "composition": (_adapt_composition, CompositionCalculator),
}


# --- 4. публичная функция: один вход для всех случаев ---
def compute(
    state: Dict[str, Any],
    *,
    kind: Optional[str] = None,
    standard_id: Optional[str] = None,
    converters: Optional[List[BaseConverter]] = None,
) -> Result:
    """
    Единая точка входа. Пример:
        res = compute(state_dict, kind="pressure", standard_id="611-2024")
    или
        res = compute(state_dict)  # с авто-детектом
    """
    # Проверка стандарта (если задан строкой)
    if standard_id is not None and standard_id not in STANDARD_REGISTRY:
        raise ValueError(f"Неизвестный стандарт: {standard_id}")

    # Детект типа
    k = (kind or _guess_kind(state) or "").lower()
    if k not in REGISTRY:
        raise ValueError(f"Не удалось распознать тип входных данных (kind='{k}'). "
                         f"Передай kind явно или добавь правила в _guess_kind().")

    adapt_fn, CalculatorCls = REGISTRY[k]

    # Сборка payload
    payload = adapt_fn(state, standard_id)

    # Инициализация калькулятора (конвертеры применятся внутри extract_context)
    if converters and hasattr(CalculatorCls, "__init__"):
        calc = CalculatorCls(payload, converters=converters)  # для pressure/density/temperature
    else:
        calc = CalculatorCls(payload)  # для corrector/composition

    # Под капотом BaseCalculator:
    # 1) подтянет стандарт
    # 2) переведёт все ошибки в относительные через standard.to_rel_percent(...)
    # 3) сложит геометрически
    result = calc.compute()

    log.info(f"[{k}] total_rel={result.total_rel:.6g}% "
             f"(main={result.main_rel:.6g}%, add={result.additional_rel:.6g}%)")
    return result
