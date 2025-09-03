import math
import logging

from orifices_classes.base_orifice import BaseOrifice

logger = logging.getLogger(__name__)

class CalcFlow:
    def __init__(self, d: float, D: float, p1: float, t1: float, delta_p: float, mu: float,
                 Roc: float, Ro: float, k: float, orifice: BaseOrifice,
                 Z: float = 1.0, R: float = 8.314, T_std: float = 293.15, p_std: float = 101325):
        self.d = d
        self.D = D
        self.p1 = p1
        self.t1 = t1
        self.delta_p = delta_p
        self.mu = mu
        self.Roc = Roc
        self.Ro = Ro
        self.k = k
        self.orifice = orifice
        self.R = R
        self.T_std = T_std
        self.p_std = p_std

        self.G = None
        self.Re = None

    def estimate_reynolds(self) -> float:
        """п. 5.2.5"""
        if self.mu != 0:
            self.Re = (4 * self.G) / (math.pi * self.D * self.mu * 0.000001) #todo опрос по вязкости
            logger.debug(f"Расчёт Re: {self.Re:.2f}")
        else:
            logger.warning("Вязкость (mu) равна 0. Re не может быть рассчитан")

        self.orifice.Re = self.Re
        # TODO ПРОВЕРКА И ВЫЧИСЛЕНИЕ RE НЕ БЪЕТСЯ ДЛЯ ВСЕХ ССУ!
        if not self.orifice.check_Re():
            msg = f"Re={self.Re:.0f} вне допустимого диапазона для {self.orifice.__class__.__name__}"
            logger.error(msg)
            raise ValueError(msg)

        return self.Re

    def calc_mass_flow(self):
        """п. 5.2.2"""
        A = (math.pi * self.D ** 2) / 4
        self.G = self.beta**2 * self.C * self.E * self.epsilon * A * math.sqrt(2 * self.Ro * self.delta_p)
        logger.debug(f"Массовый расход G: {self.G * 3600:.5f} кг/ч")
        return self.G #* 3600  # кг/ч

    def calc_standard_volume_flow(self):
        if self.G is None:
            self.calc_mass_flow()
        if self.Roc is None:
            logger.warning("Плотность в стандартных условиях (Roc) не задана. q_std = 0")
            return 0
        self.q_std = self.G / self.Roc
        logger.debug(f"Стандартный объёмный расход q_std: {self.q_std:.5f} м³/с")
        return self.q_std

    def calc_actual_volume_flow(self):
        if self.G is None:
            self.calc_mass_flow()
        A = (math.pi * self.D ** 2) / 4
        if self.Ro is None:
            logger.warning("Плотность в рабочих условиях (Ro) не задана. q_actual = 0")
            return 0
        self.q_actual = self.beta**2 * self.C * self.E * self.epsilon * A * math.sqrt(2 * self.delta_p / self.Ro)
        logger.debug(f"Актуальный объёмный расход q_actual: {self.q_actual:.5f} м³/с")
        return self.q_actual

    def calculate_discharge_coefficient(self):
        if self.C is None:
            logger.error("Коэффициент расхода C не установлен")
            raise RuntimeError("C ещё не установлен")
        return self.C

    def calculate_expansion_coefficient(self):
        if self.epsilon is None:
            logger.error("Коэффициент расширения ε не установлен")
            raise RuntimeError("ε ещё не установлено")
        return self.epsilon

    def run_all(self):
        """Запуск всех этапов расчёта"""
        logger.info("Запуск полного расчёта расходов")
        result = {
            "mass_flow": self.calc_mass_flow(),
            "Re": self.estimate_reynolds(),
            "volume_flow_actual": self.calc_actual_volume_flow(),
            "volume_flow_std": self.calc_standard_volume_flow(),
        }
        logger.info("Расчёт расходов завершён успешно")
        return result
