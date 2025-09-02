# errors/errors_handler/calculators/tests/test_pressure.py
from math import isclose, sqrt
from errors.errors_handler.calculators.pressure_abs import PressureCalculator

def approx(a, b, tol=1e-9):
    assert isclose(a, b, rel_tol=0, abs_tol=tol), f"expected {b}, got {a}"

def test_by_values_with_converters():
    payload = {
        "error_type": "RelErr",
        "main": 0.5,
        "additional": 0.2,
        "standard": "рд-2025",
        "value": 2_100_000.0,

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.1, "unit": "percent"}},
        "converter1ComplError": {"errorTypeId": "RelErr", "value": {"real": 0.05, "unit": "percent"}},
        "converter1Enabled": True,
    }
    calc = PressureCalculator(payload)
    res = calc.compute()

    parent = sqrt(0.5**2 + 0.2**2)
    chain  = sqrt(0.1**2 + 0.05**2)
    total  = sqrt(parent**2 + chain**2)
    approx(res.total_rel, total)
    print("✓ by_values + converters -> total =", res.total_rel)

def test_by_formula_two_converters_add0():
    """
    by_formula=True, additional=0.0 (по умолчанию):
      main_rel = 0.4 + 0.2*(2.1/2.5) = 0.568%
      parent = RSS(0.568, 0.0) = 0.568
      chain  = RSS(1*0.2, 2*0.15) ≈ 0.3605551275
      total  = RSS(parent, chain) ≈ 0.6727733645
    """
    payload = {
        "error_type": "RelErr",
        "by_formula": True,
        "formula": {"quantityValue": "Pizm_Pmax", "constValue": 0.4, "slopeValue": 0.2},
        "standard": "рд-2025",
        "value": 2_100_000.0,
        "p_max": 2_500_000.0,

        # additional не передаём → трактуется как 0.0

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.2, "unit": "percent"}},
        "converter2IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.15, "unit": "percent"}},
        "converter1Enabled": True,
        "converter2Enabled": True,

        "options": {"conv2_func": "quadratic"},
    }
    calc = PressureCalculator(payload)
    res = calc.compute()

    main_rel = 0.4 + 0.2*(2.1/2.5)
    add_rel  = 0.0
    parent   = sqrt(main_rel**2 + add_rel**2)
    chain    = sqrt((1*0.2)**2 + (2*0.15)**2)
    total    = sqrt(parent**2 + chain**2)
    approx(res.total_rel, total)
    print("✓ by_formula (additional=0.0) + 2 converters -> total =", res.total_rel)

def test_by_formula_two_converters_add01():
    """
    by_formula=True, additional=0.1 (явно передаём):
      main_rel = 0.568%
      parent = RSS(0.568, 0.1) ≈ 0.5767356413
      chain  = RSS(1*0.2, 2*0.15) ≈ 0.3605551275
      total  = RSS(parent, chain) ≈ 0.6801646859
    """
    payload = {
        "error_type": "RelErr",
        "by_formula": True,
        "formula": {"quantityValue": "Pizm_Pmax", "constValue": 0.4, "slopeValue": 0.2},
        "standard": "рд-2025",
        "value": 2_100_000.0,
        "p_max": 2_500_000.0,

        "main": 0.0,          # база требует наличие поля, игнорируется при by_formula
        "additional": 0.1,    # вот здесь даём 0.1%

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.2, "unit": "percent"}},
        "converter2IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.15, "unit": "percent"}},
        "converter1Enabled": True,
        "converter2Enabled": True,

        "options": {"conv2_func": "quadratic"},
    }
    calc = PressureCalculator(payload)
    res = calc.compute()

    main_rel = 0.4 + 0.2*(2.1/2.5)
    add_rel  = 0.1
    parent   = sqrt(main_rel**2 + add_rel**2)
    chain    = sqrt((1*0.2)**2 + (2*0.15)**2)
    total    = sqrt(parent**2 + chain**2)
    approx(res.total_rel, total)
    print("✓ by_formula (additional=0.1) + 2 converters -> total =", res.total_rel)

def test_abs_err_converted_plus_chain():
    """
    AbsErr с переводом по value:
      main_abs=5000 Па -> 0.2380952381%
      add_abs =2000 Па -> 0.0952380952%
      parent = RSS(...) ≈ 0.2564364194
      chain  = 0.1%
      total  ≈ 0.2752446860
    """
    payload = {
        "error_type": "AbsErr",
        "main": 5000.0,
        "additional": 2000.0,
        "standard": "рд-2025",
        "value": 2_100_000.0,

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.1, "unit": "percent"}},
        "converter1Enabled": True,
    }
    calc = PressureCalculator(payload)
    res = calc.compute()

    main_rel = 5000.0/2_100_000.0*100.0
    add_rel  = 2000.0/2_100_000.0*100.0
    parent   = sqrt(main_rel**2 + add_rel**2)
    chain    = 0.1
    total    = sqrt(parent**2 + chain**2)
    approx(res.total_rel, total)
    print("✓ AbsErr→Rel + converter -> total =", res.total_rel)

def run_all():
    test_by_values_with_converters()
    test_by_formula_two_converters_add0()
    test_by_formula_two_converters_add01()
    test_abs_err_converted_plus_chain()
    print("\nALL PRESSURE TESTS PASSED ✔")

if __name__ == "__main__":
    run_all()
