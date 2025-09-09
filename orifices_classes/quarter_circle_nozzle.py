from .base_orifice import BaseOrifice
import math

from logger_config import get_logger

logger = get_logger("QuarterCircleNozzle")

class QuarterCircleNozzle(BaseOrifice):
    """
    Сопло «четверть круга»
    """
    def __init__(self, D: float, d: float, Re: float, p: float, k: float, delta_p: float, **kwargs):
        super().__init__(D, d, Re)
        self.p = p
        self.k = k
        self.delta_p = delta_p
        
    def _beta_from_geometry(self):
        return round(self.d / self.D, 12)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        # 12.3.1.1
        if not (0.025 <= self.D <= 0.1 and 0.0055 <= self.d <= 0.07 and 0.22 <= beta <= 0.7):
            logger.error(f"[Validation error] {self.__class__.__name__}: "
                  f"D={self.D:.3f}, d={self.d:.3f}, β={beta:.3f}")
            return False
        return True

    def get_geom_checks(self) -> dict:
        """п.12"""
        checks = {}
        beta = self.calculate_beta()

        # 12.3.1.1
        checks['Диапазон D'] = "0.025--0.500 м"
        checks['Диапазон d'] = "0.010--0.300 м"
        checks['Диапазон β'] = "0.10--0.70"

        # 12.3.1.1
        checks['Толщина EД'] = f"≤ 0.1·D = {0.1 * self.D:.5f} м"

        # 12.3.1.1
        e_min = 0.0025
        e_max = 0.1 * self.D
        checks['Длина e'] = f"{e_min:.5f}--{e_max:.5f} м"

        # 12.3.1.3
        max_e_var = 0.001 * self.D if self.D > 0.2 else 0.0002
        checks['Вариация e'] = f"≤ {max_e_var:.6f} м"

        # 12.3.2(12.1–12.3)
        if beta < 0.616:
            formula = "r = d·(0.09234828 − 0.12652313·√β) / (1 − 2.2516243·√β + 0.22777416·β)"
        elif beta < 0.67:
            formula = "r = d·(23544.99·√β − 8209.1867) / (1 − 21177.205·√β + 76920.027·β)"
        else:
            formula = "r = d·(2.6227151·√β − 0.65105587) / (1 − 1.3314439·√β + 4.4964523·β)"
        checks['Формула r'] = formula

        # 12.3.2.4 Предельное отклонение радиуса (±1% от r_calc)
        checks['Допуск r'] = "±1% от расчетного r"

        return checks

    def check_Re(self) -> bool:
        #todo вопрос по строгому и не строгому равенсту Re
        beta = self.calculate_beta()
        if beta <= 0.316:
            Re_min = 2000
        else:
            Re_min = 7377 - 37016 * beta + 75648 * beta**2 - 39646 * beta**3
        Re_max = (-715045 +
                  10677719 * beta
                  - 59108018 * beta**2
                  + 157861035 * beta**3
                  - 200731143 * beta**4
                  + 97892444 * beta**5)
        if not Re_min < self.Re < Re_max:
            logger.error(f"[Re check] {self.__class__.__name__}: {Re_max} < Re={self.Re} < {Re_max}")
            return False
        return True

    def calculate_C(self) -> float:
        """п.12.4.1"""
        beta = self.calculate_beta()
        E = self.calculate_E()
        return (0.7772 - 0.2137 * beta**2 + 2.0437 * beta**4 - 1.2664 * beta**6) * (1/E)

    def discharge_coefficient_uncertainty(self) -> float:
        """Относительная погрешность п.12.4.1"""
        return 1

    def calculate_epsilon(self) -> float:
        """Коэффициент расширения п.12.4.2"""
        if self.delta_p / self.p > 0.25:
            raise ValueError("Δp/p > 0.25")
        beta = self.calculate_beta()
        return 1 - (0.484 + 1.54 * beta**4) * self.delta_p / (self.p * self.k)

    def expansion_coefficient_uncertainty(self) -> float:
        """Относительная погрешность п.12.4.2"""
        return 1.25 * (self.delta_p / self.p)

    def pressure_loss(self) -> float:
        """п.12.5"""
        beta = self.calculate_beta()
        return (1 - 1.56 * beta**2 + 0.63 * beta**4) * self.delta_p
