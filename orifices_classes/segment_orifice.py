from .base_orifice import BaseOrifice
import math
from logger_config import get_logger

logger = get_logger("SegmentOrifice")

class SegmentOrifice(BaseOrifice):
    """
    Сегментная диафрагма
    """
    def __init__(self, D: float, d: float, Re: float, p: float):
        super().__init__(D, d, Re)
        self.d = d  #считаю H, как d т.к. запрашиваем из одного окна на форме
        self.p = p



    def _beta_from_geometry(self):
        x = 1 - 2 * self.d / self.D
        return math.sqrt( (math.acos(x) / math.pi) - (x / math.pi) * math.sqrt(1 - x**2) )

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        # (п.9.2)
        Hd = self.d / self.D
        if not (0.05 <= self.D <= 1.0 and 0.00798 <= self.d <= 0.49207 and
                0.158 <= Hd <= 0.492 and 0.32 <= beta <= 0.7):
            logger.error(f"[Validation error]{self.__class__.__name__}: D={self.D}, H={self.d}, H/D={Hd:.3f}, β={beta:.3f}")
            return False
        # # 9.3.1.1 Толщина Ed ≤ 0.05·D
        # if self.Ed is not None and self.Ed > 0.05 * self.D:
        #     print(f"[Validation error]{self.__class__.__name__}: Ed={self.Ed:.5f} > 0.05·D={0.05 * self.D:.5f}")
        #     return False
        # # 9.3.1.2 Длина e ∈ [0.005·D; 0.02·D]
        # if self.e is not None:
        #     e_min, e_max = 0.005 * self.D, 0.02 * self.D
        #     if not (e_min <= self.e <= e_max):
        #         print(f"[Validation error]{self.__class__.__name__}: e={self.e:.5f} вне [{e_min:.5f}; {e_max:.5f}]")
        #         return False
        # # 9.3.2 Угол phi при Ed > 0.02·D
        # threshold = 0.02 * self.D
        # if self.Ed is not None and self.Ed > threshold:
        #     if self.phi is None or not (30 <= self.phi <= 45):
        #         print(f"[Validation error]{self.__class__.__name__}: phi={self.phi}° вне [30;45]")
        #         return False
        # # 9.3.3 Проверка H: если theta задан, альтернативный расчет H по θ (п.9.3.5.2)
        # if self.theta is not None:
        #     H_calc = (self.D / 2) * (1 - math.cos(math.radians(self.theta / 2)))
        #     # допускаем небольшое отклонение
        #     tol = 0.001 * self.D
        #     if abs(self.H - H_calc) > tol:
        #         print(f"[Validation error]{self.__class__.__name__}: H={self.H:.5f} ≠ {H_calc:.5f} по θ±{tol:.5f}")
        #         return False
        # # 9.3.4 нет кодируемых ограничений тут
        return True

    def get_geom_checks(self) -> dict:
        checks = {}
        # 9.3.1.1
        max_Ed = 0.05 * self.D
        checks['Толщина EД'] = f'≤ {max_Ed:.5f} м (0…0.05·D)'
        # 9.3.1.2
        e_min = 0.005 * self.D
        e_max = 0.02 * self.D
        checks['Длина цилиндрической части e'] = (
            f'{e_min:.5f}…{e_max:.5f} м (0.005·D…0.02·D)'
        )
        # 9.3.2
        thresh = 0.02 * self.D
        checks['Угол наклона φ'] = f'при EД > {thresh:.5f} м: 30°…45°'
        # 9.3.3
        h_calc = (self.D * (0.04605 + 1.1997 * self.calculate_beta() ** 2
                            - 0.9637 * self.calculate_beta() ** 4
                            + 0.7612 * self.calculate_beta() ** 6))
        checks['Высота сегмента H'] = (
            f'по β: {h_calc:.5f} м (формула 9.2); по θ и D: H = D / 2·(1 - cos(θ / 2))(формула 9.3)' )
        # 9.3.4
        checks['Ось отверстия'] = 'параллельно оси ±0.5°'
        checks['Отбор давления'] = 'угловой способ (п.4.1.11), отверстия с противоположной стороны, отклонение ±10°'
        # 9.3.5
        checks['Площадь сегмента f'] = 'f = D²/8·(θ·π/180 - sinθ) (формула 9.4)'
        return checks

    def check_Re(self) -> bool:
        """п.9.2"""
        beta = self.calculate_beta()
        Re_min = 41270 - 257222 * beta + 525533 * beta**2 - 232389 * beta**3
        Re_max = 1e6
        if not (Re_min <= self.Re <= Re_max):
            logger.error(f"[Re check] {self.__class__.__name__}: "
                  f"Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]")
            return False
        return True

    def calculate_C(self) -> float:
        """Коэффициент истечения п.9.4.1"""
        beta = self.calculate_beta()
        E = self.calculate_E()
        return (0.6085 - 0.03427 * beta**2 + 0.3237 * beta**4 + 0.00695 * beta**6) * (1/E)

    # def delta_C(self) -> float:
    #     """Относительная погрешность п.9.4.1"""
    #     beta = self.calculate_beta()
    #     return 0.6 + 1.5 * beta**4

    def calculate_epsilon(self, delta_p: float, k: float) -> float:
        """Коэффициент расширения п.9.4.2"""
        if delta_p / self.p > 0.25:
            raise ValueError("Δp/p > 0.25")
        beta = self.calculate_beta()
        return 1 - (0.41 + 0.351 * beta**4) * delta_p / k / self.p

    # def delta_epsilon(self, delta_p: float) -> float:
    #     """Относительная погрешность п. 9.4.2"""
    #     return 4 * (delta_p / self.p)

    def pressure_loss(self, delta_p: float) -> float:
        """Потери давления п.9.5"""
        beta = self.calculate_beta()
        return (0.98 - 0.96*beta**2) * delta_p
