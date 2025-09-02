from typing import Optional
from logger_config import get_logger
from errors.errors_handler.calculators.base import BaseCalculator
from errors.errors_handler.calculators.converters import (
    build_component_from_payload,
    combine_chain_relative,
)
from ..error_types import Result
from ..standards import STANDARD_REGISTRY
from ..geom_sum import geometric_sum

log = get_logger("TemperatureCalculator")


class TemperatureCalculator(BaseCalculator):
    def _validate_common(self):
        by_formula = bool(self.payload.get("by_formula", False))

        # Базовые обязательные поля
        for k in ("standard", "value", "error_type"):
            if k not in self.payload:
                raise ValueError(f"Отсутствует обязательное поле: '{k}'")

        value = self.payload["value"]
        if value is None:
            raise ValueError("Для TemperatureCalculator требуется 'value' (в К).")
        try:
            float(value)
        except Exception:
            raise ValueError("'value' должен быть числом (в К).")

        if not by_formula:
            # базовая проверка main/additional >= 0
            if "main" not in self.payload:
                self.payload["main"] = 0.0
            if "additional" not in self.payload:
                self.payload["additional"] = 0.0
            return

        # --- режим formula ---
        formula = self.payload.get("formula")
        if not isinstance(formula, dict):
            raise ValueError("Для by_formula=True требуется объект 'formula'.")
        if formula.get("quantityValue") != "t_abs":
            raise ValueError("Поддерживается только formula.quantityValue='t_abs' для температуры.")

        for k in ("constValue", "slopeValue"):
            if k not in formula:
                raise ValueError(f"В formula отсутствует '{k}'.")
            try:
                float(formula[k])
            except Exception:
                raise ValueError(f"formula['{k}'] должен быть числом.")

        if "additional" not in self.payload:
            self.payload["additional"] = 0.0

    # ----- КОНТЕКСТ -----
    def extract_context(self):
        value = float(self.payload["value"])
        rmin = self.payload.get("range_min")
        rmax = self.payload.get("range_max")
        range_span = None
        if rmin is not None and rmax is not None:
            range_span = float(rmax) - float(rmin)
        log.debug(f"Temperature context: value={value} K, range_span={range_span}")
        return value, range_span

    # ----- расчет ΔT_abs по формуле -----
    def _main_abs_by_formula(self, value_K: float) -> float:
        form = self.payload["formula"]
        const_val = float(form["constValue"])
        slope_val = float(form["slopeValue"])
        t_c = value_K - 273.15
        delta_abs_K = const_val + slope_val * abs(t_c)
        if delta_abs_K < 0:
            log.warning("Рассчитана отрицательная ΔT_abs, берём модуль.")
            delta_abs_K = abs(delta_abs_K)
        return delta_abs_K

    # ----- расшифровка преобразователей -----
    def converters_breakdown(self):
        opts = (self.payload.get("options") or {})

        def _func(idx: int) -> str:
            return opts.get(f"conv{idx}_func", "linear")

        def _compl_keys(idx: int):
            return [f"converter{idx}ComplError"]

        comps = []
        used = []
        for i in (1, 2, 3):
            use_flag = (
                self.payload.get(f"converter{i}IntrError") is not None
                or self.payload.get(f"converter{i}ComplError") is not None
                or bool(self.payload.get(f"converter{i}Enabled"))
            )
            if not use_flag:
                continue
            comp = build_component_from_payload(self.payload, idx=i, func=_func(i), compl_keys=_compl_keys(i))
            comps.append(comp)
            used.append((i, comp.func))

        if not comps:
            return {"delta_chain_percent": 0.0, "components": [], "components_with_k": []}

        components = []
        for (idx, _func_name), comp in zip(used, comps):
            components.append({
                "idx": idx,
                "func": comp.func,
                "delta_component_percent": comp.spec.total_rel_percent(),
            })

        sens = []
        for comp in comps:
            if comp.func == "quadratic":
                sens.append(2)
            else:
                sens.append(1)

        contrib = [
            {"idx": idx, "applied_k": k, "contribution_percent": k * comp.spec.total_rel_percent()}
            for (idx, _), k, comp in zip(used, sens, comps)
        ]

        delta_chain = combine_chain_relative(comps)
        return {
            "delta_chain_percent": delta_chain,
            "components": components,
            "components_with_k": contrib,
        }

    # ----- ОСНОВНОЙ РАСЧЁТ -----
    def compute(self) -> Result:
        std_id = self.payload["standard"]
        std = STANDARD_REGISTRY.get(std_id)
        if not std:
            raise ValueError(f"Неизвестный стандарт: {std_id}")

        value, range_span = self.extract_context()
        by_formula = bool(self.payload.get("by_formula", False))

        # ---- MAIN ----
        if by_formula:
            main_abs = self._main_abs_by_formula(value)
            main_rel = std.to_rel_percent("AbsErr", main_abs, value=value, range_span=range_span)
            log.debug(f"[by_formula] main_abs={main_abs} K -> main_rel={main_rel}%")
        else:
            err_type = self.payload["error_type"]
            main_raw = float(self.payload.get("main", 0.0) or 0.0)
            main_rel = std.to_rel_percent(err_type, main_raw, value=value, range_span=range_span)
            log.debug(f"[by_values] main_raw={main_raw} ({err_type}) -> main_rel={main_rel}%")

        # ---- ADDITIONAL ----
        add_raw = float(self.payload.get("additional", 0.0) or 0.0)
        add_type = self.payload["error_type"]
        add_rel = std.to_rel_percent(add_type, add_raw, value=value, range_span=range_span)
        log.debug(f"additional_raw={add_raw} ({add_type}) -> add_rel={add_rel}%")

        total_rel = geometric_sum(main_rel, add_rel)

        # ---- CONVERTERS (до 3 шт.) ----
        comps = []
        opts = self.payload.get("options") or {}

        def _func(idx: int) -> str:
            return opts.get(f"conv{idx}_func", "linear")

        def _compl_keys(idx: int):
            return [f"converter{idx}ComplError"]

        for i in (1, 2, 3):
            use_flag = (
                self.payload.get(f"converter{i}IntrError") is not None
                or self.payload.get(f"converter{i}ComplError") is not None
                or bool(self.payload.get(f"converter{i}Enabled"))
            )
            if not use_flag:
                continue
            comp = build_component_from_payload(self.payload, idx=i, func=_func(i), compl_keys=_compl_keys(i))
            comps.append(comp)

        if comps:
            delta_chain = combine_chain_relative(comps)
            total_rel = geometric_sum(total_rel, delta_chain)
            log.debug(f"Converters chain: delta_chain={delta_chain}% -> total_rel={total_rel}%")

        return Result(main_rel=main_rel, additional_rel=add_rel, total_rel=total_rel)
