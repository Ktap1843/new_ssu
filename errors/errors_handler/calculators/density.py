# errors/errors_handler/calculators/density.py
from __future__ import annotations
from typing import Optional, Tuple
from logger_config import get_logger

from errors.errors_handler.calculators.base import BaseCalculator
from errors.errors_handler.calculators.converters import (
    build_component_from_payload,
    combine_chain_relative,
)
from errors.errors_handler.standards import STANDARD_REGISTRY
from errors.errors_handler.error_types import Result
from errors.errors_handler.geom_sum import geometric_sum

log = get_logger("DensityCalculator")


class DensityStCalculator(BaseCalculator):
    """
    Плотность (обычно ρ_st):
      - базовая часть считает RSS(main, additional) через BaseCalculator.compute();
      - затем добавляем вклад 2 преобразователей (converter1/2), в относительных %,
        с учётом k (табл. 7): linear->k=1, quadratic->k=2;
      - если error_type == AbsErr, нужен payload['value'] (ρ), чтобы перевести в относительные.
      - итог: total_rel = RSS( RSS(main, additional), δ_chain ).
    """

    # мягкая валидация
    def _validate_common(self) -> None:
        if "standard" not in self.payload:
            raise ValueError("Отсутствует обязательное поле: 'standard'")
        if "error_type" not in self.payload:
            raise ValueError("Отсутствует обязательное поле: 'error_type'")

        # По умолчанию 0.0, если не передали
        self.payload.setdefault("main", 0.0)
        self.payload.setdefault("additional", 0.0)

        # Для AbsErr обязателен value (ρ) для перевода в RelErr
        if self.payload["error_type"] == "AbsErr":
            if self.payload.get("value") is None:
                raise ValueError("Для 'AbsErr' требуется поле 'value' (значение ρ).")

    # контекст: (ρ, None)
    def extract_context(self) -> Tuple[Optional[float], Optional[float]]:
        value = self.payload.get("value", None)
        rho = float(value) if value is not None else None
        log.debug(f"Density context: rho={rho}")
        return rho, None

    def compute(self) -> Result:
        # базовый расчёт прибора (RSS(main, additional))
        base_res: Result = super().compute()

        # вклад цепочки преобразователей (до 2 шт.)
        opts = self.payload.get("options") or {}

        def _func(idx: int) -> str:
            return opts.get(f"conv{idx}_func", "linear")

        def _compl_keys(idx: int):
            # ВАЖНО: передаём только ComplError; Intr читается адаптером по converter{idx}IntrError
            return [f"converter{idx}ComplError"]

        comps = []
        for i in (1, 2):
            use_flag = opts.get(f"use_conv{i}")
            if use_flag is None:
                use_flag = (
                    self.payload.get(f"converter{i}IntrError") is not None
                    or self.payload.get(f"converter{i}ComplError") is not None
                    or bool(self.payload.get(f"converter{i}Enabled"))
                )
            if not use_flag:
                continue
            comp = build_component_from_payload(
                self.payload, idx=i, func=_func(i), compl_keys=_compl_keys(i)
            )
            comps.append(comp)

        total_rel = base_res.total_rel
        if comps:
            delta_chain = combine_chain_relative(comps)  # уже с k из табл.7
            total_rel = geometric_sum(total_rel, delta_chain)
            log.debug(f"Converters chain: delta_chain={delta_chain}% -> total_rel={total_rel}%")

        return Result(
            main_rel=base_res.main_rel,
            additional_rel=base_res.additional_rel,
            total_rel=total_rel,)
