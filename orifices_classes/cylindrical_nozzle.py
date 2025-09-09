from .base_orifice import BaseOrifice
import math
from logger_config import get_logger
from orifices_classes.orifices_geometry_helpers.cylindrical_nozzle import calc_cylindrical_geometry

logger = get_logger("CylindricalNozzle")

class CylindricalNozzle(BaseOrifice):
    """
    Цилиндрическое сопло
    """
    def __init__(self, D: float, d: float, Re: float, p: float, dp: float, k: float, **kwargs):
        super().__init__(D, d, Re)
        self.k = k
        self.dp = dp
        self.p = p



    def _beta_from_geometry(self):
        return round(self.d / self.D, 12)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        if not (0.025 <= self.D <= 0.1 and 0.0025 <= self.d <= 0.07 and 0.1 <= beta <= 0.7):
            logger.error(f"[Validation error]{self.__class__.__name__}: D={self.D}, d={self.d}, β={beta}")
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
            logger.error(
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

    def discharge_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность коэффициента истечения
        """
        return 1

    def calculate_epsilon(self) -> float:
        """п.13.4.2"""
        ratio = self.dp / self.p
        if ratio > 0.25:
            logger.error("Δp/p > 0.25 — расчёт ε невозможен")
            raise ValueError("Δp/p > 0.25")
        phi = 1 - ratio
        beta = self.calculate_beta()
        term1 = phi**(2 / self.k)
        term2 = self.k / (self.k - 1)
        term3 = (1 - phi**((self.k - 1) / self.k)) / ratio
        term5 = (1 - beta**4) / (1 - beta**4 * phi**(2 / self.k))
        return math.sqrt(term1 * term2 * term3 * term5)

    def expansion_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность п 13.4.2
        """
        return 0

    def pressure_loss(self) -> float:
        """п.13.5"""
        beta = self.calculate_beta()
        return (1 - 1.47 * beta**2 + 0.65 * beta**4) * self.dp
