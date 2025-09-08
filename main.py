# file: main.py
from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, is_dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable
from json import JSONDecodeError

from logger_config import get_logger  # используем ТОЛЬКО ваш логгер во всём проекте

logger = get_logger("Main")  # модульный логгер

# --- JSON utils -------------------------------------------------------------
_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE_RE = re.compile(r"(^|[^:])//.*?$", re.M)


def _strip_json_comments(text: str) -> str:
    """Удаляет C-подобные комментарии из JSON (/* ... */ и // ... до конца строки)."""
    text = _COMMENT_BLOCK_RE.sub("", text)
    text = _COMMENT_LINE_RE.sub(lambda m: m.group(1), text)
    return text


def _load_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise RuntimeError(f"Пустой файл JSON: {path}")
    try:
        return json.loads(raw)
    except JSONDecodeError:
        cleaned = _strip_json_comments(raw)
        try:
            return json.loads(cleaned)
        except JSONDecodeError as e:
            start = max(e.pos - 60, 0)
            end = min(e.pos + 60, len(cleaned))
            snippet = cleaned[start:end].replace("", "\n")
            raise RuntimeError(
                f"Ошибка парсинга JSON в {path}: {e.msg} (line {e.lineno}, col {e.colno})."
                f"Контекст вокруг позиции {e.pos}: '{snippet}'"
            ) from e


def _json_default(obj: Any) -> Any:
    """Сериализация нестандартных типов: dataclass/Decimal/Path/set/obj.to_dict."""
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
    return str(obj)


def _dump_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2, default=_json_default)


# --- App entry --------------------------------------------------------------
from controllers.input_controller import InputController  # noqa: E402
from controllers.calculation_adapter import run_calculation  # noqa: E402


def _process_one(input_path: Path, output_path: Path) -> None:
    logger.info("Чтение входа: %s", input_path)
    data = _load_json(input_path)

    ic = InputController()
    parsed = ic.parse(data)
    for r in parsed.remarks:
        logger.info(r)

    logger.info("Формирование PreparedController…")
    prepared = ic.prepare_params(data)
    logger.info("Параметры успешно прошли валидацию")

    logger.info("Вызов CalculationController…")
    calc = run_calculation(prepared, parsed.values_si, data)

    out = {
        "result": calc
    }

    logger.info("Запись результата: %s", output_path)
    _dump_json(output_path, out)


def _iter_inputs(base: Path, pattern: str) -> Iterable[Path]:
    # rglob, чтобы поддержать вложенные папки
    yield from base.rglob(pattern)


def main() -> int:
    ap = argparse.ArgumentParser(description="Запуск расчёта new_ssu")
    ap.add_argument("--input", type=Path, default=Path("inputdata/conical_01.json"),
                    help="входной JSON или директория с JSON-файлами")
    ap.add_argument("--output", type=Path, default=Path("outputdata/result.json"),
                    help="файл результата (для одиночного запуска)")
    ap.add_argument("--outdir", type=Path, default=Path("outputdata"),
                    help="каталог результатов (для пакетного запуска по директории)")
    ap.add_argument("--glob", type=str, default="*.json",
                    help="маска поиска JSON в режиме каталога (rglob)")
    args = ap.parse_args()

    if args.input.is_dir():
        base_in: Path = args.input
        base_out: Path = args.outdir
        logger.info("Пакетный запуск: dir=%s, glob=%s → outdir=%s", base_in, args.glob, base_out)
        count = 0
        for src in _iter_inputs(base_in, args.glob):
            if not src.is_file():
                continue
            rel = src.relative_to(base_in)
            dst = base_out / rel
            try:
                _process_one(src, dst)
                count += 1
            except Exception as e:
                logger.exception("Ошибка при обработке %s: %s", src, e)
        logger.info("Готово. Успешно обработано файлов: %d", count)
        return 0

    # Одиночный режим
    _process_one(args.input, args.output)
    logger.info("Готово.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())


#python main.py --input inputdata/cone_01.json --output outputdata/result.json
#python main.py --input inputdata --outdir outputdata --glob "*.json"
