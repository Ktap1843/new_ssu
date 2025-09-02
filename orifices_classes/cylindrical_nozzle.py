from .base_orifice import BaseOrifice
import math
import logging
from orifices_classes.orifices_geometry_helpers.cylindrical_nozzle import calc_cylindrical_geometry

logger = logging.getLogger(__name__)

class CylindricalNozzle(BaseOrifice):
    """
    Цилиндрическое сопло
    """
    def __init__(self, D: float, d: float, Re: float, p1: float, **kwargs):
        super().__init__(D, d, Re)
        self.p1 = p1
        self.set_beta(d / D)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        if not (0.025 <= self.D <= 0.1 and 0.01 <= self.d <= 0.07 and 0.1 <= beta <= 0.7):
            logger.warning(f"[Validation error]{self.__class__.__name__}: D={self.D}, d={self.d}, β={beta}")
            return False
        return True

    def get_geom_checks(self) -> dict:
        beta = self.calculate_beta()
        try:
            return calc_cylindrical_geometry(self.D, self.d, beta)
        except Exception as e:
            logger.warning("Ошибка при проверке геометрии цилиндрического сопла")
            return {"error": str(e)}

    def check_Re(self) -> bool:
        beta = self.calculate_beta()

        Re_min = (-1156 + 30601 * beta - 200329 * beta**2 + 706003
                   * beta**3 - 1136584 * beta**4 + 679071  * beta**5)
        Re_max = (-48584 + 883500 * beta - 3925315 * beta**2
                   + 7991498 * beta**3 - 4945477 * beta**4)

        if not (Re_min <= self.Re <= Re_max):
            logger.warning(
                f"[Re check] {self.__class__.__name__}: "
                f"Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]"
            )
            return False
        return True

    def calculate_C(self) -> float:
        """п.13.4.1"""
        E = self.calculate_E()
        beta = self.calculate_beta()
        return (0.80017 - 0.01801 * beta**2 + 0.7022 * beta**4 - 0.322 * beta**6) * (1 / E)

    def calculate_epsilon(self, delta_p: float, k: float) -> float:
        """п.13.4.2"""
        ratio = delta_p / self.p1
        if ratio > 0.25:
            logger.error("Δp/p1 > 0.25 — расчёт ε невозможен")
            raise ValueError("Δp/p1 > 0.25")
        phi = 1 - ratio
        beta = self.calculate_beta()
        term1 = phi**(2 / k)
        term2 = k / (k - 1)
        term3 = (1 - phi**((k - 1) / k)) / ratio
        term5 = (1 - beta**4) / (1 - beta**4 * phi**(2 / k))
        return math.sqrt(term1 * term2 * term3 * term5)

    def pressure_loss(self, delta_p: float) -> float:
        """п.13.5"""
        beta = self.calculate_beta()
        return (1 - 1.47 * beta**2 + 0.65 * beta**4) * delta_p
