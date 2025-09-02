# errors/errors_handler/calculators/composition.py
from __future__ import annotations
from typing import Dict, Optional, Any, List
from logger_config import get_logger

from errors.errors_handler.for_package import (
    run_method10,
)

log = get_logger("CompositionCalculator")

__all__ = ["CompositionCalculator"]


class CompositionCalculator:
    """
    Обёртка над run_method10 (§10)
    Ожидает payload:
        {
          "compositionErrorPackage": {
            "composition": {... в процентах ...},
            "error_composition": {...},
            "request": ...
          }
        }
    """

    def __init__(self, payload: Dict[str, Any]) -> None:
        self.payload = payload

    def compute(
        self,
        *,
        mode: str = "auto",                 # "auto" | "general" | "methane_by_diff"
        methane_name: str = "Methane",
        # Параметры 10.28/10.29
        delta_rho_f: float = 0.08,
        theta_rho_T: float = -1.67e-3, delta_T: float = 0.20,
        theta_rho_p: float =  1.655e-2, delta_p: float = 0.15,
        # ВНИМАНИЕ: decimals=None — никаких округлений в примере фин. состава
        decimals: Optional[int] = None,
        fix_sum_to: Optional[str] = None,
        # Переопределение δx_i в п.п.
        deltas_override_pp: Optional[Dict[str, float]] = None,
    ) -> Dict[str, Any]:

        cep = (self.payload.get("compositionErrorPackage") or {})
        composition = cep.get("composition") or {}
        error_composition = cep.get("error_composition") or {}

        if not composition:
            raise ValueError("CompositionCalculator: 'compositionErrorPackage.composition' пуст.")

        res = run_method10(
            composition=composition,
            error_composition=error_composition,
            mode=mode,
            methane_name=methane_name,
            delta_rho_f=delta_rho_f,
            theta_rho_T=theta_rho_T, delta_T=delta_T,
            theta_rho_p=theta_rho_p, delta_p=delta_p,
            decimals=decimals,            # ← по умолчанию None, т.е. без округлений
            fix_sum_to=fix_sum_to,
            deltas_override_pp=deltas_override_pp,
        )

        names: List[str] = list(composition.keys())
        theta_by_component: Dict[str, float] = {n: 0.0 for n in names}
        for n, th in zip(res.get("targets", []), res.get("theta_vec", [])):
            theta_by_component[n] = float(th)

        delta_pp_used = res.get("delta_pp_used", {})
        delta_pp_by_component: Dict[str, float] = {n: 0.0 for n in names}
        for n, v in delta_pp_used.items():
            delta_pp_by_component[n] = float(v)

        out = {
            "policy": res.get("policy"),
            "upp": res.get("upp", []),
            "targets": res.get("targets", []),

            "theta_by_component": theta_by_component,
            "delta_pp_by_component": delta_pp_by_component,

            "delta_rho_1029": float(res.get("delta_rho_1029", 0.0)),
            "delta_rho_1028": float(res.get("delta_rho_1028", 0.0)),

            "begin_check_issues": res.get("begin_check_issues", []),
            "end_check_issues": res.get("end_check_issues", []),

            "final_comp_example": res.get("final_comp_example", composition),
        }

        log.debug(
            "Composition result: policy=%s, targets=%s, upp=%s",
            out["policy"], out["targets"], out["upp"]
        )
        return out


if __name__ == "__main__":
    payload = {
        "compositionErrorPackage": {
            "composition": {
                "CarbonDioxide": 2.5,
                "Ethane": 6,
                "Helium": 0.015,
                "Hydrogen": 0.005,
                "Methane": 87.535,
                "Nitrogen": 1,
                "Oxygen": 0.05,
                "Propane": 2,
                "iButane": 0.5,
                "iPentane": 0.045,
                "nButane": 0.3,
                "nPentane": 0.05
            },
            "error_composition": {
                "CarbonDioxide": {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.05, "unit": "percent"}}},
                "Ethane":        {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.10, "unit": "percent"}}},
                "Helium":        {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.005, "max": 0.015}}}},
                "Hydrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.001, "max": 0.005}}}},
                "Methane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.10, "unit": "percent"}}},
                "Nitrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.2, "max": 1.0}}}},
                "Oxygen":        {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.005, "max": 0.05}}}},
                "Propane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.5, "max": 2.0}}}},
                "iButane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.1, "max": 0.5}}}},
                "iPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.018, "max": 0.045}}}},
                "nButane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.05, "unit": "percent"}}},
                "nPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.01, "max": 0.05}}}}
            }
        }
    }
    calc = CompositionCalculator(payload)
    res = calc.compute(mode="auto", methane_name="Methane", decimals=None)
    print("policy:", res["policy"])
    print("targets:", res["targets"])
    print("issues end:", res["end_check_issues"])
