from .base_orifice import BaseOrifice
import math

class SharpEdgeOrifice(BaseOrifice):
    """
    Диафрагма с прямоугольным входом
    """
    def __init__(self, D: float, d: float, Re: float, p: float):
        super().__init__(D, d, Re)
        self.p = p
        self.set_beta(d / D)


    def _validate(self) -> bool:
        """
        п.5.3
        """
        beta = self.calculate_beta()
        if not (0.014 <= self.D <= 0.05 and 0.007 <= self.d <= 0.04):
            print(f"[Validation error]{self.__class__.__name__}: D={self.D} или d={self.d} вне диапазона")
            return False
        return True

    def get_geom_checks(self) -> dict[str, str]:
        checks = {}
        max_Ed = 0.05 * self.D
        checks['Толщина EД'] = f'≤ {max_Ed:.5f} м (0…0.05·D)'
        e_min = 0.005 * self.D
        e_max = 0.02 * self.D
        checks['Длина цилиндрической части e'] = (
            f'{e_min:.5f}…{e_max:.5f} м (0.005·D…0.02·D)'
        )
        # Угол α
        threshold = 0.02 * self.D
        checks['Угол наклона α'] = (f'при EД > {threshold:.5f} м: 30°…45°')
        checks['Кромки G, H, I'] = 'острые, без заусенцев и неровностей'
        checks['Диаметр d'] = 'параллельно оси ±0.5°, цилиндричность ±0.05%'
        checks['Отбор давления'] = 'угловой способ (п.4.1.11)'
        return checks

    def check_Re(self) -> bool:
        beta = self.calculate_beta()
        Re_min = 8.4e5 * beta ** 2 - 4.5e5 * beta + 0.86e5
        Re_max = 1e7
        if not (Re_min <= self.Re <= Re_max):
            print(
                f"[Validation error]{self.__class__.__name__}: "
                f"Re={self.Re:.0f} вне допустимого диапазона "
                f"[{Re_min:.0f}; {Re_max:.0f}]"
            )
            return False
        return True

    def _Cc(self) -> float:
        #todo тут тоже промежутки поправить
        beta = self.calculate_beta()
        if beta <= 0.55:
            return 0.5950 + 0.2 * beta + 0.547 * beta**2
        if beta <= 0.71:
            return 0.6100 - 0.235 * beta + 0.671 * beta**2
        return 0.3495 + 1.202 * beta - 1.557 * beta**2 + 1.354 * beta**3

    def calculate_C(self, *args, **kwargs) -> float:
        """(5.2),(5.3)"""
        d_mm = self.d * 1000
        Cc = self._Cc()
        E = self.calculate_E()
        invE = 1 / E
        if d_mm > 10:
            return (0.99626 + 0.260435 / d_mm - 0.79761 / d_mm**2 + 1.13279 / d_mm**3) * Cc * invE
        if 7 <= d_mm <= 10:
            return (1.0068 + 0.08287 / d_mm) * Cc * invE
        raise ValueError(f"Недопустимый d_mm={d_mm}")

    def calculate_epsilon(self, delta_p: float, k: float, *args, **kwargs) -> float:
        """п.5.6"""
        beta = self.calculate_beta()
        ratio = delta_p / self.p
        if ratio > 0.25:
            raise ValueError("Δp/p > 0.25")
        return 1 - (0.41 + 0.35 * beta**4) * ratio / k

    def pressure_loss(self, delta_p: float, *args, **kwargs) -> float:
        """п.5.5"""
        beta = self.calculate_beta()
        return (0.98 - 0.96 * beta**2) * delta_p
