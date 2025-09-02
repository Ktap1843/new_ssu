#from .gost_611_2013 import GOST611_2013
#from .gost_611_2024 import GOST611_2024
from errors.errors_handler.standards.rd_new import RD_2025


STANDARD_REGISTRY = {
    #"611-2013": GOST611_old(),
    #"611-2024": GOST611_new(),
    "рд-2025": RD_2025(),
}


__all__ = ["STANDARD_REGISTRY", "GOST611_2013", "GOST611_2024", "RD_2025"]
