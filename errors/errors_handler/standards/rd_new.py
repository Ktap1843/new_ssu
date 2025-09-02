from .base import BaseStandard
from logger_config import get_logger

log = get_logger("RD_2025-class-to-rel-prcnt")

class RD_2025(BaseStandard):
    """
    Перевод погрешности к относительной (в %), по твоей формуле:
      - RelErr: вернуть как есть (считаем, что это уже проценты)
      - AbsErr: δ% = |Δ| / |x| * 100
      - FidErr: δ% = (приведённая в %) * (размах диапазона / |x|)
                 (err_value трактуем как проценты от диапазона)
    """
    def to_rel_percent(self, error_type: str, err_value: float, *,
                       value: float | None = None,
                       range_span: float | None = None) -> float:
        if error_type == "RelErr":
            return float(err_value)

        if error_type == "AbsErr":
            if value in (None, 0):
                raise ValueError("Нельзя перевести AbsErr в относительную при value is None или 0.")
            return abs(err_value) / abs(value) * 100.0

        if error_type == "FidErr":
            if value in (None, 0):
                raise ValueError("Для FidErr требуется value ≠ 0.")
            if not range_span:
                raise ValueError("Для FidErr требуется range_span (max - min).")
            return abs(err_value) * (abs(range_span) / abs(value))

        raise ValueError(f"Неизвестный тип погрешности: {error_type}")
