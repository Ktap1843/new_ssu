from logger_config import get_logger
from errors.errors_handler.standards.rd_new import RD_2025

log = get_logger("RD2025-tests")
std = RD_2025()


#todo анализ переводов по методике
test_cases = [
    {"title": "1", "type": "RelErr", "err": 0.8, "value": 123.0, "expected": 0.8},
    {"title": "2", "type": "AbsErr", "err": 0.02, "value": 5.0, "expected": 0.4},
    {"title": "3", "type": "AbsErr", "err": 0.5, "value": -200.0, "expected": 0.25},
    {"title": "4", "type": "FidErr", "err": 0.5, "value": 14, "range_min": -40, "range_max": 100, "expected": 1},
    {"title": "5", "type": "AbsErr", "err": 1.0, "value": 12, "expect_error": True},
    {"title": "6", "type": "FidErr", "err": 1.0, "value": 11, "expect_error": True},
    {"title": "7", "type": "FidErr", "err": 1.0, "value": 55, "range_min": 0.0, "range_max": 100.0, "expect_error": True},
    {"title": "8", "type": "Smth", "err": 1.0, "value": 10, "expect_error": True},
    {"title": "9", "type": "FidErr", "err": 12.0, "value": 11, "range_min": -40, "range_max": 100,"expect_error": 0},
]

def _range_span(case: dict):
    if "range_min" in case and "range_max" in case:
        return abs(float(case["range_max"]) - float(case["range_min"]))
    return None

def run():
    for c in test_cases:
        log.info(f"--- {c['title']} ---")
        try:
            rs = std.to_rel_percent(
                c["type"], float(c["err"]),
                value=float(c["value"]) if "value" in c else None,
                range_span=_range_span(c),
            )
            log.info(f"_rel = {rs}%")
            if "expected" in c:
                log.info(f"expected = {c['expected']}%")
        except Exception as e:
            if c.get("expect_error"):
                log.info(f"raised as expected: {e}")
            else:
                log.error(f"UNEXPECTED ERROR: {e}")

if __name__ == "__main__":
    run()
