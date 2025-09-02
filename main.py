# file: main.py
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict

try:
    import logger_config  # noqa: F401
    logger = logging.getLogger("new_ssu")
    if not logger.handlers:
        logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
except Exception:
    logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
    logger = logging.getLogger("new_ssu")

from controllers.input_controller import InputController  # noqa: E402
from controllers.calculation_adapter import run_calculation  # noqa: E402


def _load_json(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _json_default(obj: Any) -> Any:
    """JSON-сериализация для нестандартных типов (dataclass, Decimal, Path, set, ...)."""
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, Decimal):
        return float(obj)
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, (set, frozenset)):
        return list(obj)
    if hasattr(obj, "to_dict"):
        try:
            return obj.to_dict()
        except Exception:
            pass
    # последний шанс — строковое представление (чтобы не падать на типах контроллера)
    return str(obj)


def _dump_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


def main() -> int:
    ap = argparse.ArgumentParser(description="Запуск расчёта new_ssu")
    ap.add_argument("--input", type=Path, default=Path("inputdata/1.json"))
    ap.add_argument("--output", type=Path, default=Path("outputdata/result.json"))
    args = ap.parse_args()

    logger.info("Чтение входа: %s", args.input)
    data = _load_json(args.input)

    ic = InputController()
    parsed = ic.parse(data)
    for r in parsed.remarks:
        logger.info(r)

    logger.info("Формирование PreparedController…")
    prepared = ic.prepare_params(data)

    logger.info("Вызов CalculationController…")
    calc = run_calculation(prepared, parsed.values_si, data)

    out = {
        "meta": {
            "ts": datetime.utcnow().isoformat() + "Z",
            "input": str(args.input),
            "type": data.get("type"),
            "methodic": data.get("physPackage", {}).get("physProperties", {}).get("methodic"),
            "controller": "CalculationController",
        },
        "remarks": parsed.remarks,
        "prepared": asdict(prepared) if is_dataclass(prepared) else prepared,
        "result": calc,  # может содержать dataclass — обработаем в _json_default
    }

    logger.info("Запись результата: %s", args.output)
    _dump_json(args.output, out)
    logger.info("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
