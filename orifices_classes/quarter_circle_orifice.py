from .base_orifice import BaseOrifice
import math

class QuarterCircleOrifice(BaseOrifice):
    """
    Диафрагма "четверть круга"
    """
    def __init__(self, D: float, d: float, Re: float, p1: float, **kwargs):
        super().__init__(D, d, Re)
        self.p1 = p1
        beta = d / D
        self.set_beta(beta)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        # 11.2 базовые проверки D, d, β (делаем через диапазоны)
        if not (0.015 <= self.d <= 0.6 and 0.025 <= self.D <= 0.5 and 0.245 <= beta <= 0.6):
            print(f"[Validation error]{self.__class__.__name__}: D={self.D:.3f}, d={self.d:.3f}, β={beta:.3f}")
            return False
        return True

    def get_geom_checks(self) -> dict[str, str]:
        checks = {}
        # 11.3.1.1 Длина e ≥ 2.5 мм и ≤ 0.1·D
        e_min = 0.0025
        e_max = 0.1 * self.D
        checks['Длина отверстия e'] = f'{e_min:.4f}…{e_max:.5f} м (≥2.5 мм, ≤0.1·D)'
        # 11.3.1.2 При r>0.1·D уменьшать Ed до r или 0.1·D; описание
        checks['Обработка Ed при большом r'] = (
            'если r>0.1·D: удалить металл до r; если Ed>r: скруглить выходной торец Ø1.5d под 45°'
        )
        # 11.3.1.3 Вариация e
        checks['Вариация e'] = '≤ 0.001·D (D>200 мм) или ≤ 0.2 мм (D≤200 мм)'
        # 11.3.2 Профиль входного отверстия
        checks['Профиль радиус r'] = (
            'r = 3.17e-6·d·e^(16.8β) + 0.0554·d·e^(1.016β) + 0.029·d; ±1 %'
        )
        checks['Касательная к профилю'] = 'перпендикулярна торцу ±1°'
        checks['Кромки и профиль'] = 'острые, без заусенцев и неровностей'
        # 11.3.3 Диаметр d
        checks['Диаметр d'] = 'соосность ±0.5 °, цилиндричность ±0.05 %'
        # 11.3.4 Отбор давления
        checks['Отбор давления'] = 'угловой способ (п.4.1.11); фланцевый (D>40 мм, ГОСТ 8.586.2 п.5.2.2)'
        return checks
    def check_Re(self) -> bool:
        beta = self.calculate_beta()
        Re_min = 1000 * beta + 9.4e6 * (beta - 0.24)**8
        Re_max = 1e5 * beta
        if not (Re_min <= self.Re <= Re_max):
            print(f"[Re check] {self.__class__.__name__}: Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]")
            return False
        return True

    def calculate_C(self) -> float:
        """Коэффициент истечения п.11.4.1"""
        beta = self.calculate_beta()
        return (0.73823 + 0.3309 * beta - 1.1615 * beta**2 + 1.5084 * beta**3)

    # todo потом можно вкл
    # def delta_C(self) -> float:
    #     """Относительная погрешность п.11.4.1"""
    #     beta = self.calculate_beta()
    #     return 0.025 if beta <= 0.316 else 0.02

    def calculate_epsilon(self, delta_p: float, k: float) -> float:
        """Коэффициент расширения п.11.4.2"""
        if delta_p / self.p1 > 0.25:
            raise ValueError("Δp/p1 > 0.25")
        beta = self.calculate_beta()
        term = (0.351 + 0.256 * beta**4 + 0.93 * beta**8)
        return 1 - term * (1 - (1 - delta_p / self.p1)**(1/k))

    # todo потом можно вкл
    # def delta_epsilon(self, delta_p: float, k: float) -> float:
    #     """Относительная погрешность п.11.4.2"""
    #     return 3.5 * (delta_p / (k * self.p1))

    def pressure_loss(self, delta_p: float) -> float:
        """п.11.5"""
        beta = self.calculate_beta()
        return (1 - beta**1.9) * delta_p
