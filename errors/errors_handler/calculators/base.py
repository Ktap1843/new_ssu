from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
from ..error_types import Result
from errors.errors_handler.geom_sum import geometric_sum
from errors.errors_handler.standards import STANDARD_REGISTRY

class BaseCalculator(ABC):
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload
        self._validate_common()

    def _validate_common(self):
        if "error_type" not in self.payload:
            raise ValueError("Отсутствует обязательное поле: 'error_type'")
        if "standard" not in self.payload:
            raise ValueError("Отсутствует обязательное поле: 'standard'")

        self.payload.setdefault("main", 0.0)
        self.payload.setdefault("additional", 0.0)

        if self.payload["main"] < 0 or self.payload["additional"] < 0:
            raise ValueError("Погрешности не могут быть отрицательными.")

    @abstractmethod
    def extract_context(self) -> tuple[Optional[float], Optional[float]]:
        ...

    def compute(self) -> Result:
        std_id = self.payload["standard"]
        std = STANDARD_REGISTRY.get(std_id)
        if not std:
            raise ValueError(f"Неизвестный стандарт: {std_id}")

        value, range_span = self.extract_context()
        by_formula = bool(self.payload.get("by_formula", False))
        err_type = self.payload["error_type"]  # общий флаг

        # --- MAIN ---
        if by_formula:
            if err_type != "RelErr":
                raise ValueError("В формульном режиме error_type должен быть 'RelErr', "
                                 "т.к. формула возвращает относительную погрешность (%).")
            formula = self.payload.get("formula") or {}
            qv = formula.get("quantityValue")
            const = float(formula.get("constValue", 0.0))
            slope = float(formula.get("slopeValue", 0.0))

            rmax = self._rmax_cache or _first(self.payload, "range_max", "p_max", "pressure_max")
            if rmax is None:
                raise ValueError("Для by_formula=True нужен верхний предел диапазона: range_max/p_max/pressure_max.")
            rmax = float(rmax)

            if qv in ("Pizm_Pmax", "Qizm_Qmax"):
                if rmax == 0:
                    raise ValueError("range_max не может быть 0 для 'Pizm_Pmax'/'Qizm_Qmax'.")
                main_rel = const + slope * (value / rmax)
            elif qv in ("Pmax_Pizm", "Qmax_Qizm"):
                if value == 0:
                    raise ValueError("value не может быть 0 для 'Pmax_Pizm'/'Qmax_Qizm'.")
                main_rel = const + slope * (rmax / value)
            else:
                raise ValueError("quantityValue: 'Pizm_Pmax'|'Qizm_Qmax'|'Pmax_Pizm'|'Qmax_Qizm'.")

            # унифицируем через стандарт (для RelErr вернётся как есть)
            main_rel = std.to_rel_percent("RelErr", main_rel, value=value, range_span=range_span)
        else:
            main_raw = float(self.payload["main"])
            main_rel = std.to_rel_percent(err_type, main_raw, value=value, range_span=range_span)

        # --- ADDITIONAL (всегда общий err_type) ---
        add_raw = float(self.payload.get("additional", 0.0))
        add_rel = std.to_rel_percent(err_type, add_raw, value=value, range_span=range_span)

        total_rel = geometric_sum(main_rel, add_rel)
        return Result(main_rel=main_rel, additional_rel=add_rel, total_rel=total_rel)

