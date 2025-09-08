from .base_orifice import BaseOrifice
import math

from logger_config import get_logger

logger = get_logger("WedgeFlowMeter")

class WedgeFlowMeter(BaseOrifice):
    """Клиновый преобразователь расхода"""
    def __init__(self, D: float, d: float, Re: float, k:float, delta_p:float):
        super().__init__(D, d, Re)
        self.k = k
        self.delta_p = delta_p


    def _beta_from_geometry(self):
        x = 1 - 2 * self.d / self.D
        return math.sqrt( (math.acos(x) / math.pi) - (x / math.pi) * math.sqrt(1 - x**2) )

    def _validate(self) -> bool:
        """
        (п.14.2)
        """
        beta = self.calculate_beta()
        cond_geom = (
            0.05 <= self.D <= 0.6 and
            0.2  <= (self.d / self.D) <= 0.6 and
            0.377 <= beta <= 0.791
        )
        if not cond_geom:
            logger.error(f"[Validation error] {self.__class__.__name__}: "
                  f"D={self.D}, h={self.d}, h/D={self.d/self.D}, β={beta}")
            return False
        return True

    def get_geom_checks(self) -> dict:
        return {}

    def check_Re(self) -> bool:
        """(п.14.2)"""
        Re_min, Re_max = 1e4, 9e6
        if not (Re_min <= self.Re <= Re_max):
            logger.error(f"[Re check] {self.__class__.__name__}: "
                  f"Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]")
            return False
        return True

    def calculate_C(self) -> float:
        """C (п.14.4.1)"""
        beta = self.calculate_beta()
        return 0.77 - 0.09 * beta

    def discharge_coefficient_uncertainty(self) -> float:
        """Относительная погрешность п.9.4.1"""
        return 4

    def calculate_epsilon(self, delta_p: float, p: float) -> float:
        """ε (п.14.4.2)"""
        dp_p = delta_p / p
        if dp_p > 0.25:
            raise ValueError("dp/p > 0.25")
        beta = self.calculate_beta()
        term1 = self.k * (1 - dp_p) ** (2 / self.k) / (self.k - 1)
        term2 = (1 - beta**4) / (1 - beta**4 * (1 - dp_p) ** (2 / self.k))
        term3 = (1 - (1 - dp_p) ** ((self.k - 1) / self.k)) / dp_p
        return math.sqrt(term1 * term2 * term3)

    def expansion_coefficient_uncertainty(self) -> float:
        """Относительная погрешность"""
        return (1 - (1 - self.delta_p / self.p)) / 3

    def pressure_loss(self, dp: float) -> float:
        """(п.14.5)"""
        beta = self.calculate_beta()
        return (1.09 - 0.79 * beta) * dp
