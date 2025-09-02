from .base_straightness import BaseStraightness
from logger_config import get_logger
from .rules_tables import (
    get_cone_length,
    get_length_after_ssu,
    get_relative_roughness,
    get_wedge_length,
    get_generic_ms_length,
    BETWEEN_MS_LENGTHS,
    get_min_between_ms_length
)

log = get_logger("CalcStraightness")

class CalcStraightness(BaseStraightness):
    """
    Расчёт длины прямолинейных участков ССУ по ГОСТ
    """

    def calculate(self):
        if not self.is_straightness_required():
            log.debug("Пропущен расчёт прямолинейных участков (skip_straightness=True)")
            return None

        if not (self.ssu_type and self.beta and self.D and self.Ra is not None):
            log.error("Недостаточно данных: ssu_type, beta, D или Ra отсутствует")
            return {"error": "Не хватает данных для расчёта (ssu_type, beta, D, Ra)"}

        log.info(f"Старт расчёта прямолинейных участков для ССУ '{self.ssu_type}'")
        log.debug(f"beta={self.beta}, D={self.D}, Ra={self.Ra}")
        log.debug(f"ms_before: {self.ms_before}")
        log.debug(f"ms_after: {self.ms_after}")

        try:
            length_1_to_ssu = 0
            length_between_ms = 0
            length_after = 0

            ms1 = self.ms_before[0]["type"] if len(self.ms_before) > 0 else None
            ms2 = self.ms_before[1]["type"] if len(self.ms_before) > 1 else None
            if self.ssu_type == "wedge" or self.ssu_type == "cone":
                ms2 = None

            if self.ssu_type == "wedge":
                if ms1:
                    length_1_to_ssu = get_wedge_length(ms1) or 0
                length_after = 6
                log.debug(f"WEDGE: {length_1_to_ssu * self.D} (1->ССУ), после = {length_after * self.D}")

            elif self.ssu_type == "cone":
                if ms1:
                    length_1_to_ssu = get_cone_length(self.beta, ms1) or 0
                length_after = 2
                log.debug(f"CONE: {length_1_to_ssu * self.D} (1->ССУ), после = {length_after * self.D}")

            else:
                if ms1:
                    length_1_to_ssu = get_generic_ms_length(self.beta, ms1) or 0
                if ms2:
                    length_between_ms = get_min_between_ms_length(ms1, ms2)
                if self.ms_after:
                    length_after_val = get_length_after_ssu(self.beta, prefer_ceiling=True)
                    length_after = (length_after_val or 0) * self.D
                else:
                    length_after = 0
                log.debug(
                    f"GENERIC: {length_1_to_ssu * self.D} (ССУ -> 1), {length_between_ms * self.D} (1 -> 2), после = {length_after  if length_after else 0}")



            if not self.ms_after:
                log.info("МС после ССУ отсутствуют")
            else:
                log.info("МС после ССУ переданы")

            roughness_limit = get_relative_roughness(self.beta) / 1000
            actual_roughness = self.Ra / self.D
            log.debug(f"Ra = {self.Ra} м, D = {self.D} м → Ra/D = {actual_roughness}, допустимо ≤ {roughness_limit}")

            is_smooth = actual_roughness <= roughness_limit
            if is_smooth:
                log.info("Трубопровод считается гладким — можно применять ССУ без поправок")
            else:
                log.warning("Трубопровод не считается гладким — необходимо учитывать поправочный коэффициент на истечение")

            return {
                "length_first_ms_to_ssu_D": length_1_to_ssu,
                "length_between_ms_D": length_between_ms if ms2 else None,
                "length_after_SSU": length_after if length_after > 0 else None,
                "relative_roughness_Ra_D": actual_roughness,
                "roughness_limit_Ra_D": roughness_limit,
                "is_smooth_pipe": is_smooth
            }

        except Exception as e:
            log.exception("Ошибка при расчёте прямолинейных участков:")
            return {"error": str(e)}
