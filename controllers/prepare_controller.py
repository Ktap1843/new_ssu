from typing import Optional
import math
from logger_config import get_logger

logger = get_logger("PreparedController")

#todo добавить перевод ед изм в необходимые величины которые использует стандарт
class PreparedController:
    """подготовка параметров к рассчету (перевод ед. изм.)"""
    def __init__( self, d: float, D: float, p1: float, t1: float, dp: float,
                  R: float = 8.314, Z: Optional[float] = 1.0):
        self.d = d
        self.D = D
        self.p1 = p1
        self.t1 = t1
        self.dp = dp
        self.R = R
        self.Z = Z or 1.0

        self.T1_K = self.celsius_to_kelvin(t1)
        self.beta = d / D

        self.validate()

    def celsius_to_kelvin(self, t: float) -> float:
        return t + 273.15

    def validate(self):
        if not (0 < self.d < self.D):
            logger.error("Ошибка валидации: d должно быть меньше D")
            raise ValueError("Диаметр d должен быть меньше D")
        if self.p1 <= 0:
            logger.error("Ошибка валидации: Давление должно быть положительным")
            raise ValueError("Давление должно быть положительным")
        if self.T1_K <= 0:
            logger.error("Ошибка валидации: Температура должна быть больше 0 К")
            raise ValueError("Температура должна быть больше 0 К")
        if self.dp <= 0:
            logger.error("Ошибка валидации: Перепад давления должен быть положительным")
            raise ValueError("Перепад давления должен быть положительным")
        if not (0 < self.beta < 1):
            logger.error("Ошибка валидации: Относительный диаметр должен быть в пределах от 0 до 1")
            raise ValueError("Относительный диаметр должен быть в пределах от 0 до 1")

        logger.info("Параметры успешно прошли валидацию")

    def as_dict(self):
        return {
            "d": self.d,
            "D": self.D,
            "beta": self.beta,
            "p1": self.p1,
            "T1_K": self.T1_K,
            "dp": self.dp,
            "Z": self.Z,
            "R": self.R
        }
