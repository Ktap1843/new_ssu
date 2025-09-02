from __future__ import annotations
from typing import Dict, Any, Callable, Optional, Tuple
from logger_config import get_logger

from .calculators.base import BaseCalculator
from .calculators.corrector import CorrectorCalculator
from .calculators.temperature import TemperatureCalculator
# from .calculators.pressure import PressureCalculator   # когда появится
# from .calculators.density import DensityCalculator     # когда появится
# from .calculators.composition import CompositionCalculator  # когда появится

log = get_logger("ErrorsAdapter")

CalculatorFactory = Callable[[Dict[str, Any]], BaseCalculator]

CALCULATOR_REGISTRY: dict[str, CalculatorFactory] = {
    "corrector": lambda payload: CorrectorCalculator(payload),
    "temperature": lambda playload: TemperatureCalculator(payload)
    # "pressure": lambda payload: PressureCalculator(payload),
    # "density": lambda payload: DensityCalculator(payload),
    # "composition": lambda payload: CompositionCalculator(payload),
}

# ————————————————— helpers —————————————————

def _normalize_standard_id(std: str) -> str:
    s = (std or "").strip().lower()
    aliases = {
        "gost 611-2013": "611-2013",
        "gost 611-2024": "611-2024",
        "rd-2025": "рд-2025",
        "рд2025": "рд-2025",
    }
    return aliases.get(s, std)

def _extract_value_from_state(state: Dict[str, Any]) -> Optional[float]:
    """
    Если где-то в состоянии есть измеренное значение x (для AbsErr/FidErr),
    достань его. Для corrector оно обычно не нужно, возвращаем None.
    Оставь как заготовку: под свои реальные поля просто поправишь.
    """
    v = state.get("measuredValue") or state.get("value")
    if isinstance(v, dict):
        v = v.get("real")
    if v is None:
        return None
    return float(v)

def _extract_range_span(block: Optional[Dict[str, Any]]) -> Optional[Tuple[float, float]]:
    """
    Принимает что-то вроде:
      {"min": a, "max": b} или {"range": {"min": a, "max": b}}
    Возвращает (min, max) или None.
    """
    if not block:
        return None
    rng = block.get("range") if isinstance(block, dict) else None
    if rng and "min" in rng and "max" in rng:
        return float(rng["min"]), float(rng["max"])
    if "min" in block and "max" in block:
        return float(block["min"]), float(block["max"])
    return None

def _pick_error_type(intr: Dict[str, Any], compl: Dict[str, Any]) -> str:
    return (intr.get("errorTypeId")
            or compl.get("errorTypeId")
            or "RelErr")

def _val_real(d: Optional[Dict[str, Any]]) -> float:
    if not d:
        return 0.0
    v = d.get("value") if isinstance(d, dict) else None
    if isinstance(v, dict):
        v = v.get("real")
    return float(v or 0.0)

# ————————————————— builders —————————————————

def build_payload_corrector(state: Dict[str, Any], standard_id: str) -> Dict[str, Any]:
    """
    state — это сам блок calcCorrectorProState (НЕ весь верхний JSON).
    Ожидаем ключи intrError/complError как в твоём примере.
    """
    intr = state.get("intrError") or {}
    compl = state.get("complError") or {}

    error_type = _pick_error_type(intr, compl)
    main = _val_real(intr)
    additional = _val_real(compl)

    payload = {
        "error_type": error_type,
        "main": main,
        "additional": additional,
        "standard": _normalize_standard_id(standard_id),
        # контекст:
        # для RelErr он не нужен; для AbsErr/FidErr — может понадобиться:
    }

    if error_type in ("AbsErr", "FidErr"):
        value = _extract_value_from_state(state)
        if value is not None:
            payload["value"] = value

        rng = intr.get("range") or compl.get("range")
        span = _extract_range_span(rng)
        if span:
            payload["range_min"], payload["range_max"] = span

    log.debug(f"Corrector payload: {payload}")
    return payload

# ————————————————— public API —————————————————

def compute_from_state(kind: str, state: Dict[str, Any], standard_id: str):
    """
    Универсальный вход для «сырого» блока состояния по типу узла.
    kind: "corrector" | "pressure" | "density" | "composition"
    state: сам под-блок (например, calcCorrectorProState)
    """
    builder_map = {
        "corrector": build_payload_corrector,
        # "pressure": build_payload_pressure,
        "density": build_payload_density,
        # "composition": build_payload_composition,
    }
    if kind not in builder_map:
        raise ValueError(f"Неизвестный kind: {kind}")

    payload = builder_map[kind](state, standard_id)
    calc = CALCULATOR_REGISTRY[kind](payload)
    return calc.compute()



#todo тут добавляем все СИ
def auto_dispatch_and_compute(root_json: Dict[str, Any], standard_id: str):
    """
    Принимает ВЕСЬ входной JSON и сам определяет, какой блок есть:
    - calcCorrectorProState
    - calcPressureProState
    - calcDensityProState
    - calcCompositionProState
    Возвращает (kind, result).
    """
    if "calcCorrectorProState" in root_json:
        res = compute_from_state("corrector", root_json["calcCorrectorProState"], standard_id)
        return "corrector", res

    # когда будут готовы — просто добавишь:
    # if "calcPressureProState" in root_json:
    #     res = compute_from_state("pressure", root_json["calcPressureProState"], standard_id)
    #     return "pressure", res
    #
    # if "calcDensityProState" in root_json:
    #     res = compute_from_state("density", root_json["calcDensityProState"], standard_id)
    #     return "density", res
    #
    # if "calcCompositionProState" in root_json:
    #     res = compute_from_state("composition", root_json["calcCompositionProState"], standard_id)
    #     return "composition", res

    raise ValueError("В корне JSON не найден ни один известный блок состояния.")
