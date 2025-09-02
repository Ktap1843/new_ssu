"""
Адаптер для гибкого вызова пользовательского CalculationController.
Ищет метод в порядке: run → dispatch → calculate → process.
Пробует сигнатуры: (prepared, parsed, raw) именованные и позиционные; либо (prepared).
Возвращает диагностическую заглушку, если класса/метода нет.
"""
from __future__ import annotations

from typing import Any, Dict

try:
    from controllers.calculation_controller import CalculationController  # type: ignore
    _HAVE_CALC_CTRL = True
except Exception:
    CalculationController = None  # type: ignore
    _HAVE_CALC_CTRL = False


def run_calculation(prepared, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    if not _HAVE_CALC_CTRL or CalculationController is None:
        return {
            "status": "stub",
            "error": "CalculationController не обнаружен. Подключите controllers/calculation_controller.py",
            "prepared": {
                "d": prepared.d,
                "D": prepared.D,
                "p1": prepared.p1,
                "t1": prepared.t1,
                "dp": prepared.dp,
                "R": prepared.R,
                "Z": prepared.Z,
            },
            "used_values_si": {k: float(v) for k, v in parsed.items()},
        }

    ctrl = CalculationController()

    for meth_name in ("run", "dispatch", "calculate", "process"):
        if hasattr(ctrl, meth_name):
            meth = getattr(ctrl, meth_name)
            try:
                return meth(prepared=prepared, parsed=parsed, raw=raw)
            except TypeError:
                try:
                    return meth(prepared, parsed, raw)
                except TypeError:
                    try:
                        return meth(prepared)
                    except TypeError:
                        continue

    return {
        "status": "error",
        "error": "Подходящий метод CalculationController не найден (ожидается run/dispatch/calculate/process)",
    }
