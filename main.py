
from __future__ import annotations

import json
from json import JSONDecodeError
from pathlib import Path
from typing import Any, Dict
import re

_COMMENT_BLOCK_RE = re.compile(r"/\*.*?\*/", re.S)
_COMMENT_LINE_RE = re.compile(r"(^|[^:])//.*?$", re.M)


def _strip_json_comments(text: str) -> str:
    """Удаляет C-подобные комментарии из JSON (/* ... */ и // ... до конца строки).
    Важно: не использовать для production-конфигов с URL'ами вида "http://..." внутри строк.
    """
    # Удаляем блочные комментарии
    text = _COMMENT_BLOCK_RE.sub("", text)
    # Удаляем построчные комментарии, но не трогаем 'http://': матчим только если перед // нет двоеточия
    text = _COMMENT_LINE_RE.sub(lambda m: m.group(1), text)
    return text


def _load_json(path: Path) -> Dict[str, Any]:
    raw = path.read_text(encoding="utf-8")
    if not raw.strip():
        raise RuntimeError(f"Пустой файл JSON: {path}")
    try:
        return json.loads(raw)
    except JSONDecodeError:
        # Попробуем как JSONC (с комментариями)
        cleaned = _strip_json_comments(raw)
        try:
            return json.loads(cleaned)
        except JSONDecodeError as e:
            # Покажем контекст вокруг ошибки
            start = max(e.pos - 60, 0)
            end = min(e.pos + 60, len(cleaned))
            snippet = cleaned[start:end].replace("\n", "\\n")
            raise RuntimeError(
                f"Ошибка парсинга JSON в {path}: {e.msg} (line {e.lineno}, col {e.colno}).\n"
                f"Контекст вокруг позиции {e.pos}: '{snippet}'"
            ) from e



def _json_default(obj: Any) -> Any:
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
        "result": calc,
    }

    logger.info("Запись результата: %s", args.output)
    _dump_json(args.output, out)
    logger.info("Готово.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
