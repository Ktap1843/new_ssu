# errors/error_adapter.py
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple
import math


# -------------------------- Вспомогательные конвертеры --------------------------

def _to_float(x: Any) -> Optional[float]:
    try:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict) and "real" in x:
            return float(x["real"])
        return float(x)
    except Exception:
        return None


def _unit_pressure_to_pa(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower()
    if not u or u in ("pa",):
        return value
    if u in ("kpa",):
        return value * 1e3
    if u in ("mpa",):
        return value * 1e6
    if u in ("bar",):
        return value * 1e5
    if u in ("atm", "at", "ata"):
        return value * 101325.0
    # неизвестную единицу трактуем как Па
    return value


def _unit_temp_to_k(value: float, unit: Optional[str]) -> float:
    u = (unit or "").strip().lower()
    if not u:
        # если нет явной единицы – применим простую эвристику:
        # "большие" значения считаем K, "комнатные" — °C
        return value if value >= 200.0 else value + 273.15
    if u in ("k", "kelvin", "kelvins"):
        return value
    if u in ("c", "°c", "degc", "celsius"):
        return value + 273.15
    return value  # по умолчанию считаем K


def _to_rel_fraction(err_node: Mapping[str, Any],
                     base_value: Optional[float],
                     base_unit: Optional[str] = None,
                     quantity: str = "") -> float:
    """
    Превращает описание ошибки в относительную долю (0.01 = 1%).
    err_node: {"errorTypeId": "AbsErr|RelErr", "value": {"real": .., "unit": ".."}}
    base_value: значение измеряемой величины в её базовых единицах (для AbsErr).
    base_unit: подсказка по единицам base_value (для температур/давлений, если err_node без unit).
    quantity: "pressure"|"temperature"|... — влияет на конверсии единиц.
    """
    if not isinstance(err_node, Mapping):
        return 0.0

    etype = str(err_node.get("errorTypeId") or "").strip().lower()
    val = err_node.get("value")

    # --- относительная ошибка в процентах ---
    if etype in ("relerr", "rel", "relative"):
        # ожидаем unit ~ "percent"
        real = _to_float(val)
        if real is None and isinstance(val, Mapping):
            real = _to_float(val.get("real"))
        if real is None:
            return 0.0
        return float(real) / 100.0

    # --- абсолютная ошибка ---
    if etype in ("abserr", "abs", "absolute"):
        if base_value in (None, 0.0):
            return 0.0
        # извлечём значение и юнит
        if isinstance(val, Mapping):
            real = _to_float(val.get("real"))
            unit = val.get("unit")
        else:
            real = _to_float(val)
            unit = base_unit

        if real is None:
            return 0.0

        # конвертируем абсолют в базовые единицы измеряемой величины
        abs_base = float(real)
        q = quantity.strip().lower()
        if q == "pressure":
            abs_base = _unit_pressure_to_pa(abs_base, unit)
        elif q == "temperature":
            # абсолютная погрешность температуры переводится в К
            # (±1°C == ±1K)
            abs_base = abs_base  # 1°C = 1K для приращений
        # else: прочие — оставляем как есть

        return abs(abs_base) / abs(base_value)

    return 0.0


def _combine_rss(values) -> float:
    return math.sqrt(sum((float(v) ** 2 for v in values if v is not None)))


# -------------------------- Основная логика --------------------------

def _extract_base_phys(ctx: Mapping[str, Any]) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Возвращает (p_abs [Pa], T [K], dp [Pa]) из ctx["phys"].
    ctx["phys"]["T"] может быть в К (предпочтительно) или в °C — определим эвристикой.
    """
    phys = (ctx or {}).get("phys") or {}

    p_abs = _to_float(phys.get("p_abs"))
    dp = _to_float(phys.get("dp"))
    T_in = _to_float(phys.get("T"))

    # Температуру приведём к Кельвинам
    T = None
    if T_in is not None:
        # Если в ctx лежит уже К — оставим; если нет — поправим
        # Heвысокие значения трактуем как °C
        T = T_in if T_in >= 200.0 else (T_in + 273.15)

    return p_abs, T, dp


def _gather_rel_inputs(errors_cfg: Mapping[str, Any],
                       p_abs: Optional[float],
                       T: Optional[float],
                       dp: Optional[float]) -> Dict[str, float]:
    """
    Преобразует структуру из input.errorPackage.errors в относительные вклады (фракции).
    Возвращает словарь с ключами: "dp","p_abs","T","corrector","flow","out_signal" (что нашлось).
    """
    rel: Dict[str, float] = {}

    # ---- Температура ----
    t_node = errors_cfg.get("temperatureErrorProState") or {}
    t_intr = t_node.get("intrError")
    t_compl = t_node.get("complError")
    t_rel = _combine_rss([
        _to_rel_fraction(t_intr, base_value=T, base_unit="K", quantity="temperature"),
        _to_rel_fraction(t_compl, base_value=T, base_unit="K", quantity="temperature"),
    ])
    if t_rel > 0.0:
        rel["T"] = t_rel

    # ---- Абсолютное давление ----
    p_node = errors_cfg.get("absPressureErrorProState") or {}
    p_intr = p_node.get("intrError")
    p_compl = p_node.get("complError")
    p_rel = _combine_rss([
        _to_rel_fraction(p_intr, base_value=p_abs, base_unit="Pa", quantity="pressure"),
        _to_rel_fraction(p_compl, base_value=p_abs, base_unit="Pa", quantity="pressure"),
    ])
    if p_rel > 0.0:
        rel["p_abs"] = p_rel

    # ---- Перепад давления ----
    dp_node = errors_cfg.get("diffPressureErrorProState") or {}
    dp_intr = dp_node.get("intrError")
    dp_compl = dp_node.get("complError")
    dp_rel = _combine_rss([
        _to_rel_fraction(dp_intr, base_value=dp, base_unit="Pa", quantity="pressure"),
        _to_rel_fraction(dp_compl, base_value=dp, base_unit="Pa", quantity="pressure"),
    ])
    if dp_rel > 0.0:
        rel["dp"] = dp_rel

    # ---- Корректор/внешняя электроника (как относительные) ----
    corr_node = errors_cfg.get("calcCorrectorProState") or {}
    corr_intr = corr_node.get("intrError")
    corr_compl = corr_node.get("complError")
    corr_rel = _combine_rss([
        _to_rel_fraction(corr_intr, base_value=None),
        _to_rel_fraction(corr_compl, base_value=None),
    ])
    if corr_rel > 0.0:
        rel["corrector"] = corr_rel

    # ---- Итоговой блок расхода/выходного сигнала (как относительные) ----
    flow_node = errors_cfg.get("flowErrorProState") or {}
    flow_intr = flow_node.get("intrError")
    flow_out = flow_node.get("outSignalIntrError")
    flow_rel = _combine_rss([
        _to_rel_fraction(flow_intr, base_value=None),
        _to_rel_fraction(flow_out, base_value=None),
    ])
    if flow_rel > 0.0:
        rel["flow"] = flow_rel

    return rel


def _map_to_outputs(rel_inputs: Mapping[str, float]) -> Dict[str, Dict[str, float]]:
    """
    Перераспределяет вклады по выходным величинам.
    Для dP, p_abs, T используется коэффициент 0.5 (классическая зависимость через корень).
    Прочие относительные вклады (corrector/flow) идут с коэф. 1.0.
    """
    k_dp = 0.5
    k_pT = 0.5

    dp = rel_inputs.get("dp", 0.0)
    p_abs = rel_inputs.get("p_abs", 0.0)
    T = rel_inputs.get("T", 0.0)
    corr = rel_inputs.get("corrector", 0.0)
    flow = rel_inputs.get("flow", 0.0)

    def rss_for(*terms) -> float:
        return _combine_rss(terms)

    # Для трёх целевых величин применим одинаковую модель влияний:
    # Qm ∝ sqrt(Δp) * sqrt(ρ)  ~→ 0.5*σ_dp + 0.5*σ_ρ;  ρ ~ p/T → 0.5*(σ_p + σ_T)
    # Qv ∝ sqrt(Δp/ρ)         ~→ 0.5*σ_dp + 0.5*σ_ρ  (знак роли не играет в RSS)
    # Qstd считаем так же, если нет отдельных ошибок p_st/T_st.
    mass = rss_for(k_dp * dp, k_pT * p_abs, k_pT * T, corr, flow)
    vol_act = rss_for(k_dp * dp, k_pT * p_abs, k_pT * T, corr, flow)
    vol_std = rss_for(k_dp * dp, k_pT * p_abs, k_pT * T, corr, flow)

    return {
        "mass_flow": {"rel": mass, "percent": mass * 100.0},
        "volume_flow_actual": {"rel": vol_act, "percent": vol_act * 100.0},
        "volume_flow_std": {"rel": vol_std, "percent": vol_std * 100.0},
    }


def calculate_all(errors: Mapping[str, Any],
                  ctx: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """
    Главная точка входа.
    errors — поддерево из input.errorPackage.errors
    ctx — то, что отдаёт CalculationAdapter (геометрия/физика/результаты); используем физику.
    Возвращает словарь, готовый к включению в result["errors"].
    """
    try:
        if not isinstance(errors, Mapping) or not errors:
            return {"skip": True, "reason": "empty errors config"}

        p_abs, T, dp = _extract_base_phys(ctx or {})

        rel_inputs = _gather_rel_inputs(errors, p_abs, T, dp)
        outputs = _map_to_outputs(rel_inputs)

        # Детализируем «использованные» исходники (чтобы было видно, что распознано)
        details = {
            "inputs_rel": {k: {"rel": v, "percent": v * 100.0} for k, v in rel_inputs.items()},
        }

        # Итог: можно ещё сложить «общую» сводку по одному из выходов (напр., mass_flow)
        summary_rel = outputs["mass_flow"]["rel"]

        return {
            "skip": False,
            "details": details,
            "by_output": outputs,
            "summary": {"rel": summary_rel, "percent": summary_rel * 100.0},
        }
    except Exception as exc:
        return {"skip": False, "error": f"{exc}"}


# Дополнительные алиасы, чтобы адаптер легко находил «вход»
def calculate(errors: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return calculate_all(errors, ctx)


def run(errors: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return calculate_all(errors, ctx)


def main(errors: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    return calculate_all(errors, ctx)


class ErrorAdapter:
    """Объектный интерфейс на случай, если поиск функции не сработает."""
    def calculate(self, errors: Mapping[str, Any], ctx: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
        return calculate_all(errors, ctx)
