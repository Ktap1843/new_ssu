from .base import BaseCalculator
from logger_config import get_logger

log = get_logger("CorrectorCalculator")

class CorrectorCalculator(BaseCalculator):
    def _validate_common(self):
        super()._validate_common()
        # корректоры считаем ТОЛЬКО для относительных ошибок
        if self.payload["error_type"] != "RelErr":
            raise ValueError("CorrectorCalculator поддерживает только 'RelErr'.")
        # value для RelErr не нужен — убираем проверку на его наличие

    def extract_context(self):
        # Контекст не требуется для RelErr
        return None, None