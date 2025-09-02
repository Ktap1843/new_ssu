# path: controllers/calculation_adapter.py
"""Calculation Adapter: связывает создание ССУ (дросселирующего устройства)
и вычисление расхода. Не создаёт новых файлов и не ломает существующие импорты.

Использование:
    from controllers.calculation_adapter import CalculationAdapter, Fluid, Process, SSUType

    adapter = CalculationAdapter()
    ssu = adapter.build_ssu(SSUType.ORIFICE, D=0.2, d=0.1, taps="corner")
    flow = adapter.calc_flow(ssu, Fluid(rho=998.2, mu=1.0e-3), Process(D=0.2, d=0.1, dp=5_000, p1=2.0e5, t1=293.15))
    print(flow)

Примечания:
- Если в пакете `calc_flow` уже есть «правильная» функция, адаптер найдёт её динамически
  (по именам вида calculate_flow/compute_flow/calc_flow/calc/calculate). Иначе —
  fallback (упрощённая ISO 5167) — чтобы пайплайн работал сразу.
- Для поиска класса ССУ адаптер перебирает модули в пакете `orifices_classes` и пытается
  найти класс по типу (orifice/nozzle/venturi). Если не находит — встроенный класс.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from importlib import import_module
from importlib.util import find_spec
import inspect
import math
import pkgutil
from types import ModuleType
from typing import Any, Callable, Dict, Optional, Protocol, TypedDict


# -------------------- Доменные типы --------------------

class SSUType(str, Enum):
    ORIFICE = "orifice"
    NOZZLE = "nozzle"
    VENTURI = "venturi"


@dataclass(slots=True)
class Fluid:
    rho: float  # кг/м^3
    mu: float   # Па·с
    kappa: float = 1.4
    is_gas: bool = False


@dataclass(slots=True)
class Process:
    D: float
    d: float
    dp: float
    p1: float
    t1: float
    taps: Optional[str] = None


class SSULike(Protocol):
    D: float
    d: float
    type: SSUType

    def discharge_coefficient(self, Re: float, beta: float, **ctx: Any) -> float: ...


class FlowResult(TypedDict):
    beta: float
    Re: float
    C: float
    epsilon: float
    qv: float  # м^3/с
    qm: float  # кг/с


# -------------------- Вспомогательные утилиты --------------------

def _area(d: float) -> float:
    return math.pi * d * d / 4.0


def _reynolds(rho: float, v: float, D: float, mu: float) -> float:
    return rho * v * D / max(mu, 1e-12)


def _epsilon_orifice(beta: float, kappa: float, dp: float, p1: float) -> float:
    if dp <= 0 or p1 <= 0:
        return 1.0
    m = (0.351 + 0.256 * beta**4 + 0.93 * beta**8)
    x = dp / p1
    return max(min(1.0 - (m / kappa) * x, 1.0), 0.6)


# -------------------- Адаптер --------------------

class CalculationAdapter:
    """Координирует шаги: создание ССУ → расчёт расхода.

    Почему так: минимально-инвазивная интеграция под разные имена функций/классов в проекте.
    """

    # ---- Создание ССУ ----
    def build_ssu(self, ssu_type: SSUType, D: float, d: float, taps: Optional[str] = None) -> SSULike:
        # 1) Сначала пытаемся найти класс в пакете `orifices_classes` по типу
        candidate = self._find_ssu_class(ssu_type)
        if candidate is not None:
            try:
                return candidate(D=D, d=d, taps=taps)  # type: ignore[call-arg]
            except TypeError:
                # Почему: возможны другие имена аргументов у пользовательских классов
                return candidate(D, d)  # type: ignore[misc]

        # 2) Фоллбек: встроенный класс с приемлемым C(Re, beta)
        class _BuiltinSSU:
            def __init__(self, D: float, d: float, ssu_type: SSUType, taps: Optional[str]):
                self.D = D
                self.d = d
                self.type = ssu_type
                self.taps = taps

            def discharge_coefficient(self, Re: float, beta: float, **ctx: Any) -> float:
                # Почему: безопасные ориентиры близко к ISO 5167
                if self.type is SSUType.ORIFICE:
                    return 0.596 + 0.0261 * beta**2 - 0.216 * beta**8 + (0.000521 / (Re**0.7 + 1e-9))
                if self.type is SSUType.NOZZLE:
                    return 0.995 - 10_000.0 / (Re + 10_000.0)
                if self.type is SSUType.VENTURI:
                    return 0.985
                return 0.62

        return _BuiltinSSU(D=D, d=d, ssu_type=ssu_type, taps=taps)  # type: ignore[return-value]

    def _find_ssu_class(self, ssu_type: SSUType):
        if find_spec("orifices_classes") is None:
            return None
        pkg = import_module("orifices_classes")
        type_key = ssu_type.value.lower()
        for modinfo in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
            mod: ModuleType = import_module(f"orifices_classes.{modinfo.name}")
            for name, obj in vars(mod).items():
                if not inspect.isclass(obj):
                    continue
                low = name.lower()
                if any(k in low for k in ("orifice", "diaphr", "nozzle", "venturi")):
                    if type_key in low or (type_key == "orifice" and ("orifice" in low or "diaphr" in low)):
                        return obj
        return None

    # ---- Поиск функции расчёта в проекте ----
    def _find_calc_func(self) -> Optional[Callable[[SSULike, Fluid, Process], FlowResult]]:
        if find_spec("calc_flow") is None:
            return None
        pkg = import_module("calc_flow")
        candidates = [
            "calculate_flow", "compute_flow", "calc_flow", "calc", "calculate",
            "get_flow", "flow_rate",
        ]
        # 1) Пробуем простые имена на уровне пакета
        for name in candidates:
            fn = getattr(pkg, name, None)
            if callable(fn) and self._callable_compatible(fn):
                return fn  # type: ignore[return-value]
        # 2) Обходим подпакеты/модули
        for modinfo in pkgutil.iter_modules(getattr(pkg, "__path__", [])):
            sub = import_module(f"calc_flow.{modinfo.name}")
            for name, obj in vars(sub).items():
                if callable(obj) and name in candidates and self._callable_compatible(obj):
                    return obj  # type: ignore[return-value]
        return None

    @staticmethod
    def _callable_compatible(fn: Callable[..., Any]) -> bool:
        try:
            sig = inspect.signature(fn)
        except (TypeError, ValueError):
            return False
        params = list(sig.parameters.values())
        if len(params) < 3:
            return False
        # Почему: допускаем разные имена, но позиционно ≥3 параметров
        return True

    # ---- Расчёт ----
    def calc_flow(self, ssu: SSULike, fluid: Fluid, proc: Process) -> FlowResult:
        project_fn = self._find_calc_func()
        if project_fn is not None:
            # Передаём как есть — пользовательская реализация приоритетна
            return project_fn(ssu, fluid, proc)  # type: ignore[return-value]
        # Фоллбек (упрощённый ISO 5167)
        beta = proc.d / proc.D
        beta4 = beta ** 4
        A_pipe = _area(proc.D)
        A_orif = _area(proc.d)
        C0 = 0.62
        qv_guess = C0 * A_orif * math.sqrt(max(2.0 * proc.dp / (fluid.rho * max(1.0 - beta4, 1e-12)), 0.0))
        v_pipe_guess = qv_guess / max(A_pipe, 1e-12)
        Re_guess = _reynolds(fluid.rho, v_pipe_guess, proc.D, fluid.mu)
        C = getattr(ssu, "discharge_coefficient", lambda Re, beta, **kw: C0)(Re_guess, beta)
        epsilon = 1.0
        if fluid.is_gas:
            epsilon = _epsilon_orifice(beta, fluid.kappa, proc.dp, proc.p1)
        coef = C * epsilon * A_orif
        denom = math.sqrt(max(1.0 - beta4, 1e-12))
        qv = coef * math.sqrt(max(2.0 * proc.dp / (fluid.rho * denom**2), 0.0))
        qm = qv * fluid.rho
        v_pipe = qv / max(A_pipe, 1e-12)
        Re = _reynolds(fluid.rho, v_pipe, proc.D, fluid.mu)
        return FlowResult(beta=beta, Re=Re, C=C, epsilon=epsilon, qv=qv, qm=qm)

    # ---- Высокоуровневый шаг: создание + расчёт ----
    def run(self, ssu_type: SSUType, process: Process, fluid: Fluid) -> FlowResult:
        ssu = self.build_ssu(ssu_type, D=process.D, d=process.d, taps=process.taps)
        return self.calc_flow(ssu, fluid, process)


__all__ = [
    "CalculationAdapter",
    "SSUType",
    "Fluid",
    "Process",
    "FlowResult",
    "run_calculation",
]

# ---- Удобная точка входа для main.py ----

def run_calculation(
    ssu_type: SSUType | str,
    process: Optional[Process] = None,
    fluid: Optional[Fluid] = None,
    **kwargs: Any,
) -> FlowResult:
    """Гибкая обёртка, совместимая с разными стилями вызова из main.py.

    Поддерживаемые способы:
      1) run_calculation("orifice", D=..., d=..., dp=..., p1=..., t1=..., rho=..., mu=..., taps=..., is_gas=..., kappa=...)
      2) run_calculation(SSUType.ORIFICE, process=Process(...), fluid=Fluid(...))
      3) run_calculation("nozzle", process={...}, fluid={...})
    """
    # Нормализуем тип ССУ
    if isinstance(ssu_type, str):
        try:
            ssu_type = SSUType(ssu_type.lower())
        except ValueError as exc:
            raise ValueError(f"Unknown ssu_type='{ssu_type}'. Expected one of: {[t.value for t in SSUType]}") from exc

    # Если process/fluid переданы словарями — преобразуем
    if isinstance(process, dict):
        process = Process(**process)  # type: ignore[arg-type]
    if isinstance(fluid, dict):
        fluid = Fluid(**fluid)  # type: ignore[arg-type]

    # Если process/fluid не заданы — собираем из kwargs
    if process is None:
        required_p = ["D", "d", "dp", "p1", "t1"]
        missing_p = [k for k in required_p if k not in kwargs]
        if missing_p:
            raise ValueError(f"Missing process keys: {missing_p}. Provide {required_p}.")
        process = Process(
            D=float(kwargs["D"]),
            d=float(kwargs["d"]),
            dp=float(kwargs["dp"]),
            p1=float(kwargs["p1"]),
            t1=float(kwargs["t1"]),
            taps=kwargs.get("taps"),
        )
    if fluid is None:
        required_f = ["rho", "mu"]
        missing_f = [k for k in required_f if k not in kwargs]
        if missing_f:
            raise ValueError(f"Missing fluid keys: {missing_f}. Provide {required_f}.")
        fluid = Fluid(
            rho=float(kwargs["rho"]),
            mu=float(kwargs["mu"]),
            kappa=float(kwargs.get("kappa", 1.4)),
            is_gas=bool(kwargs.get("is_gas", False)),
        )

    adapter = CalculationAdapter()
    return adapter.run(ssu_type, process, fluid)
