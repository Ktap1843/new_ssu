from .base_orifice import BaseOrifice
import math
import logging

logger = logging.getLogger(__name__)

class DoubleOrifice(BaseOrifice):
    """
    Двойная диафрагма
    """
    def __init__(self, D: float, d: float, Re: float, p: float, **kwargs):
        super().__init__(D, d=d, Re=Re)
        self.p = p


    def _beta_from_geometry(self):
        return round(self.d / self.D, 12)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        if not (0.0127 <= self.d <= 0.0705 and 0.04 <= self.D <= 0.1 and 0.32 <= beta <= 0.7):
            logger.warning(f"[Validation error]{self.__class__.__name__}: d={self.d}, D={self.D}, β={beta:.3f}")
            return False
        return True

    def get_geom_checks(self) -> dict:
        checks = {
            'Отклонение d': '≤ 0.2% от d',
            'Толщина EД': '≤ 0.05·D',
            'Вариация EД': '≤ 0.2 мм',
            'Длина e': f'{0.005 * self.D:.5f}…{0.02 * self.D:.5f} м (0.005·D…0.02·D)',
            'Вариация e': '≤ 0.001·D',
            'Параллельность оси': '±0.5°',
            'Угол наклона α': 'при EД>0.02·D: 30°…45°',
            'Диаметр d': 'параллельно оси ±0.5°, цилиндричность ±0.05%',
            'Отбор давления': 'угловой способ (п.4.1.11), Δp измерять у переднего и заднего торца'
        }
        return checks

    def check_Re(self) -> bool:
        beta = self.calculate_beta()
        Re_min = (43580 - 352612 * beta + 1090001 * beta**2 - 1453233 * beta**3 + 738677 * beta**4)
        Re_max = 500000 * beta**2
        if not (Re_min <= self.Re <= Re_max):
            logger.warning(
                f"[Re check] {self.__class__.__name__}: "
                f"Re={self.Re:.5f} вне [{Re_min:.5f}; {Re_max:.5f}]"
            )
            return False
        return True

    def calculate_C(self) -> float:
        """п.8.1"""
        E = self.calculate_E()
        beta = self.calculate_beta()
        return (0.6836 + 0.243 * beta**3.64) * (1 / E)

    # def discharge_coefficient_uncertainty(self) -> float:
    #     """
    #     Относительная погрешность коэффициента истечения
    #     """
    #     return 0.5

    def calculate_epsilon(self, delta_p: float, k: float) -> float:
        """п.8.2"""
        beta = self.calculate_beta()
        ratio = delta_p / self.p
        if ratio > 0.25:
            logger.error(f"[Epsilon error] Δp/p = {ratio:.3f} > 0.25 — расчёт невозможен")
            raise ValueError("Δp/p > 0.25")
        return 1 - (0.41 + 0.35 * beta**4) * ratio / k

    # def expansion_coefficient_uncertainty(self, dp_p: float) -> float:
    #     """
    #     Относительная погрешность
    #     """
    #     beta = self.calculate_beta()
    #     if beta <= 0.75: n = 2
    #     elif beta > 0.75: n = 4
    #     return n * dp_p

    def pressure_loss(self, delta_p: float) -> float:
        """(8.3)"""
        beta = self.calculate_beta()
        return (0.99 - 1.17 * beta**2) * delta_p
