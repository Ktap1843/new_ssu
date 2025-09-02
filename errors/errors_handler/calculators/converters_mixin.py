from __future__ import annotations

from typing import Any, Dict, List
from errors.errors_handler.geom_sum import geometric_sum
from errors.errors_handler.error_types import Result
from errors.errors_handler.calculators.converters import build_component_from_payload, combine_chain_relative

class ConvertersMixin:
    """
    Обёртка, которая добавляет к total_rel ещё и вклад цепочки преобразователей.
    Ничего не знает про конкретный калькулятор — ожидает только self.payload.
    Вызов цепочки — после родительского compute().
    """
    # --- публичная точка для вызова вручную при желании ---
    def compute_chain_delta_percent(self) -> float:
        comps = self._build_converter_chain()
        return combine_chain_relative(comps) if comps else 0.0

    # --- публичная расшифровка (кому нужно показать вклад по компонентам) ---
    def converters_breakdown(self) -> Dict[str, Any]:
        comps = self._build_converter_chain()
        if not comps:
            return {"delta_chain_percent": 0.0, "components": []}
        parts = [{"index": i + 1, "func": c.func, "delta_percent": c.spec.total_rel_percent()}
                 for i, c in enumerate(comps)]
        return {
            "delta_chain_percent": combine_chain_relative(comps),
            "components": parts
        }

    def compute(self):
        parent: Result = super().compute()  # твой BaseCalculator.compute(): RSS(main, additional)
        delta_chain = self.compute_chain_delta_percent()
        total_with_chain = geometric_sum(parent.total_rel, delta_chain)
        return Result(
            main_rel=parent.main_rel,
            additional_rel=parent.additional_rel,
            total_rel=total_with_chain
        )


    def _opts(self) -> Dict[str, Any]:
        return (self.payload.get("options") or {})

    def _use_conv(self, idx: int) -> bool:
        """Определяем включён ли i‑й преобразователь."""
        opts = self._opts()
        opt_key = f"use_conv{idx}"
        if opt_key in opts and opts[opt_key] is not None:
            return bool(opts[opt_key])
        return (self.payload.get(f"converter{idx}IntrError") is not None) or bool(self.payload.get(f"converter{idx}Enabled"))

    def _func_for(self, idx: int) -> str:
        return self._opts().get(f"conv{idx}_func", "linear")

    def _compl_keys_for(self, idx: int):
        keys = self._opts().get(f"conv{idx}_compl_keys")
        if keys:
            return list(keys)
        return [f"converter{idx}ComplError"]

    def _build_converter_chain(self):
        comps: List = []
        for idx in (1, 2, 3):  # поддержим до трёх на будущее
            if not self._use_conv(idx):
                continue
            comp = build_component_from_payload(
                self.payload,
                idx=idx,
                func=self._func_for(idx),
                compl_keys=self._compl_keys_for(idx),
            )
            comps.append(comp)
        return comps