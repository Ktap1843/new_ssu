# errors/errors_handler/calculators/tests/test_density.py
from math import sqrt, isclose
from errors.errors_handler.calculators.density import DensityStCalculator

def approx(a, b, tol=1e-9):
    assert isclose(a, b, rel_tol=0, abs_tol=tol), f"expected {b}, got {a}"

def test_rel_only_no_converters():
    """
    Только СИ в относительных:
      main=0.6%, additional=0.2% -> parent = sqrt(0.6^2 + 0.2^2) = 0.6324555%
      chain отсутствует -> total = parent
    """
    payload = {
        "standard": "рд-2025",
        "error_type": "RelErr",
        "main": 0.6,
        "additional": 0.2,
        # value не обязателен для RelErr
        # конвертеров нет
    }
    calc = DensityStCalculator(payload)
    res = calc.compute()
    parent = sqrt(0.6**2 + 0.2**2)
    approx(res.total_rel, parent)
    print("✓ density rel-only (no converters) ->", res.total_rel)

def test_rel_with_two_converters():
    """
    СИ + 2 преобразователя:
      parent = sqrt(0.6^2 + 0.2^2) = 0.6324555%
      conv1: δ1 = sqrt(0.4^2 + 0.3^2) = 0.5% (linear -> k=1 -> вклад 0.5)
      conv2: δ2 = sqrt(0.2^2 + 0.0^2) = 0.2% (quadratic -> k=2 -> вклад 0.4)
      chain = sqrt(0.5^2 + 0.4^2) = 0.6403124%
      total = sqrt(parent^2 + chain^2) ≈ 0.899999... ≈ 0.9%
    """
    payload = {
        "standard": "рд-2025",
        "error_type": "RelErr",
        "main": 0.6,
        "additional": 0.2,

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.4, "unit": "percent"}},
        "converter1ComplError": {"errorTypeId": "RelErr", "value": {"real": 0.3, "unit": "percent"}},
        "converter1Enabled": True,

        "converter2IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.2, "unit": "percent"}},
        "converter2ComplError": None,         # None -> 0
        "converter2Enabled": True,

        "options": {"conv2_func": "quadratic"}
    }
    calc = DensityStCalculator(payload)
    res = calc.compute()

    parent = (0.6**2 + 0.2**2) ** 0.5
    chain  = ( (1*0.5)**2 + (2*0.2)**2 ) ** 0.5
    total  = (parent**2 + chain**2) ** 0.5
    approx(res.total_rel, total, tol=1e-12)
    print("✓ density rel + 2 converters ->", res.total_rel)

def test_abs_to_rel_with_converter():
    """
    AbsErr -> RelErr:
      ρ = 0.73
      main_abs = 0.01 кг/м3 -> main_rel = 0.01/0.73*100 ≈ 1.369863%
      additional отсутствует -> 0
      conv1: 0.1% (linear -> k=1)
      total = sqrt(1.369863^2 + 0.1^2) ≈ 1.3735%
    """
    payload = {
        "standard": "рд-2025",
        "error_type": "AbsErr",
        "value": 0.73,
        "main": 0.01,              # единицы у стандарта/тестового рд-2025 не проверяются — это демонстрация
        "additional": 0.0,

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.1, "unit": "percent"}},
        "converter1Enabled": True,
    }
    calc = DensityStCalculator(payload)
    res = calc.compute()

    main_rel = 0.01/0.73*100.0
    total = (main_rel**2 + 0.1**2) ** 0.5
    approx(res.total_rel, total, tol=1e-9)
    print("✓ density abs->rel + converter ->", res.total_rel)

def run_all():
    test_rel_only_no_converters()
    test_rel_with_two_converters()
    test_abs_to_rel_with_converter()
    print("\nALL DENSITY TESTS PASSED ✔")

if __name__ == "__main__":
    run_all()
