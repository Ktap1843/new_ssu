from dataclasses import dataclass
from typing import Literal, Optional, Tuple

ErrorType = Literal["AbsErr", "RelErr", "FidErr"]
StandardId = Literal["рд-2025"]

@dataclass(frozen=True)
class Context:
    """
    Доп. контекст для перевода в относительную погрешность (по необходимости).
    - value: измеренное значение x (нужно для AbsErr, FidErr)
    - range_span: размах диапазона (max - min), нужен для FidErr
    """
    value: Optional[float] = None
    range_span: Optional[float] = None  # (max - min)

@dataclass(frozen=True)
class Inputs:
    error_type: ErrorType
    main: float
    additional: float
    standard: StandardId
    # Контекст опционален — «простой» режим = None
    context: Optional[Context] = None

@dataclass(frozen=True)
class Result:
    main_rel: float       # %
    additional_rel: float # %
    total_rel: float      # %
