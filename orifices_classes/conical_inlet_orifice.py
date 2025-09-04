from .base_orifice import BaseOrifice
import math
import numpy as np
from logger_config import get_logger
from orifices_classes.orifices_geometry_helpers.conical_inlet import calc_e1_nominal, calc_e_nominal, calc_e_tol, calc_f_angle

logger = get_logger("ConicalInletOrifice")

class ConicalInletOrifice(BaseOrifice):
    """
    Диафрагма с коническим входом
    """
    ##Табл 5
    _BETAS = np.array([...])  # укорочено
    _F_DEGREES = np.array([...])
    _D_OVER_E1 = np.array([...])

    def __init__(self, D: float, d: float, Re: float, p: float, k: float, **kwargs):
        self.D = D
        self.d = d
        self.k = k
        super().__init__(self.D, self.d, Re)
        self.p = p
        beta = self.calculate_beta()

        #if self.D <= 0.1:
        #    self.alpha = float(np.interp(beta, self._BETAS, self._F_DEGREES))
        #    d_over_e1 = float(np.interp(beta, self._BETAS, self._D_OVER_E1))
        #    self.e1 = self.d / d_over_e1
        #else:
        #    self.e1 = 0.084 * self.d
        #    self.alpha = constr.get("alpha", 45.0)

        #self.e = 0.021 * self.d
        #self.e_tol = min(0.0025 * self.d, 0.00004)
        #self.S1 = constr.get("S1")
        #self.Ed = constr.get("Ed")


    def _beta_from_geometry(self):
        return round(self.d / self.D, 12)

    def _validate(self) -> bool:
        beta = self.calculate_beta()
        if not (0.025 <= self.D <= 0.5 and 0.006 <= self.d <= 0.05):
            logger.error(f"[Validation error]{self.__class__.__name__}: D={self.D:.4f}m или d={self.d:.4f}m вне диапазона")
            return False

        if self.D <= 0.1:
            if not (0.1 <= beta <= 0.5):
                logger.error(f"[Validation error]{self.__class__.__name__}: β={beta:.3f} вне [0.1; 0.5]")
                return False
        else:
            if not (0.1 <= beta <= 0.316):
                logger.error(f"[Validation error]{self.__class__.__name__}: β={beta:.3f} вне [0.1; 0.316]")
                return False
        return True

    def get_geom_checks(self) -> dict:
        checks = {}
        beta = self.calculate_beta()
        checks['Шероховатость Ra (D 12.5–100 мм)'] = 'по п.4.1.1'
        checks['Шероховатость Ra (100–500 мм)'] = '≤ 1e-4·d в круге Ø≥1.5d'

        try:
            if self.D <= 0.1:
                F_nom = calc_f_angle(beta, self._BETAS, self._F_DEGREES)
                checks['Угол F'] = f'{F_nom:.1f}° ±0.03° (табл.5)'

                e1_nom = calc_e1_nominal(self.d, beta, self._BETAS, self._D_OVER_E1)
                tol = 0.04 * e1_nom
                checks['Толщина e1'] = f'{e1_nom:.5f} ±{tol:.5f} м'
            else:
                checks['Угол F'] = '45° ±1°'
                checks['Толщина e1'] = f'0.084·d ±0.003·d'

            e_nom = calc_e_nominal(self.d)
            tol_e = calc_e_tol(self.d)
            checks['Длина e'] = f'{e_nom:.5f} ±{tol_e:.5f} м'

            checks['Толщина S1'] = '≤ 0.105·d'
            checks['Толщина EД'] = '≤ 0.1·D'
            checks['Выточка k'] = 'диаметр 2·d при Ed>e+e1'
            checks['Вариация EД1'] = '0.001·D (D≥200 мм) или 0.2 мм (D<200 мм)'
            checks['Допуск F'] = '±0.03°' if self.D <= 0.1 else '±1°'
            checks['Кромки G,H,I'] = 'острые, без заусенцев'
            checks['Диаметр d'] = 'соосно ±0.5°, цилиндричность ±0.05%'
            checks['Отбор давления'] = 'угловой способ (п.4.1.11)'

            return checks

        except Exception as e:
            logger.error("Ошибка при проверке геометрии диафрагмы с коническим входом")
            return {"error": str(e)}

    def check_Re(self) -> bool:
        beta = self.calculate_beta()
        if self.D <= 0.1:
            Re_min = 40 if beta <= 0.2 else (-40 + 933 * beta - 4000 * beta ** 2 + 6667 * beta ** 3)
            Re_max = 50000 if beta > 0.3 else (350000 * beta - 500000 * beta ** 2)
        else:
            Re_min, Re_max = 80, 2e5 * beta

        if not (Re_min <= self.Re <= Re_max):
            logger.error(f"[Validation error]{self.__class__.__name__}: Re={self.Re:.0f} вне [{Re_min:.0f}; {Re_max:.0f}]")
            return False
        return True

    def calculate_C(self) -> float:
        beta, E = self.calculate_beta(), self.calculate_E()
        if 0.0025 <= self.D <= 0.1:
            return (0.73095 + 0.2726 * beta ** 2 - 0.7138 * beta ** 4 + 5.0623 * beta ** 6) / E
        elif 0.1 < self.D <= 0.5:
            return 0.734

    def discharge_coefficient_uncertainty(self) -> float:
        """
        Относительная погрешность коэффициента истечения п. 6.4.1
        """
        if 0.0025 <= self.D <= 0.1:
            return 1
        elif 0.1 < self.D <= 0.5:
            return 2

    def calculate_epsilon(self, delta_p: float) -> float:
        x = delta_p / self.p
        if x > 0.25:
            logger.error("Δp/p > 0.25 — расчёт ε невозможен")
            raise ValueError("Δp/p > 0.25")
        beta = self.calculate_beta()
        if 0.00125 <= self.D <= 0.1:
            term = (1 - x) ** (2 / self.k)
            num = term * (self.k / (self.k - 1)) * (1 - (1 - x) ** ((self.k - 1) / self.k))
            frac = num / x * (1 - beta ** 4) / (1 - beta ** 4 * term)
            return 0.25 + 0.75 * math.sqrt(frac)
        return 1 - 0.351 * (1 - (1 - x) ** (1 / self.k))

    def expansion_coefficient_uncertainty(self, delta_p: float) -> float:
        """
        Относительная погрешность
        """
        x = delta_p / self.p
        beta = self.calculate_beta()
        if 0.1 < D <= 0.5:
            eps = self.calculate_epsilon(delta_p)
            return 33 * (1 - eps)
        elif 0.00125 <= self.D <= 0.1:
            ot_k = 2 / self.k#todo проверить формулу мб ошибка
            return 7.5 * (1 - ((1 - x)**ot_k * (self.k / (self.k - 1))
                               * ((1 - (1 - x)**((self.k - 1) / self.k)) / x)
                              * ((1 - beta**4) / ((1 - beta**4) * (1 - x)**ot_k)))**0.5)


    def pressure_loss(self, delta_p: float) -> float:
        beta = self.calculate_beta()
        return (0.99 - 1.32 * beta ** 2) * delta_p
