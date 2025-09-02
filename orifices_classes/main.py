import inspect
from enum import Enum
from logger_config import get_logger

from .sharp_edge_orifice     import SharpEdgeOrifice
from .conical_inlet_orifice  import ConicalInletOrifice
from .wear_resistant_orifice import WearResistantOrifice
from .double_orifice         import DoubleOrifice
from .segment_orifice        import SegmentOrifice
from .eccentric_orifice      import EccentricOrifice
from .quarter_circle_orifice import QuarterCircleOrifice
from .quarter_circle_nozzle  import QuarterCircleNozzle
from .cylindrical_nozzle     import CylindricalNozzle
from .wedge_flow_meter       import WedgeFlowMeter
from .cone_flow_meter        import ConeFlowMeter

class OrificeType(Enum):
    SHARP = "sharp"
    CONICAL = "conical"
    WEAR = "wear"
    DOUBLE = "double"
    SEGMENT = "segment"
    ECCENTRIC = "eccentric"
    QUARTER = "quarter"
    QUARTER_NOZZLE = "quarter_nozzle"
    CYLINDRICAL_NOZZLE = "cylindrical"
    WEDGE = "wedge"
    CONE = "cone"

_mapping = {
    OrificeType.SHARP:              SharpEdgeOrifice,
    OrificeType.CONICAL:            ConicalInletOrifice,
    OrificeType.WEAR:               WearResistantOrifice,
    OrificeType.DOUBLE:             DoubleOrifice,
    OrificeType.SEGMENT:            SegmentOrifice,
    OrificeType.ECCENTRIC:          EccentricOrifice,
    OrificeType.QUARTER:            QuarterCircleOrifice,
    OrificeType.QUARTER_NOZZLE:     QuarterCircleNozzle,
    OrificeType.CYLINDRICAL_NOZZLE: CylindricalNozzle,
    OrificeType.WEDGE:              WedgeFlowMeter,
    OrificeType.CONE:               ConeFlowMeter,
}

def create_orifice(name: str | OrificeType, **kwargs):
    if isinstance(name, str):
        name = OrificeType(name.lower())

    cls = _mapping[name]
    sig = inspect.signature(cls.__init__)
    init_args = {
        k: v for k, v in kwargs.items()
        if k in sig.parameters and k != "self"
    }
    inst = cls(**init_args)
    if not inst.validate():
        raise ValueError(f"Валидация геометрии ССУ '{name.value}' не пройдена")
    return inst

def run_orifice(orifice, delta_p: float, **kwargs) -> dict:
    out = orifice.run_all(delta_p, **kwargs)
    if not orifice.check_Re():
        raise ValueError(f"Re для {orifice.__class__.__name__} вне допустимого диапазона")
    return out

# def run_orifice(orifice, delta_p: float, **kwargs) -> dict:
#     out = orifice.run_all(delta_p, **kwargs)
#     if not orifice.check_Re():
#         raise ValueError(f"Re для {orifice.__class__.__name__} вне допустимого диапазона")
#     return out


# def run_orifice(orifice, delta_p: float, **kwargs) -> dict:
#     return orifice.run_all(delta_p, **kwargs)
