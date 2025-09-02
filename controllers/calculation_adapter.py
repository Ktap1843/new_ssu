# file: controllers/calculation_adapter.py
"""
Адаптер для гибкого вызова пользовательского CalculationController.
Зачем: у пользователя уже есть CalculationController, который раскидывает расчёты.
Этот модуль аккуратно импортирует его, находит подходящий метод (run/dispatch/calculate/process)
и передаёт параметры. Если контроллер не найден — возвращает диагностическую заглушку.
"""
from __future__ import annotations

from typing import Any, Dict

try:  # динамический импорт пользовательского контроллера расчёта
    from controllers.calculation_controller import CalculationController  # type: ignore
    _HAVE_CALC_CTRL = True
except Exception:  # нет ещё файла/класса — используем заглушку
    CalculationController = None  # type: ignore
    _HAVE_CALC_CTRL = False


def run_calculation(prepared, parsed: Dict[str, Any], raw: Dict[str, Any]) -> Dict[str, Any]:
    """Единая точка входа для вызова контроллера расчёта.

    Пытается вызвать CalculationController.{run|dispatch|calculate|process}.
    Возвращает словарь (готовый для записи в output).
    """
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
            # пробуем несколько сигнатур
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
