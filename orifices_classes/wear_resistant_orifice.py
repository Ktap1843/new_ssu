from .base_orifice import BaseOrifice

class WearResistantOrifice(BaseOrifice):
    """
    Износоустойчивая диафрагма
    """
    def __init__(self, D: float, d: float, Re: float, p: float, dp: float, k: float):
        super().__init__(D, d, Re)
        self.p = p
        self.dp = dp
        self.k = k


    def _beta_from_geometry(self):
        return round(self.d / self.D, 12)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        # базовые геометрические ограничения п.7.2
        if not (0.016 <= self.d <= 0.8 and 0.03 <= self.D <= 1.0 and 0.22 <= beta <= 0.8):
            print(f"[Validation error]{self.__class__.__name__}: D={self.D}, d={self.d}, β={beta:.3f}")
            return False
        # # 7.3.1.1 Толщина Ed ≤ 0.05·D
        # if self.Ed is not None and self.Ed > 0.05 * self.D:
        #     print(f"[Validation error]{self.__class__.__name__}: Ed={self.Ed:.5f} > 0.05·D={0.05 * self.D:.5f}")
        #     return False
        # # 7.3.1.2 Длина цилиндрической части e ∈ [0.005·D; 0.02·(D - 0.0125)]
        # if self.e is not None:
        #     e_min = 0.005 * self.D
        #     e_max = 0.02 * max(self.D - 0.0125, 0)
        #     if not (e_min <= self.e <= e_max):
        #         print(f"[Validation error]{self.__class__.__name__}: e={self.e:.5f} вне [{e_min:.5f}; {e_max:.5f}]")
        #         return False
        # # 7.3.2 Угол наклона α при Ed > 0.02·(D - 0.0125)
        # threshold = 0.02 * max(self.D - 0.0125, 0)
        # if self.Ed is not None and self.Ed > threshold:
        #     if self.alpha is None:
        #         print(f"[Validation error]{self.__class__.__name__}: alpha не задан при Ed > {threshold:.5f}")
        #         return False
        #     if not (44 <= self.alpha <= 46):
        #         print(f"[Validation error]{self.__class__.__name__}: alpha={self.alpha:.1f}° вне [44; 46]")
        #         return False
        # # 7.3.5.1 Глубина фаски b
        # if self.b is not None:
        #     if self.d <= 0.125:
        #         b_nom = 0.25 * self.d
        #         tol = 0.0005 * self.d
        #     else:
        #         num = self.d ** 2
        #         den = 13 * self.d - 1.0
        #         b_nom = 0.25 * num / den
        #         tol = 0.002 * num / den
        #     if not (b_nom - tol <= self.b <= b_nom + tol):
        #         print(f"[Validation error]{self.__class__.__name__}: b={self.b:.5f} вне {b_nom:.5f}±{tol:.5f}")
        #         return False
        # # 7.3.5.2 Угол фаски 45°±5°
        # if self.chamfer_angle is not None and not (40 <= self.chamfer_angle <= 50):
        #     print(f"[Validation error]{self.__class__.__name__}: chamfer_angle={self.chamfer_angle}° вне [40; 50]")
        #     return False
        return True

    def get_geom_checks(self) -> dict:
        checks = {}
        # 7.3.1.1 Толщина EД ≤ 0.05·D
        max_Ed = 0.05 * self.D
        checks['Толщина EД'] = f'≤ {max_Ed:.5f} м (0…0.05·D)'
        # 7.3.1.2 Длина e ∈ [0.005·D; 0.02·(D-0.0125)]
        e_min = 0.005 * self.D
        e_max = 0.02 * max(self.D - 0.0125, 0)
        checks['Длина цилиндрической части e'] = (
            f'{e_min:.5f}…{e_max:.5f} м (0.005·D…0.02·(D-0.0125))'
        )
        # 7.3.2 Угол α при EД > 0.02·(D-0.0125): 45°±1°
        threshold = 0.02 * max(self.D - 0.0125, 0)
        checks['Угол наклона α'] = (
            f'при EД > {threshold:.5f} м: 45° ±1°'
        )
        # 7.3.3 Кромки G, H, I
        checks['Кромки G,H,I'] = 'острые, без заусенцев и неровностей'
        # 7.3.4 Диаметр d
        checks['Диаметр d'] = 'параллельно оси ±0.5°, цилиндричность ±0.05%'
        # 7.3.5 Отбор давления
        checks['Отбор давления'] = 'угловой способ (п.4.1.11)'
        # 7.3.5.1 Глубина фаски b
        b_nom1 = '0.25·d ±0.0005·d при d≤125 мм'
        b_nom2 = '0.25·d²/(13d-1000) ±0.002·d²/(13d-1000) при d>125 мм'
        checks['Глубина фаски b'] = f'{b_nom1}; {b_nom2}'
        # 7.3.5.2 Угол фаски 45°±5°
        checks['Угол фаски'] = '45° ±5°'
        return checks

    def check_Re(self) -> bool:
        """
        п.7.2
        """
        beta = self.calculate_beta()
        if beta <= 0.316:
            Re_min = 2000
        else:
            Re_min = (183183 - 1204741 * beta + 2544031 * beta**2 - 1107419 * beta**3)
        Re_max = 1e7

        if not (Re_min <= self.Re <= Re_max):
            print(f"[Re check] {self.__class__.__name__}: "
                  f"Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]")
            return False
        return True

    def _Cc(self) -> float:
        beta = self.calculate_beta()
        #todo почему промежутки не сделали кв корень
        if beta <= 0.54:
            return 0.5950 + 0.04 * beta**2 + 0.3 * beta**4
        if beta <= 70:
            return 0.6100 - 0.055 * beta**2 + 0.45 * beta**4
        return 0.3495 + 1.4454 * beta**2 - 2.4249 * beta**4 + 1.8333 * beta**6

    def calculate_C(self) -> float:
        """
        п.7.4.1
        """
        d_mm = self.d * 1000
        Cc = self._Cc()
        E = self.calculate_E()
        invE = 1 / E
        if 16 <= d_mm <= 125:
            return (1.0068 + 1.03585/d_mm) * Cc * invE
        return (0.99626 + 3.2554/d_mm - 124.627/d_mm**2) * Cc * invE

    def discharge_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность коэффициента истечения
        """
        beta = self.calculate_beta()
        if beta <= 0.63:
            return 0.2
        elif beta > 0.63:
            return 0.8 * beta**2 - 0.1

    def calculate_epsilon(self) -> float:
        """
        п.7.4.2
        """
        dp_p = self.dp / self.p
        beta = self.calculate_beta()
        if dp_p > 0.25:
            raise ValueError("Δp/p > 0.25")
        return 1 - (0.351 + 0.256 * beta**4 + 0.93 * beta**8) * (1 - (1 - dp_p)**(1/self.k))

    def expansion_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность
        """
        return 3.5 * (self.dp / (self.k * self.p))

    def pressure_loss(self) -> float:
        beta = self.calculate_beta()
        return (0.98 - 0.96*beta**2) * self.dp
