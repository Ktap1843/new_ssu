from .base_orifice import BaseOrifice
import math
import logging

logger = logging.getLogger(__name__)

class ConeFlowMeter(BaseOrifice):
    """
    Конусный преобразователь расхода
    """
    def __init__(self, D: float, d: float, Re: float, alpha: float, p: float, **kwargs):
        super().__init__(D, d, Re)
        self.alpha = alpha
        self.p = p
        # todo = d_k(делал как d -- нужно ли поправку по температуре делать) / D

    def _beta_from_geometry(self):
        return (1 - (self.d / self.D)**2)**0.5

    def _validate(self) -> bool:
        tests = []

        beta = self.calculate_beta()

        valid_D = 0.05 <= self.D <= 0.50
        tests.append(valid_D)
        if not valid_D:
            logger.warning(f"D={self.D * 1000:.1f} мм вне диапазона [50; 500] мм")

        valid_beta = 0.45 <= beta <= 0.75
        tests.append(valid_beta)
        if not valid_beta:
            logger.warning(f"β={beta:.3f} вне диапазона [0.45; 0.75]")

        # valid_alpha = self.alpha is not None and 10 <= self.alpha <= 60
        # tests.append(valid_alpha)
        # if not valid_alpha:
        #     logger.warning(f"угол α={self.alpha}° вне диапазона [10; 60]°")

        return all(tests)

    def get_geom_checks(self) -> dict:
        return {}

    def check_Re(self) -> bool:
        Re_min = 8e4
        Re_max = 1.2e7
        if not (Re_min <= self.Re <= Re_max):
            logger.warning(
                f"{self.__class__.__name__}: Re={self.Re:.0f} вне диапазона [{Re_min:.0f}; {Re_max:.0f}]"
            )
            return False
        return True

    def calculate_C(self) -> float:
        """
        Коэффициент истечения C п.15.4.1
        """
        return 0.82

    def discharge_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность коэффициента истечения
        """
        return 5

    def calculate_epsilon(self, delta_p: float, p: float) -> float:  # TODO тут отредактировать нужно
        """
        Коэффициент расширения п.15.4.2
        """
        beta = self.calculate_beta()
        otn = delta_p / p
        if otn > 0.25:
            logger.error(f"dp/p = {otn:.2f} > 0.25 — недопустимо")
            raise ValueError("dp/p > 0.25")

        return 1 - (0.649 - 0.696 * beta**4) * otn

    def expansion_coefficient_uncertainty(self, delta_p: float, k: float) -> float:
        """
        Относительная погрешность
        """
        return (0.096 * delta_p) / (self.p * k)

    def pressure_loss(self, delta_p: float) -> float:
        """
        Потери давления п.15.5
        """
        beta = self.calculate_beta()
        return (1.09 - 0.813 * beta) * delta_p
