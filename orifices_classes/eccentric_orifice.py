from .base_orifice import BaseOrifice
import math

class EccentricOrifice(BaseOrifice):
    """
    Эксцентричная диафрагма
    """
    def __init__(self, D: float, d: float, Re: float, p1: float, Ra: float):
        super().__init__(D, d, Re)
        self.p1 = p1      # начальное давление
        self.Ra = Ra      # шероховатость трубопровода
        self.set_beta(d / D)
        # # Геометрические параметры
        # self.e = e
        # self.Ed = Ed
        # self.Ed_variation = Ed_variation
        # self.e_variation = e_variation
        # self.alpha = alpha
        # self.G = G
        # # Патрубок отбора давления
        # self.a = a
        # # Инверсивный поток
        # self.inversion = inversion  #bool


    def _validate(self) -> bool:
        #beta = self.calculate_beta()
        # Базовые ограничения по п.10.3 (диапазоны D, d, β уже проверяются в базовом классе)
        # 10.3.1.1 Толщина Ed ≤ 0.05·D
        # if self.Ed is not None and self.Ed > 0.05 * self.D:
        #     print(f"[Validation error]{self.__class__.__name__}: Ed={self.Ed:.6f} > 0.05·D={0.05 * self.D:.6f}")
        #     return False
        # # 10.3.1.2 Разность толщин
        # if self.Ed_variation is not None:
        #     max_var = 0.001 * self.D if self.D > 0.2 else 0.0002
        #     if self.Ed_variation > max_var:
        #         print(
        #             f"[Validation error]{self.__class__.__name__}: Ed_variation={self.Ed_variation:.6f} > {max_var:.6f}")
        #         return False
        # # 10.3.1.3 e ∈ [0.005·D; 0.02·D]
        # if self.e is not None:
        #     e_min, e_max = 0.005 * self.D, 0.02 * self.D
        #     if not (e_min <= self.e <= e_max):
        #         print(f"[Validation error]{self.__class__.__name__}: e={self.e:.6f} вне [{e_min:.6f}; {e_max:.6f}]")
        #         return False
        # # 10.3.1.4 Разность e
        # if self.e_variation is not None:
        #     if self.e_variation > 0.001 * self.D:
        #         print(
        #             f"[Validation error]{self.__class__.__name__}: e_variation={self.e_variation:.6f} > {0.001 * self.D:.6f}")
        #         return False
        # # 10.3.2 Угол alpha при Ed > 0.02·D
        # if self.Ed is not None and self.Ed > 0.02 * self.D:
        #     if self.alpha is None or not (45 - 15 <= self.alpha <= 45 + 15):
        #         print(f"[Validation error]{self.__class__.__name__}: alpha={self.alpha}° вне [30;60]")
        #         return False
        # # 10.3.3 Радиус кромки G
        # if self.G is not None:
        #     # G ≤ 0.0004·d
        #     if self.G > 0.0004 * self.d:
        #         print(
        #             f"[Validation error]{self.__class__.__name__}: G={self.G:.6f} > 0.0004·d={0.0004 * self.d:.6f}")
        #         return False
        # # 10.3.4 Диаметр патрубка a ∈ [0.003;0.01]
        # if self.a is not None and not (0.003 <= self.a <= 0.01):
        #     print(f"[Validation error]{self.__class__.__name__}: a={self.a:.3f} вне [0.003;0.01]")
        #     return False
        # # 10.3.5.3 Рекомендованная ориентация патрубков (рекомендация, не жёсткое правило)
        # # 10.3.6 Инверсивный поток: без конуса, Ed == e
        # if self.inversion is True:
        #     if self.alpha is not None:
        #         print(f"[Validation error]{self.__class__.__name__}: inversion - конусная часть не должна быть")
        #         return False
        #     if self.Ed is not None and self.e is not None and abs(self.Ed - self.e) > 1e-6:
        #         print(f"[Validation error]{self.__class__.__name__}: inversion - Ed={self.Ed:.6f} != e={self.e:.6f}")
        #         return False
        return True

    def get_geom_checks(self) -> dict[str, str]:
        checks = {}
        checks['Толщина EД'] = f'≤ {0.05 * self.D:.5f} м (0…0.05·D)'
        checks['Вариация EД'] = '≤ 0.001·D (D>200 мм) или ≤ 0.2 мм (D≤200 мм)'
        checks['Длина e'] = f'{0.005 * self.D:.5f}…{0.02 * self.D:.5f} м (0.005·D…0.02·D)'
        checks['Вариация e'] = '≤ 0.001·D'
        checks['Угол наклона α'] = 'при EД>0.02·D: 45° ±15°'
        checks['Кромки G,H,I'] = (
            'острые, без заусенцев; '
            'если r_кромки ≤0.0004·d — считается острой'
        )
        checks['Диаметр d'] = '0.46·D…0.84·D; цилиндричность ±0.05%; параллельно оси ±0.5°'
        checks['Отбор давления'] = (
            'угловой способ (ГОСТ 8.586.2 п.5.2.3); диаметр отвода 3…10 мм; '
            'расположение диаметрально противоположно касательной точке; '
            'рекомендуемый поворот на 30° от вертикали'
        )
        checks['Инверсивные потоки'] = 'без конической части; S=e; кромки по п.10.3.3'
        return checks

    def check_Re(self) -> bool:
        beta = self.calculate_beta()
        Re_min = 2e5 * beta**2
        Re_max = 1e6 * beta
        if not (Re_min <= self.Re <= Re_max):
            logger.warning(
                f"[Re check] {self.__class__.__name__}: "
                f"Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]"
            )
            return False
        return True

    def calculate_C(self) -> float:
        """Коэффициент истечения п.10.4.1"""
        E = self.calculate_E()
        beta = self.calculate_beta()
        C0 = 0.9355 - 1.6889 * beta + 3.0428 * beta**2 - 1.7989 * beta**3
        RaD = self.Ra / self.D
        try:
            FE = 1.032 + 0.0178 * math.log10(RaD) + 0.0939 * beta**2 * math.log10(RaD)
        except ValueError as e:
            logger.error(f"Ошибка логарифма log10(Ra/D): Ra={self.Ra}, D={self.D} → {e}")
            raise
        return C0 * FE / E

    def calculate_epsilon(self, delta_p: float, k: float) -> float:
        """Коэффициент расширения п.10.4.2"""
        ratio = delta_p / self.p1
        if ratio > 0.25:
            logger.error(f"[Epsilon error] Δp/p1 = {ratio:.3f} > 0.25 — расчёт невозможен")
            raise ValueError("Δp/p1 > 0.25")
        beta = self.calculate_beta()
        return 1 - (0.351 + 0.256 * beta**4 + 0.93 * beta**8) * (1 - ratio**(1/k))

    def pressure_loss(self, delta_p: float) -> float:
        """Потери давления п.10.5"""
        beta = self.calculate_beta()
        return (1 - beta**1.9) * delta_p
