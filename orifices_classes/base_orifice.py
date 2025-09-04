from __future__ import annotations

import math
import inspect
import logging
from abc import ABC, abstractmethod
from typing import Optional

logger = logging.getLogger(__name__)  # TODO: заменить на проектный get_logger


class BaseOrifice(ABC):
    """
    Базовый класс без дефолтного расчёта β.
    β берётся так: ручной override (set_beta) → _beta_from_geometry() [АБСТРАКТНЫЙ].
    Т.е. базовый класс сам β не считает — обязанность подкласса.
    """

    def __init__(self, D: float, d: float, Re: float):
        self.D = float(D)
        self.d = float(d)
        self.Re = float(Re)
        self._beta: Optional[float] = None
        self.straightness = None

    # ---------------- β API ----------------
    def set_beta(self, beta: Optional[float]) -> None:
        if beta is None:
            self._beta = None
            return
        if not (0.0 < float(beta) < 1.0):
            raise ValueError(f"beta={beta} вне (0,1)")
        self._beta = float(beta)

    def calculate_beta(self) -> float:
        if self._beta is not None:
            return self._beta
        return self._beta_from_geometry()

    @abstractmethod
    def _beta_from_geometry(self) -> float:
        """Абстрактная заглушка: подкласс обязан вернуть β своей методики."""
        raise NotImplementedError

    # ---------------- валидаторы/утилиты ----------------
    def validate(self) -> bool:
        try:
            return self._validate()
        except Exception as e:
            logger.error(f"Validation error in {self.__class__.__name__}: {e}")
            return False

    @abstractmethod
    def _validate(self) -> bool:
        pass

    @abstractmethod
    def get_geom_checks(self) -> dict:
        """Возвращает словарь описаний геом. требований/параметров."""
        return NotImplementedError

    def calc_K_CCU(self, alpha_CCU: float, t: float) -> float:
        return 1 + alpha_CCU * (t - 20)

    def calc_K_T(self, alpha_T: float, t: float) -> float:
        return 1 + alpha_T * (t - 20)

    def update_geometry_from_temp(self, d_20: float, D_20: float,
                                  alpha_CCU: float, alpha_T: float, t: float):
        self.d = float(d_20) * self.calc_K_CCU(alpha_CCU, t)
        self.D = float(D_20) * self.calc_K_T(alpha_T, t)
        logger.debug(f"{self.__class__.__name__}: Обновлена геометрия: d={self.d}, D={self.D}")

    def _get_roughness_limits(self):
        return [
            (0.3, 25.0), (0.32, 18.2), (0.35, 12.9), (0.36, 10.0),
            (0.37, 8.3), (0.39, 7.1), (0.45, 5.6), (0.5, 4.9),
            (0.6, 4.2), (0.7, 4.0), (1.0, 3.9),
        ]

    def validate_roughness(self, Ra: float) -> bool:
        beta = self.calculate_beta()
        ratio = (Ra / self.D) * 1e4
        for max_beta, max_ratio in self._get_roughness_limits():
            if beta <= max_beta:
                if ratio > max_ratio:
                    logger.warning(f"[Ошибка Ra] Ra/D*1e4 = {ratio} > {max_ratio} при β = {beta}.")
                    return False
                return True
        logger.warning(f"[Ошибка Ra] β = {beta} вне допустимого диапазона таблицы 4.")
        return False

    def roughness_allowance(self) -> float:
        beta = self.calculate_beta()
        for max_beta, max_ratio in self._get_roughness_limits():
            if beta <= max_beta:
                return self.D * max_ratio / 1e4
        logger.warning(f"[Ra допуск] β = {beta} не найден в таблице допусков.")
        return None

    def calculate_E(self) -> float:
        beta = self.calculate_beta()
        denom = 1 - beta**4
        if denom <= 0:
            logger.error(f"Ошибка при расчёте E: недопустимое значение β={beta}")
            raise ValueError(f"Неверное β={beta}: подкоренное выражение ≤0")
        return 1.0 / math.sqrt(denom)

    def run_all(self, delta_p: float, **kwargs) -> dict:
        result = {
            "beta": self.calculate_beta(),
            "E_speed": self.calculate_E(),
            "straightness": self.straightness,
        }

        sig_C = inspect.signature(self.calculate_C)
        params_C = {
            name for name, param in sig_C.parameters.items()
            if name != "self"
            and param.kind in (inspect.Parameter.POSITIONAL_ONLY,
                               inspect.Parameter.POSITIONAL_OR_KEYWORD)
        }
        args_C = {k: v for k, v in kwargs.items() if k in params_C}
        result["C"] = self.calculate_C(**args_C)

        result['ssu_params'] = self.get_geom_checks()

        sig_eps = inspect.signature(self.calculate_epsilon)
        args_eps = {}
        for name, param in sig_eps.parameters.items():
            if name == "self":
                continue
            if name == "delta_p":
                args_eps[name] = delta_p
            elif name in kwargs:
                args_eps[name] = kwargs[name]
        result["Epsilon"] = self.calculate_epsilon(**args_eps)

        result["pressure_loss"] = self.pressure_loss(delta_p)

        logger.info(f"{self.__class__.__name__}: Успешный расчёт всех параметров")
        return result

    # -------------- абстрактные спец-методы --------------
    @abstractmethod
    def check_Re(self) -> bool:
        raise NotImplementedError

    @abstractmethod
    def calculate_C(self, *args, **kwargs) -> float:
        """Коэффициент истечения"""
        raise NotImplementedError

    @abstractmethod
    def calculate_epsilon(self, delta_p: float, *args, **kwargs) -> float:
        """Коэффициент расширения"""
        raise NotImplementedError

    #@abstractmethod
    def discharge_coefficient_uncertainty(self) -> float:
        """Относительня погрешность коэффициента истечения"""
        raise NotImplementedError

    #@abstractmethod
    def expansion_coefficient_uncertainty(self, dp_p: float, k: float | None = None) -> float:
        """Относительня погрешность коэффициента расширения"""
        raise NotImplementedError


    @abstractmethod
    def pressure_loss(self, delta_p: float) -> float:
        """Потери давления"""
        raise NotImplementedError


#todo добавиьть заглушки к рассчету доп св-в + раскоментировать в соотв классах методы  + изменить адаптер для записи результатов
#todo потом можно подклчать пакет погрешностей
#todo затем можно формировать итоговый пакет сборки результатов