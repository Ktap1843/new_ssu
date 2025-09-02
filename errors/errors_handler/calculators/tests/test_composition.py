from __future__ import annotations
from math import isfinite, isclose

from errors.errors_handler.calculators.composition import CompositionCalculator
from errors.errors_handler.for_package import (
    compute_theta_for_component,   # оставлено, если пригодится для ручных проверок
    decide_policy_simple,
    build_upp_from_error,
    NormalizationPolicy,
    pp_to_fraction,
)


def _payload_base():
    return {
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
                "CarbonDioxide": {"complError": {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}}},
                "Ethane":        {"complError": {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}}},
                "Helium":        {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.015,"min":0.005},"unit":"percent"}}},
                "Hydrogen":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.005,"min":0.001},"unit":"percent"}}},
                "Methane":       {"complError": {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId":"RelErr","value":{"real":0,"unit":"percent"}}},
                "Nitrogen":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":1,"min":0.2},"unit":"percent"}}},
                "Oxygen":        {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.05,"min":0.005},"unit":"percent"}}},
                "Propane":       {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":2,"min":0.5},"unit":"percent"}}},
                "iButane":       {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.5,"min":0.1},"unit":"percent"}}},
                "iPentane":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.045,"min":0.018},"unit":"percent"}}},
                "nButane":       {"complError": {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId":"FidErr","value":{"real":0,"unit":"percent"}}},
                "nPentane":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.05,"min":0.01},"unit":"percent"}}},
            },
            "request": None
        }
    }


def approx(a: float, b: float, tol: float = 1e-12):
    assert isclose(a, b, rel_tol=0.0, abs_tol=tol), f"expected {b}, got {a}"


def test_A_all_zero_deltas():
    payload = _payload_base()
    calc = CompositionCalculator(payload)
    out = calc.compute(mode="auto", methane_name="Methane")

    # все δx_i = 0, ϑ = 0
    for k, v in out["delta_pp_by_component"].items():
        assert v == 0.0, f"{k}: expected 0.0 δx_i(pp), got {v}"
    for k, th in out["theta_by_component"].items():
        assert th == 0.0, f"{k}: expected 0.0 theta, got {th}"

    assert out["policy"] in ("general", "methane_by_diff")
    approx(out["delta_rho_1029"], out["delta_rho_1028"])

    print("✓ composition: all zeros -> OK")


def test_B_overrides_nonzero_targets():
    payload = _payload_base()
    calc = CompositionCalculator(payload)

    # дадим ненулевые δx_i (в ПРОЦЕНТНЫХ ПУНКТАХ) для пары компонентов
    overrides = {"Ethane": 0.10, "CarbonDioxide": 0.05}
    out = calc.compute(
        mode="auto", methane_name="Methane",
        deltas_override_pp=overrides,
    )

    theta = out["theta_by_component"]
    delta_pp = out["delta_pp_by_component"]

    # только эти два должны быть ненулевые
    assert delta_pp["Ethane"] == 0.10
    assert delta_pp["CarbonDioxide"] == 0.05
    for k, v in delta_pp.items():
        if k not in overrides:
            assert v == 0.0, f"{k}: expected 0.0 δx_i(pp), got {v}"

    assert isfinite(theta["Ethane"]) and theta["Ethane"] != 0.0
    assert isfinite(theta["CarbonDioxide"]) and theta["CarbonDioxide"] != 0.0
    assert theta["Helium"] == 0.0

    print("✓ composition: overrides + theta mapping -> OK")


def test_C_methane_by_difference_policy():
    """
    Режим 10.31 «метан по разности»:
    - варьируем Ethane на Δ=0.10 п.п.,
    - компенсация делается ТОЛЬКО метаном (CH4),
    - остальные компоненты фиксируются,
    - θ_Ethane ≠ 0, θ_CH4 не участвует в сумме 10.29.
    """
    payload = _payload_base()
    calc = CompositionCalculator(payload)

    overrides = {"Ethane": 0.10}  # Δx_i для этана в ПРОЦЕНТНЫХ ПУНКТАХ
    out = calc.compute(
        mode="methane_by_diff",     # ← фиксируем политику «по разности»
        methane_name="Methane",
        deltas_override_pp=overrides
    )

    assert out["policy"] == "methane_by_diff"

    delta_pp = out["delta_pp_by_component"]
    theta    = out["theta_by_component"]

    # В сумме 10.29 участвует только Ethane (CH4 исключается из targets)
    assert delta_pp["Ethane"] == 0.10
    for k, v in delta_pp.items():
        if k != "Ethane":
            assert v == 0.0, f"{k}: expected 0.0 δx_i(pp), got {v}"

    # θ для Ethane должен быть конечным и ненулевым
    assert isfinite(theta["Ethane"]) and theta["Ethane"] != 0.0

    # Инварианты нормировки: должны быть пусты
    assert not out["end_check_issues"], f"Нарушение инвариантов: {out['end_check_issues']}"

    # Доп. проверка инварианта: изменены только Ethane и Methane
    begin = payload["compositionErrorPackage"]["composition"]
    end   = out["final_comp_example"]
    changed = [k for k in begin if abs(begin[k] - end[k]) > 1e-12]
    assert set(changed) <= {"Ethane", "Methane"}, f"Лишние изменения при 'метан по разности': {changed}"

    print("✓ composition: methane_by_diff policy -> OK")


def test_D_general_policy_with_upp_and_target():
    """
    Режим 10.31 «general»:
    - часть компонентов отмечены как УПП (фиксируются),
    - варьируем CO2 на Δ=0.05 п.п.,
    - остальные свободные компоненты масштабируются (чтобы сумма = 100%),
    - θ_CO2 ≠ 0, УПП не меняются.
    """
    payload = _payload_base()
    calc = CompositionCalculator(payload)

    overrides = {"CarbonDioxide": 0.05}
    out = calc.compute(
        mode="general",              # ← фиксируем «general»
        methane_name="Methane",
        deltas_override_pp=overrides
    )

    assert out["policy"] == "general"

    delta_pp = out["delta_pp_by_component"]
    theta    = out["theta_by_component"]
    upp      = set(out["upp"])

    # Участвует только CO2
    assert delta_pp["CarbonDioxide"] == 0.05
    for k, v in delta_pp.items():
        if k != "CarbonDioxide":
            assert v == 0.0, f"{k}: expected 0.0 δx_i(pp), got {v}"

    assert isfinite(theta["CarbonDioxide"]) and theta["CarbonDioxide"] != 0.0

    # УПП действительно не изменились
    begin = payload["compositionErrorPackage"]["composition"]
    end   = out["final_comp_example"]
    for name in upp:
        assert abs(begin[name] - end[name]) <= 1e-12, f"UPP '{name}' должен быть фиксирован (general)."

    # Нормировка без нарушений
    assert not out["end_check_issues"], f"Нарушение инвариантов (general): {out['end_check_issues']}"

    print("✓ composition: general policy with UPP -> OK")


def _payload_large():
    comp = {
        # было "Methane": 83.0,
        # подняли на 4.38, чтобы сумма была ровно 100.0
        "Methane": 87.38,
        "Ethane": 5.2,
        "Propane": 2.1,
        "iButane": 0.6,
        "nButane": 0.7,
        "iPentane": 0.12,
        "nPentane": 0.13,
        "Hexane": 0.08,
        "Heptane": 0.04,

        "CarbonDioxide": 1.2,
        "Nitrogen": 1.1,
        "Oxygen": 0.05,
        "Hydrogen": 0.01,
        "Helium": 0.02,
        "Argon": 0.03,
        "Neon": 0.01,

        "Cyclohexane": 0.02,
        "Benzene": 0.03,
        "Toluene": 0.04,
        "Ethylene": 0.35,
        "Propylene": 0.35,
        "Butenes": 0.25,
        "Pentene": 0.16,
        "H2S": 0.03,
    }
    # Накидываем ошибки: многие — УПП, несколько — AbsErr=0 (как бы измерены точно)
    err = {
        "Methane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Ethane":        {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Propane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":1.5,"max":2.5},"unit":"percent"}}},
        "iButane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.3,"max":0.9},"unit":"percent"}}},
        "nButane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "iPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.05,"max":0.2},"unit":"percent"}}},
        "nPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.05,"max":0.2},"unit":"percent"}}},
        "Hexane":        {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Heptane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},

        "CarbonDioxide": {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Nitrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.2,"max":1.5},"unit":"percent"}}},
        "Oxygen":        {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.005,"max":0.08},"unit":"percent"}}},
        "Hydrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.0,"max":0.05},"unit":"percent"}}},
        "Helium":        {"intrError": {"errorTypeId": "UppErr", "range": {"range":{"min":0.0,"max":0.05},"unit":"percent"}}},
        "Argon":         {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Neon":          {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},

        "Cyclohexane":   {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Benzene":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Toluene":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Ethylene":      {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Propylene":     {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Butenes":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "Pentene":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
        "H2S":           {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.0, "unit": "percent"}}},
    }
    return {"compositionErrorPackage": {"composition": comp, "error_composition": err, "request": None}}



def test_E_large_methane_by_diff():
    payload = _payload_large()
    calc = CompositionCalculator(payload)

    overrides = {"Ethane": 0.12, "CarbonDioxide": 0.07}
    out = calc.compute(
        mode="methane_by_diff",
        methane_name="Methane",
        deltas_override_pp=overrides,
    )

    assert out["policy"] == "methane_by_diff"

    delta_pp = out["delta_pp_by_component"]
    theta    = out["theta_by_component"]

    # targets — только те, что задали overrides; метан исключён
    assert delta_pp["Ethane"] == 0.12
    assert delta_pp["CarbonDioxide"] == 0.07
    assert delta_pp.get("Methane", 0.0) == 0.0

    # Остальные — нули
    for k, v in delta_pp.items():
        if k not in overrides:
            assert v == 0.0, f"{k}: δx_i(pp) должен быть 0.0"

    # θ для целей — конечные и ненулевые
    from math import isclose
    assert theta["Ethane"] != 0.0 and isfinite(theta["Ethane"])
    assert theta["CarbonDioxide"] != 0.0 and isfinite(theta["CarbonDioxide"])

    # Проверим инварианты нормировки (методик-правила не нарушены)
    assert not out["end_check_issues"], f"Нарушение инвариантов: {out['end_check_issues']}"

    # Меняться должны только пары {target, Methane} — из-за двух целей список объединится
    begin = payload["compositionErrorPackage"]["composition"]
    end   = out["final_comp_example"]
    changed = [k for k in begin if abs(begin[k] - end[k]) > 1e-12]
    # допускаем изменения только у Ethane/CO2/Methane
    assert set(changed) <= {"Ethane", "CarbonDioxide", "Methane"}, f"Лишние изменения: {changed}"

    # Сумма ≈ 100
    from math import fsum, isclose as iscl
    assert iscl(fsum(end.values()), 100.0, rel_tol=0.0, abs_tol=1e-6)

    print("✓ composition: large methane_by_diff -> OK")


def test_F_large_general_with_upp():
    """
    Большой состав, режим 'general':
    - задаём Δx_i(pp) для одной цели (Propylene);
    - проверяем, что УПП не изменились;
    - θ цели ≠ 0; сумма ≈ 100.
    """
    payload = _payload_large()
    calc = CompositionCalculator(payload)

    overrides = {"Propylene": 0.09}
    out = calc.compute(
        mode="general",
        methane_name="Methane",
        deltas_override_pp=overrides,
    )

    assert out["policy"] == "general"

    delta_pp = out["delta_pp_by_component"]
    theta    = out["theta_by_component"]
    upp      = set(out["upp"])

    # Только Propylene имеет ненулевой δx_i
    assert delta_pp["Propylene"] == 0.09
    for k, v in delta_pp.items():
        if k != "Propylene":
            assert v == 0.0, f"{k}: δx_i(pp) должен быть 0.0"

    # θ цели — конечный и ненулевой
    assert isfinite(theta["Propylene"]) and theta["Propylene"] != 0.0

    # УПП не изменились
    begin = payload["compositionErrorPackage"]["composition"]
    end   = out["final_comp_example"]
    for name in upp:
        assert abs(begin[name] - end[name]) <= 1e-12, f"UPP '{name}' должен быть фиксирован (general)."

    # Сумма ≈ 100
    from math import fsum, isclose as iscl
    assert iscl(fsum(end.values()), 100.0, rel_tol=0.0, abs_tol=1e-6)

    # Инварианты нормировки соблюдены
    assert not out["end_check_issues"], f"Нарушение инвариантов (general): {out['end_check_issues']}"

    print("✓ composition: large general with UPP -> OK")


def run_all():
    test_A_all_zero_deltas()
    test_B_overrides_nonzero_targets()
    test_C_methane_by_difference_policy()
    test_D_general_policy_with_upp_and_target()
    test_E_large_methane_by_diff()
    test_F_large_general_with_upp()
print("\nALL COMPOSITION TESTS PASSED ✔")


if __name__ == "__main__":
    run_all()
