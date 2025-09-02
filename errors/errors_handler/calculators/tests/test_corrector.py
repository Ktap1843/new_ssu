from logger_config import get_logger
from errors.handle import compute_corrector_from_state

log = get_logger("CorrectorRunner")

cases = [
    {
        "title": "1",
        "state": {
            "complError": {"errorTypeId": "RelErr", "range": None, "value": {"real": 0.0, "unit": "percent"}},
            "intrError":  {"errorTypeId": "RelErr", "range": None, "value": {"real": 0.02, "unit": "percent"}},
        },
        "standard": "рд-2025",
        "ctx": {"value": 5.0}
    },
    {
        "title": "2",
        "state": {
            "complError": {"errorTypeId": "RelErr", "value": {"real": 0.01, "unit": "whatever"}},
            "intrError":  {"errorTypeId": "RelErr", "value": {"real": 0.02, "unit": "whatever"}},
        },
        "standard": "рд-2025",
        "ctx": {"value": 5.0}
    },
    {
        "title": "3",
        "state": {
            "complError": {"errorTypeId": "FidErr", "value": {"real": 0.2, "unit": "percent_of_range"}},
            "intrError":  {"errorTypeId": "FidErr", "value": {"real": 0.5, "unit": "percent_of_range"}},
        },
        "standard": "рд-2025",
        "ctx": {"value": 50.0, "range_min": 0.0, "range_max": 100.0}
    },
]

def run():
    for c in cases:
        log.info("--- %s ---", c["title"])
        try:
            res = compute_corrector_from_state(c["state"], c["standard"], **c["ctx"])
            log.info("main=%.6g%% add=%.6g%% total=%.6g%%", res.main_rel, res.additional_rel, res.total_rel)
        except Exception as e:
            log.error("Error: %s", e)

if __name__ == "__main__":
    run()
