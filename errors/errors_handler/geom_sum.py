from math import sqrt
from typing import Union, Sequence

def geometric_sum(*vals: Union[float, Sequence[float]]) -> float:
    if len(vals) == 1 and isinstance(vals[0], (list, tuple)):
        values = vals[0]
    else:
        values = vals
    clean = []
    for v in values:
        try:
            x = float(v)
            if x == x:  # фильтр NaN
                clean.append(x)
        except Exception:
            pass
    return sqrt(sum(x*x for x in clean))