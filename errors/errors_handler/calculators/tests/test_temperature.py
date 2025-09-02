# errors/errors_handler/calculators/tests/test_temperature.py
from math import sqrt, isclose
from errors.errors_handler.calculators.temperature import TemperatureCalculator

def approx(a, b, tol=1e-9):
    assert isclose(a, b, rel_tol=0, abs_tol=tol), f"expected {b}, got {a}"

def test_by_values_with_converters():
    """
    Режим по значениям (RelErr):
      parent = RSS(0.3, 0.1) = 0.31622777
      chain (conv1: 0.2%, conv1compl: 0.1%) = RSS(0.2, 0.1) = 0.2236067977
      total = RSS(parent, chain) ≈ 0.389249
    """
    payload = {
        "error_type": "RelErr",
        "standard": "рд-2025",
        "value": 250.0,      # K
        "main": 0.3,         # %
        "additional": 0.1,   # %

        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.2, "unit": "percent"}},
        "converter1ComplError": {"errorTypeId": "RelErr", "value": {"real": 0.1, "unit": "percent"}},
        "converter1Enabled": True,
    }
    calc = TemperatureCalculator(payload)
    res = calc.compute()

    parent = sqrt(0.3**2 + 0.1**2)
    chain  = sqrt(0.2**2 + 0.1**2)
    total  = sqrt(parent**2 + chain**2)
    approx(res.total_rel, total)
    print("✓ temperature by_values + 1 converter -> total =", res.total_rel)

def test_by_formula_three_converters_and_range():
    """
    Формульный режим:
      value = 250 K  (≈ -23.15 °C)
      ΔT_abs = const + slope*|t°C| = 0.05 + 0.01*23.15 = 0.2815 K
      main_rel = 0.2815/250*100 = 0.1126%
      additional = 0.0 (по умолчанию)
      parent = 0.1126%

      Цепочка (табл.7):
        conv1: linear 0.05% -> k=1
        conv2: quadratic 0.04% -> k=2
        conv3: linear 0.03% -> k=1
      chain = sqrt( (1*0.05)^2 + (2*0.04)^2 + (1*0.03)^2 )
            = sqrt(0.0025 + 0.0064 + 0.0009) = sqrt(0.0098) ≈ 0.09899495%

      total = RSS(parent, chain)
    Диапазон: range_min=-40, range_max=60 — просто проверяем, что не ломает и попадёт в стандарт при необходимости.
    """
    payload = {
        "error_type": "RelErr",
        "by_formula": True,
        "formula": {"quantityValue": "t_abs", "constValue": 0.05, "slopeValue": 0.01},
        "standard": "рд-2025",
        "value": 250.0,          # K
        "range_min": -40.0,      # °C или K — стандарт сам знает; здесь нам важен факт наличия границ
        "range_max": 60.0,

        # три преобразователя
        "converter1IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.05, "unit": "percent"}},
        "converter1Enabled": True,

        "converter2IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.04, "unit": "percent"}},
        "converter2Enabled": True,

        "converter3IntrError": {"errorTypeId": "RelErr", "value": {"real": 0.03, "unit": "percent"}},
        "converter3Enabled": True,

        "options": {"conv2_func": "quadratic"}  # второй — квадратичный
    }
    calc = TemperatureCalculator(payload)
    res = calc.compute()

    # ожидаемое
    main_abs = 0.05 + 0.01*abs(250.0 - 273.15)     # 0.2815 K
    parent   = ( (main_abs/250.0*100.0)**2 + 0.0**2 )**0.5
    chain    = ( (1*0.05)**2 + (2*0.04)**2 + (1*0.03)**2 )**0.5
    total    = (parent**2 + chain**2) ** 0.5
    approx(res.total_rel, total, tol=1e-12)
    print("✓ temperature by_formula + 3 converters + range -> total =", res.total_rel)

def run_all():
    test_by_values_with_converters()
    test_by_formula_three_converters_and_range()
    print("\nALL TEMPERATURE TESTS PASSED ✔")

if __name__ == "__main__":
    run_all()
