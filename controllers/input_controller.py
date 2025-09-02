# file: controllers/input_controller.py
"""
ПЛАН (псевдокод):
1) Цель: Универсально читать входные JSON-словари с меняющейся структурой
   и приводить значения к внутренним единицам SI для последующего расчёта.
   Нужна устойчивость к:
      - разным путям в JSON (алиасы путей),
      - формату чисел: просто число или {real, unit} / {value: {real, unit}},
      - разношёрстным обозначениям единиц ("mm_Hg", "m3_h", "°C", ...),
      - частично отсутствующим полям (мягкая деградация и лог замечаний).

2) Абстракции:
   - DotPath: обращение к полю по "a.b.c" с безопасной навигацией.
   - UnitCategory: pressure/temperature/length/volflow/massflow.
   - UnitNormalizer: нормализация строк единиц к каноническому виду.
   - ValueExtractor: извлекает число из узла (int|float|dict с unit),
     при необходимости конвертирует в целевую единицу категории.

3) Спецификация входа (InputSpec):
   - Для каждой целевой величины задать список альтернативных путей и категорию,
     плюс целевую единицу, а также обязательность для расчёта.
   - Первый найденный путь используется; если нет — пишем замечание.

4) Контроллер:
   - class InputController:
       - parse(data) -> ParsedInput: словарь SI-значений + список замечаний.
       - prepare_params(data) -> PreparedController: жёсткие проверки для
         расчёта; падение только если обязательные поля не найдены.

5) Конвертация единиц:
   - Используем converters.units_validator (если доступен).
   - На случай отсутствия — локальные минимальные конвертеры (pressure/length/
     volflow/temperature), чтобы не падать на ранней интеграции.

6) Примаппинг текущего JSON (по образцу из сообщения):
   - p_abs ← physPackage.physProperties.p_abs
   - p_atm ← physPackage.physProperties.p_atm
   - p_st  ← physPackage.physProperties.p_st
   - T     ← physPackage.physProperties.T
   - T_st  ← physPackage.physProperties.T_st
   - q_v   ← flowPackage.flowProperties.q_v
   - d20,D20 ← lenPackage.lenProperties.{d20,D}  (или позже из techParams)
   - dp    ← (пока нет в примере) зарезервировано под альтернативные пути

7) Выходные единицы для PreparedController (исторически):
   - d, D: м; p1: Па (абс); dp: Па; t1: °C; R: Дж/(моль·К); Z: безразм.

8) Логика устойчивости:
   - Все значения собираются «мягко»: добавляется remark, если поле не найдено.
   - В prepare_params() чётко проверяются необходимые для выбранного расчёта поля.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --- Попытка использовать общий конвертер из converters.units_validator ---
try:  # noqa: SIM105
    from converters.units_validator import (
        convert_length,
        convert_pressure,
        convert_volflow,
    )
    from converters.units_validator import (
        # вспомогательные для температуры (если есть)
        # безопасно определим локально ниже, если в модуле их нет
        dynamic_viscosity_from_rho_nu,  # noqa: F401  (для будущего)
    )
    HAVE_CONVERTERS = True
except Exception:  # модуль ещё не подключен в репозиторий
    HAVE_CONVERTERS = False


# --------------------------- Локальные конвертеры (fallback) ---------------------------
# Почему нужны: чтобы модуль не падал до интеграции общего конвертера.

def _norm_unit(u: str) -> str:
    u = (u or "").strip()
    return u.replace(" ", "").replace("_", "/").replace("·", "*")


def _k_pressure_to_pa(unit: str) -> Decimal:
    u = _norm_unit(unit).lower()
    m = {
        "pa": Decimal("1"),
        "kpa": Decimal("1e3"),
        "mpa": Decimal("1e6"),
        "bar": Decimal("1e5"),
        "mmhg": Decimal("1.3332e2"),
        "mm/hg": Decimal("1.3332e2"),
        "mmhg": Decimal("1.3332e2"),
        "mmhg": Decimal("1.3332e2"),
        "mmhg": Decimal("1.3332e2"),
        "mmhg": Decimal("1.3332e2"),
        "kgf/cm2": Decimal("9.80665e4"),
        "kgf/m2": Decimal("9.80665"),
        # Варианты из примера
        "mm/hg": Decimal("1.3332e2"),
    }
    # Частые синонимы из входа
    if u in ("mmhg", "mmhg", "mmhg"):
        return Decimal("1.3332e2")
    if u in ("mmhg", "mm/hg", "mm_hg", "mmhg"):
        return Decimal("1.3332e2")
    return m.get(u, Decimal("1"))


def _convert_pressure(val: float | Decimal, unit: str, to_unit: str = "Pa") -> Decimal:
    if HAVE_CONVERTERS:
        return Decimal(str(convert_pressure(val, unit, to_unit)))
    if to_unit.lower() != "pa":
        raise ValueError("Локальный конвертер давления поддерживает только Pa")
    k = _k_pressure_to_pa(unit)
    return Decimal(str(val)) * k


def _k_length_to_m(unit: str) -> Decimal:
    u = _norm_unit(unit).lower()
    if u in ("m",):
        return Decimal("1")
    if u in ("mm",):
        return Decimal("1e-3")
    return Decimal("1")


def _convert_length(val: float | Decimal, unit: str, to_unit: str = "m") -> Decimal:
    if HAVE_CONVERTERS:
        return Decimal(str(convert_length(val, unit, to_unit)))
    if to_unit.lower() != "m":
        raise ValueError("Локальный конвертер длины поддерживает только m")
    return Decimal(str(val)) * _k_length_to_m(unit)


def _k_vol_to_m3s(unit: str) -> Decimal:
    u = _norm_unit(unit).lower()
    if u in ("m3/s", "m3s"):
        return Decimal("1")
    if u in ("m3/h", "m3h"):
        return Decimal("1") / Decimal("3600")
    if u in ("l/s", "ls"):
        return Decimal("1e-3")
    if u in ("l/min", "l/min", "lmin"):
        return Decimal("1e-3") / Decimal("60")
    if u in ("m3_h",):
        return Decimal("1") / Decimal("3600")
    return Decimal("1")


def _convert_volflow(val: float | Decimal, unit: str, to_unit: str = "m3/s") -> Decimal:
    if HAVE_CONVERTERS:
        return Decimal(str(convert_volflow(val, unit, to_unit)))
    if to_unit.lower() not in ("m3/s", "m3s"):
        raise ValueError("Локальный конвертер расхода поддерживает только м³/с")
    return Decimal(str(val)) * _k_vol_to_m3s(unit)


def kelvin_to_celsius(x: float | Decimal) -> Decimal:
    # Критично: PreparedController исторически ждёт °C
    return Decimal(str(x)) - Decimal("273.15")


# --------------------------- Вспомогательная навигация по JSON ---------------------------

def _get_by_path(root: Dict[str, Any], path: str) -> Any:
    cur: Any = root
    for key in path.split('.'):
        if not isinstance(cur, dict) or key not in cur:
            return None
        cur = cur[key]
    return cur


def _first_existing(root: Dict[str, Any], paths: Iterable[str]) -> Tuple[Optional[str], Any]:
    for p in paths:
        v = _get_by_path(root, p)
        if v is not None:
            return p, v
    return None, None


# --------------------------- Извлечение значений с единицами ---------------------------

class Category:
    PRESSURE = "pressure"
    TEMPERATURE = "temperature"
    LENGTH = "length"
    VOLFLOW = "volflow"
    MASSFLOW = "massflow"


def _extract_number_or_unit(node: Any, *, default_unit: str, category: str) -> Decimal:
    """Возвращает значение в целевых единицах категории (SI),
    поддерживает:
      - просто число
      - {real, unit}
      - {value: {real, unit}}
    default_unit — если unit не указан.
    """
    def as_decimal(x: Any) -> Decimal:
        return Decimal(str(x))

    # распаковка вложенного {value: {...}}
    if isinstance(node, dict) and "value" in node and isinstance(node["value"], dict):
        node = node["value"]

    # просто число
    if isinstance(node, (int, float, Decimal)):
        val, unit = as_decimal(node), default_unit
    elif isinstance(node, dict):
        val = node.get("real") if "real" in node else node.get("value")
        unit = node.get("unit") or default_unit
        if val is None:
            raise ValueError("Ожидалось поле 'real'/'value' в объекте с единицами.")
        val = as_decimal(val)
    else:
        raise ValueError(f"Некорректный узел значения: {node}")

    # конвертация по категории
    cu = (unit or default_unit)
    if category == Category.LENGTH:
        return _convert_length(val, cu, "m")
    if category == Category.PRESSURE:
        return _convert_pressure(val, cu, "Pa")
    if category == Category.VOLFLOW:
        return _convert_volflow(val, cu, "m3/s")
    if category == Category.TEMPERATURE:
        u = (cu or "").lower()
        if u in ("c", "°c", "celsius"):
            return val
        if u in ("k", "kelvin"):
            return kelvin_to_celsius(val)
        raise ValueError(f"Неизвестная единица температуры: '{unit}'. Ожидается 'C' или 'K'.")
    if category == Category.MASSFLOW:
        # при необходимости — аналогично VOLFLOW, пока не используется здесь
        return val

    return val


# --------------------------- Спецификация входа ---------------------------

@dataclass
class FieldSpec:
    name: str
    category: str
    target_unit: str  # используется только для документации/логов
    required: bool
    candidates: Tuple[str, ...]  # альтернативные пути в JSON
    default_unit: str


DEFAULT_SPEC: Tuple[FieldSpec, ...] = (
    FieldSpec(
        name="p_abs",
        category=Category.PRESSURE,
        target_unit="Pa",
        required=False,
        candidates=(
            "physPackage.physProperties.p_abs",
            "physPackage.p_abs",
            "environment_parameters.p_abs",  # на будущее
        ),
        default_unit="Pa",
    ),
    FieldSpec(
        name="p_atm",
        category=Category.PRESSURE,
        target_unit="Pa",
        required=False,
        candidates=(
            "physPackage.physProperties.p_atm",
            "physPackage.p_atm",
        ),
        default_unit="Pa",
    ),
    FieldSpec(
        name="p_st",
        category=Category.PRESSURE,
        target_unit="Pa",
        required=False,
        candidates=(
            "physPackage.physProperties.p_st",
            "physPackage.p_st",
        ),
        default_unit="Pa",
    ),
    FieldSpec(
        name="T",
        category=Category.TEMPERATURE,
        target_unit="C",
        required=False,
        candidates=(
            "physPackage.physProperties.T",
            "physPackage.T",
        ),
        default_unit="C",
    ),
    FieldSpec(
        name="T_st",
        category=Category.TEMPERATURE,
        target_unit="C",
        required=False,
        candidates=(
            "physPackage.physProperties.T_st",
            "physPackage.T_st",
        ),
        default_unit="C",
    ),
    FieldSpec(
        name="q_v",
        category=Category.VOLFLOW,
        target_unit="m3/s",
        required=False,
        candidates=(
            "flowPackage.flowProperties.q_v",
            "flowPackage.q_v",
        ),
        default_unit="m3/h",  # частый случай в примерах
    ),
    FieldSpec(
        name="q_st",
        category=Category.VOLFLOW,
        target_unit="m3/s",
        required=False,
        candidates=(
            "flowPackage.flowProperties.q_st",
            "flowPackage.q_st",
        ),
        default_unit="m3/h",
    ),
    FieldSpec(
        name="d20",
        category=Category.LENGTH,
        target_unit="m",
        required=False,
        candidates=(
            "lenPackage.lenProperties.d20",
            "errorPackage.errors.techParamsProState.d",  # если придёт там
        ),
        default_unit="mm",
    ),
    FieldSpec(
        name="D20",
        category=Category.LENGTH,
        target_unit="m",
        required=False,
        candidates=(
            "lenPackage.lenProperties.D",
            "lenPackage.lenProperties.D20",
            "errorPackage.errors.techParamsProState.D",
        ),
        default_unit="mm",
    ),
    FieldSpec(
        name="dp",
        category=Category.PRESSURE,
        target_unit="Pa",
        required=False,
        candidates=(
            "environment_parameters.dp",
            "physPackage.physProperties.dp",
            "flowPackage.flowProperties.dp",
        ),
        default_unit="Pa",
    ),
)


@dataclass
class ParsedInput:
    values_si: Dict[str, Decimal]
    remarks: List[str]


class InputController:
    """Универсальная обработка входных данных.
    - parse(data): извлекает и конвертирует значения в SI.
    - prepare_params(data): формирует PreparedController для расчёта
      (проверяя наличие обязательных полей для конкретного сценария).
    """

    def __init__(self, spec: Iterable[FieldSpec] = DEFAULT_SPEC):
        self.spec = tuple(spec)

    # --------------- API ---------------
    def parse(self, data: Dict[str, Any]) -> ParsedInput:
        values: Dict[str, Decimal] = {}
        remarks: List[str] = []

        for fs in self.spec:
            path, raw = _first_existing(data, fs.candidates)
            if path is None:
                if fs.required:
                    remarks.append(
                        f"[WARN] Не найдено обязательное поле '{fs.name}' (пути: {', '.join(fs.candidates)})."
                    )
                else:
                    remarks.append(
                        f"[INFO] Поле '{fs.name}' не найдено (пути: {', '.join(fs.candidates)})."
                    )
                continue

            try:
                val_si = _extract_number_or_unit(raw, default_unit=fs.default_unit, category=fs.category)
                values[fs.name] = val_si
                # Почему пишем remark: для последующей трассируемости входа.
                remarks.append(f"[OK] {fs.name} <- {path} → {val_si} {fs.target_unit}")
            except Exception as e:  # важно логировать
                remarks.append(f"[ERR] {fs.name} <- {path}: {e}")

        return ParsedInput(values_si=values, remarks=remarks)

    def prepare_params(self, data: Dict[str, Any]) -> "PreparedController":  # type: ignore[name-defined]
        parsed = self.parse(data)
        v = parsed.values_si

        # Жёсткая валидация под базовый кейс расчёта (например, pTZ по диафрагме):
        # d20, D20, p_abs, dp, T — обязательны.
        missing: List[str] = [k for k in ("d20", "D20", "p_abs", "dp", "T") if k not in v]
        if missing:
            tips = ", ".join(missing)
            context = "\n".join(parsed.remarks)
            raise ValueError(
                f"Отсутствуют обязательные поля для расчёта: {tips}.\nТрассировка:\n{context}"
            )

        d_m = float(v["d20"])  # м
        D_m = float(v["D20"])  # м
        p1_pa = float(v["p_abs"])  # Па
        dp_pa = float(v["dp"])  # Па
        t_c = float(v["T"])  # °C

        # Подхватываем необязательные (если есть):
        R = 8.314
        Z = 1.0
        if "R" in v:
            R = float(v["R"])  # если когда-то появится
        if "Z" in v:
            Z = float(v["Z"])  # если когда-то появится

        # Импортируем локально, чтобы не тянуть лишнее при простом парсе
        from controllers.prepare_controller import PreparedController  # noqa: WPS433

        if not (d_m > 0 and D_m > 0 and d_m < D_m):
            context = "\n".join(parsed.remarks)
            raise ValueError(
                f"Некорректные диаметры: d20={d_m} м, D20={D_m} м (ожидается 0 < d < D).\nТрассировка:\n{context}"
            )
        if p1_pa <= 0 or dp_pa <= 0:
            context = "\n".join(parsed.remarks)
            raise ValueError(
                f"Давления должны быть > 0 Па (p_abs={p1_pa}, dp={dp_pa}).\nТрассировка:\n{context}"
            )

        return PreparedController(
            d=d_m,
            D=D_m,
            p1=p1_pa,
            t1=t_c,
            dp=dp_pa,
            R=R,
            Z=Z,
        )


# --------------------------- Демонстрация на текущем примере ---------------------------
if __name__ == "__main__":
    # Пример из сообщения (сокращён до используемых полей):
    sample = {
        "flowPackage": {
            "flowProperties": {
                "q_v": {"real": 50, "unit": "m3_h"}
            },
            "request": {"extraTypeOfCalc": "Direct", "typeOfCalc": "pTZ"}
        },
        "physPackage": {
            "physProperties": {
                "T": {"real": 15, "unit": "C"},
                "T_st": {"real": 20, "unit": "C"},
                "p_abs": {"real": 4, "unit": "MPa"},
                "p_atm": {"real": 760, "unit": "mm_Hg"},
                "p_st": {"real": 0.101325, "unit": "MPa"}
            }
        },
        "lenPackage": {
            "lenProperties": {
                # Допустим, сюда придут диаметры позже:
                "d20": {"real": 100, "unit": "mm"},
                "D": {"real": 300, "unit": "mm"}
            }
        }
    }

    ic = InputController()
    parsed = ic.parse(sample)
    for r in parsed.remarks:
        print(r)
    print("VALUES_SI:", parsed.values_si)

    # Для демонстрации prepare_params добавим dp:
    sample["physPackage"]["physProperties"]["dp"] = {"real": 20, "unit": "kPa"}
    prepared = ic.prepare_params(sample)
    print(prepared)
