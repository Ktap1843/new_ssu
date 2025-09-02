from typing import Callable, Union
from orifices_classes.main import create_orifice
from orifices_classes.main import OrificeType
from orifices_classes.base_orifice import BaseOrifice


def get_check_re(
        orifice_type: Union[str, OrificeType], D: float, d: float, Re: float, **kwargs) -> Callable[[], bool]:
    orifice: BaseOrifice = create_orifice(orifice_type, D=D, d=d, Re=Re, **kwargs)
    return orifice.check_Re