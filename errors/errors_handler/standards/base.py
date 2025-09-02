from abc import ABC, abstractmethod

class BaseStandard(ABC):
    @abstractmethod
    def to_rel_percent(self, error_type: str, err_value: float,
                       *, value: float | None = None,
                       range_span: float | None = None) -> float:
        pass