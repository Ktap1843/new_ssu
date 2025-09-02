import logging
from enum import Enum

from .sharp_edge_orifice import SharpEdgeOrifice
from .conical_inlet_orifice import ConicalInletOrifice
from .wear_resistant_orifice import WearResistantOrifice
from .double_orifice import DoubleOrifice
from .segment_orifice import SegmentOrifice
from .eccentric_orifice import EccentricOrifice
from .quarter_circle_orifice import QuarterCircleOrifice

logger = logging.getLogger(__name__)

class OrificeType(Enum):
    SHARP = "sharp"
    CONICAL = "conical"
    WEAR = "wear"
    DOUBLE = "double"
    SEGMENT = "segment"
    ECCENTRIC = "eccentric"
    QUARTER = "quarter"

def create_orifice(name: str | OrificeType, *args, **kwargs):
    """
    Создаёт экземпляр соответствующего класса диафрагмы по названию или Enum.

    :param name: Строка или OrificeType
    :param args: Аргументы конструктора
    :param kwargs: Именованные аргументы конструктора
    :return: Экземпляр диафрагмы или None при ошибке
    """
    try:
        if isinstance(name, str):
            try:
                name = OrificeType(name.lower())
            except ValueError:
                values = [e.value for e in OrificeType]
                msg = f"Неизвестный тип диафрагмы '{name}'. Возможные типы: {values}"
                logger.error(msg)
                raise ValueError(msg)

        mapping = {
            OrificeType.SHARP: SharpEdgeOrifice,
            OrificeType.CONICAL: ConicalInletOrifice,
            OrificeType.WEAR: WearResistantOrifice,
            OrificeType.DOUBLE: DoubleOrifice,
            OrificeType.SEGMENT: SegmentOrifice,
            OrificeType.ECCENTRIC: EccentricOrifice,
            OrificeType.QUARTER: QuarterCircleOrifice
        }

        cls = mapping.get(name)
        if cls is None:
            logger.error(f"Класс не найден для типа: {name}")
            return None

        return cls(*args, **kwargs)

    except Exception as e:
        logger.exception(f"Ошибка при создании экземпляра '{name}': {e}")
        return None
