from typing import Optional
from logger_config import get_logger
from errors.errors_handler.calculators.base import BaseCalculator
from errors.errors_handler.calculators.converters import build_component_from_payload, combine_chain_relative
from errors.errors_handler.standards import STANDARD_REGISTRY
from errors.errors_handler.error_types import Result
from errors.errors_handler.geom_sum import geometric_sum
from errors.errors_handler.calculators.converters_mixin import ConvertersMixin

log = get_logger("PressureCalculator")


#todo логика  Pизм / Pмакс  ; Pмакс / Pизм -- не реализовано, нужно сделать только для абсолютного давления?


def _first(payload: dict, *keys):
    for k in keys:
        v = payload.get(k)
        if v is not None:
            return v
    return None


class PressureCalculator(ConvertersMixin, BaseCalculator):
    def extract_context(self) -> tuple[Optional[float], Optional[float]]:
        raw_value = _first(self.payload, "value", "P", "p", "pressure")
        if raw_value is None:
            raise ValueError("Нужно одно из полей: 'value' | 'P' | 'p' | 'pressure'.")

        value = float(raw_value)

        converters = getattr(self, "converters", None)
        if converters:
            try:
                from .base_converters import ConverterPipeline
                log.debug("Запуск конвертеров для давления.")
                value = ConverterPipeline(converters).run(value, self.payload)
            except Exception as e:
                log.warning(f"Конвертеры отключены: {e}")

        rmin = _first(self.payload, "range_min", "p_min", "pressure_min")
        rmax = _first(self.payload, "range_max", "p_max", "pressure_max")
        range_span = abs(float(rmax) - float(rmin)) if (rmin is not None and rmax is not None) else None

        # Сохраним верхний предел — он нужен для формулы
        self._rmax_cache = float(rmax) if rmax is not None else None

        self.payload["value"] = value
        log.debug(f"Pressure context: value={value}, range_span={range_span}, rmax={self._rmax_cache}")
        return value, range_span

    def compute(self) -> Result:
        std_id = self.payload["standard"]
        std = STANDARD_REGISTRY.get(std_id)
        if not std:
            raise ValueError(f"Неизвестный стандарт: {std_id}")

        value, range_span = self.extract_context()
        by_formula = bool(self.payload.get("by_formula", False))
        err_type = self.payload.get("error_type", "RelErr")

        # --- MAIN ---
        if by_formula:
            formula = self.payload.get("formula") or {}
            qv = formula.get("quantityValue")
            try:
                const = float(formula.get("constValue", 0.0))
                slope = float(formula.get("slopeValue", 0.0))
            except Exception:
                raise ValueError("formula.constValue и formula.slopeValue должны быть числами.")

            rmax = self._rmax_cache or _first(self.payload, "range_max", "p_max", "pressure_max")
            if rmax is None:
                raise ValueError("Для by_formula=True укажи верхний предел диапазона: 'range_max'|'p_max'|'pressure_max'.")
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
                raise ValueError("quantityValue должен быть: 'Pizm_Pmax'|'Qizm_Qmax'|'Pmax_Pizm'|'Qmax_Qizm'.")

            # унифицируем через стандарт (для RelErr вернётся как есть)
            main_rel = std.to_rel_percent("RelErr", float(main_rel), value=value, range_span=range_span)
            log.debug(f"[by_formula] main_rel={main_rel}% (const={const}, slope={slope}, qv={qv})")
        else:
            main_raw = float(self.payload["main"])
            main_rel = std.to_rel_percent(err_type, main_raw, value=value, range_span=range_span)
            log.debug(f"[by_values] main_raw={main_raw} ({err_type}) -> main_rel={main_rel}%")

        # --- ADDITIONAL ---
        add_raw = float(self.payload.get("additional", 0.0))
        add_rel = std.to_rel_percent(err_type, add_raw, value=value, range_span=range_span)
        log.debug(f"additional_raw={add_raw} ({err_type}) -> add_rel={add_rel}%")

        # --- TOTAL ---
        total_rel = geometric_sum(main_rel, add_rel)

        # --- ВКЛАД ЦЕПОЧКИ ПРЕОБРАЗОВАТЕЛЕЙ ---
        opts = self.payload.get("options") or {}

        def _func(idx: int) -> str:
            return opts.get(f"conv{idx}_func", "linear")

        def _compl_keys(idx: int):
            keys = opts.get(f"conv{idx}_compl_keys")
            return list(keys) if keys else [f"converter{idx}ComplError"]

        comps = []
        for i in (1, 2, 3):
            use_flag = opts.get(f"use_conv{i}")
            if use_flag is None:
                use_flag = (self.payload.get(f"converter{i}IntrError") is not None) or bool(
                    self.payload.get(f"converter{i}Enabled")
                )
            if not use_flag:
                continue
            comps.append(
                build_component_from_payload(self.payload, idx=i, func=_func(i), compl_keys=_compl_keys(i))
            )

        if comps:
            delta_chain = combine_chain_relative(comps)
            total_rel = geometric_sum(total_rel, delta_chain)
            log.debug(f"Converters chain: delta_chain={delta_chain}% -> total_rel={total_rel}%")

        return Result(main_rel=main_rel, additional_rel=add_rel, total_rel=total_rel)
