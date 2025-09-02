from __future__ import annotations
import argparse
import json
import sys
from copy import deepcopy
from pprint import pprint
from typing import Dict, Any

from errors.handle import process_package
from errors.tests.payload_cases import CASES

def run_case(name: str, overrides_json: str | None = None, pretty: bool = False) -> Dict[str, Any]:
    if name not in CASES:
        raise SystemExit(f"Unknown case '{name}'. Available: {', '.join(CASES.keys())}")

    payload = CASES[name]() if callable(CASES[name]) else deepcopy(CASES[name])

    # при необходимости прокинем overrides для состава
    if overrides_json:
        try:
            overrides = json.loads(overrides_json)
            # куда прокинуть: в compositionErrorPackage.request.deltas_override_pp
            comp_pkg = payload.setdefault("data", {}).setdefault("compositionErrorPackage", {})
            req = comp_pkg.setdefault("request", {})
            req["deltas_override_pp"] = overrides
        except Exception as e:
            raise SystemExit(f"Bad --overrides-json: {e}")

    out = process_package(payload)

    if pretty:
        print("\n=== RESULT (short) ===")
        errs = out.get("data", {}).get("errorPackage", {}).get("errors", {})
        print("error_p     :", errs.get("error_p"))
        print("error_T     :", errs.get("error_T"))
        print("error_rho_st:", errs.get("error_rho_st"))
        comp_res = out.get("data", {}).get("compositionErrorPackage", {}).get("result", {})
        print("composition.delta_rho_1029:", comp_res.get("delta_rho_1029"))
        print("composition.delta_rho_1028:", comp_res.get("delta_rho_1028"))
        print("composition.policy         :", comp_res.get("policy"))
        print("diagnostics.router_status  :", out.get("diagnostics", {}).get("router_status"))

    return out

def main():
    ap = argparse.ArgumentParser(description="Run end-to-end error calculations with selectable tests cases.")
    ap.add_argument("--case", default="default", choices=sorted(CASES.keys()), help="Which payload case to run")
    ap.add_argument("--pretty", action="store_true", help="Pretty-print short result to console")
    ap.add_argument("--save-json", metavar="PATH", help="Save full result to JSON file")
    ap.add_argument("--overrides-json", metavar="JSON", help="Overrides for composition δx_i (pp), e.g. '{\"Ethane\":0.1}'")
    args = ap.parse_args()

    out = run_case(args.case, overrides_json=args.overrides_json, pretty=args.pretty)

    if args.save_json:
        with open(args.save_json, "w", encoding="utf-8") as f:
            json.dump(out, f, ensure_ascii=False, indent=2)
        print(f"\nSaved to: {args.save_json}")

if __name__ == "__main__":
    main()
