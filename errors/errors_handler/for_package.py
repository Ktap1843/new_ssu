# errors/errors_handler/for_package.py
from __future__ import annotations
from typing import Optional, Sequence, List, Dict, Tuple
from math import sqrt

# ========= Исключение =========
class CalcThetaError(Exception):
    pass

# ========= Политики нормировки (10.31) =========
class NormalizationPolicy:
    GENERAL = "general"                   # 10.31: Δx_i — абсолютная доля в ДОЛЯХ (0..1), УПП фикс.
    METHANE_BY_DIFF = "methane_by_diff"   # 10.31: x_i += Δ, x_CH4 -= ΣΔ, остальные фикс.

# ========= Утилиты состава =========
def _as_fractions_from_percent_dict(comp_pct: Dict[str, float]) -> Tuple[List[str], List[float]]:
    if not comp_pct:
        raise CalcThetaError("Состав пустой.")
    names = list(comp_pct.keys())
    vals = [float(comp_pct[k]) for k in names]
    if any(v < 0.0 for v in vals):
        raise CalcThetaError("Доли состава не могут быть отрицательными.")
    s = sum(vals)
    if s <= 0.0:
        raise CalcThetaError("Сумма долей должна быть > 0.")
    fracs = [v / s for v in vals]
    return names, fracs

def _to_percent_dict(
    names: List[str],
    fracs: List[float],
    *,
    decimals: Optional[int] = None,   # None => без округления
    fix_to: Optional[str] = None
) -> Dict[str, float]:
    if len(names) != len(fracs):
        raise CalcThetaError("Длины имен и долей не совпадают.")
    # не даём отрицательных
    fracs = [max(0.0, float(f)) for f in fracs]
    s = sum(fracs)
    if s <= 0.0:
        raise CalcThetaError("Сумма долей после нормировки ≤ 0.")
    fracs = [f / s for f in fracs]

    if decimals is None:
        out = {n: f * 100.0 for n, f in zip(names, fracs)}
        # суммарно уже 100.0 (в машинной точности), ничего не правим
        return out

    out = {n: round(f * 100.0, decimals) for n, f in zip(names, fracs)}
    total = round(sum(out.values()), decimals)
    diff = round(100.0 - total, decimals)
    if abs(diff) > 10 ** (-decimals):
        # если нужно ровно добить сумму — корректируем самый большой или фиксированный компонент
        tgt = fix_to if (fix_to and fix_to in out) else names[max(range(len(fracs)), key=lambda i: fracs[i])]
        out[tgt] = round(out[tgt] + diff, decimals)
    for k, v in out.items():
        if v == -0.0:
            out[k] = 0.0
    return out

def names_to_indices(names: List[str], subset: Sequence[str]) -> List[int]:
    pos = {n: i for i, n in enumerate(names)}
    idx: List[int] = []
    for n in subset:
        if n not in pos:
            raise CalcThetaError(f"Компонент '{n}' не найден в составе.")
        idx.append(pos[n])
    return idx

# ========= Валидация (разок в начале и разок в конце) =========
def validate_comp_once(comp: Dict[str, float],
                       *,
                       error_composition: Optional[Dict[str, dict]] = None,
                       upp_names: Optional[Sequence[str]] = None,
                       sum_tol: float = 1e-6,
                       value_tol: float = 1e-12) -> List[str]:
    issues: List[str] = []
    s = sum(comp.values())
    if abs(s - 100.0) > sum_tol:
        issues.append(f"Сумма != 100%: {s:.9f}")
    for k, v in comp.items():
        if not (v == v and abs(v) != float("inf")):
            issues.append(f"{k}: NaN/inf")
        if v < -value_tol:
            issues.append(f"{k}: отрицательная доля ({v:.9f})")
        if v > 100.0 + value_tol:
            issues.append(f"{k}: >100% ({v:.9f})")
    if error_composition and upp_names:
        for name in upp_names:
            meta = error_composition.get(name, {})
            intr = (meta.get("intrError") or {})
            if intr.get("errorTypeId") == "UppErr":
                rng = (intr.get("range") or {}).get("range") or {}
                mn, mx = rng.get("min"), rng.get("max")
                if mn is not None and mx is not None:
                    v = comp.get(name)
                    if v is not None and not (mn - value_tol <= v <= mx + value_tol):
                        issues.append(f"УПП '{name}' вне диапазона [{mn};{mx}] -> {v}")
    return issues

def end_policy_invariants(before: Dict[str, float],
                          after: Dict[str, float],
                          *,
                          policy: str,
                          target_names: Sequence[str],
                          methane_name: str,
                          upp_names: Sequence[str],
                          tol: float = 1e-9) -> List[str]:
    issues: List[str] = []
    if policy == NormalizationPolicy.GENERAL:
        for n in upp_names:
            if abs(after.get(n, 0) - before.get(n, 0)) > tol:
                issues.append(f"GENERAL: УПП '{n}' изменился {before[n]} -> {after[n]}")
    elif policy == NormalizationPolicy.METHANE_BY_DIFF:
        changed = [k for k in before if abs(after.get(k, 0) - before[k]) > tol]
        allowed = set(target_names) | {methane_name}
        extra = [k for k in changed if k not in allowed]
        if extra:
            issues.append(f"METHANE_BY_DIFF: изменены лишние компоненты: {extra}")
    return issues

# ========= Нормировки (10.31) =========
def normalize_composition_general(fracs: List[float], i: int, delta_xi: float,
                                  upp_indices: Optional[Sequence[int]] = None) -> List[float]:
    n = len(fracs)
    x = list(map(float, fracs))
    if i < 0 or i >= n:
        raise CalcThetaError("Индекс i вне диапазона.")
    upp = set(upp_indices or [])
    if i in upp:
        raise CalcThetaError("i-компонент не может быть УПП в GENERAL.")
    s = sum(x)
    if s <= 0.0:
        raise CalcThetaError("Сумма долей должна быть > 0.")
    x = [v / s for v in x]
    s_upp = sum(x[k] for k in upp)
    s_free = 1.0 - s_upp
    xi = x[i]
    x_new_i = xi + delta_xi
    if x_new_i < 0.0:
        raise CalcThetaError(f"x[i] + Δx_i < 0 (x[i]={xi:.6g}, Δx_i={delta_xi:.6g}).")
    if x_new_i > s_free + 1e-15:
        raise CalcThetaError(f"x[i] + Δx_i ({x_new_i:.6g}) > свободной доли ({s_free:.6g}).")
    s_free_wo_i = s_free - xi
    alpha = 1.0 if s_free_wo_i == 0.0 else (s_free - x_new_i) / s_free_wo_i
    x_star = x[:]
    for j in range(n):
        if j in upp:
            x_star[j] = x[j]
        elif j == i:
            x_star[j] = x_new_i
        else:
            x_star[j] = x[j] * alpha
    s2 = sum(x_star)
    if s2 <= 0.0:
        raise CalcThetaError("Сумма долей после нормализации ≤ 0.")
    return [max(0.0, v / s2) for v in x_star]

def normalize_composition_methane_by_difference(fracs: List[float], i: int, delta_xi: float, ch4_index: int) -> List[float]:
    n = len(fracs)
    x = list(map(float, fracs))
    if i < 0 or i >= n or ch4_index < 0 or ch4_index >= n:
        raise CalcThetaError("Индексы i/ch4_index вне диапазона.")
    if i == ch4_index:
        raise CalcThetaError("В 'метан по разности' i не может совпадать с CH4.")
    s = sum(x)
    if s <= 0.0:
        raise CalcThetaError("Сумма долей должна быть > 0.")
    x = [v / s for v in x]
    if x[i] + delta_xi < 0.0:
        raise CalcThetaError(f"x[i] + Δx_i < 0 (x[i]={x[i]:.6g}, Δx_i={delta_xi:.6g}).")
    if x[ch4_index] - delta_xi < 0.0:
        raise CalcThetaError(f"x[CH4] - Δx_i < 0 (x[CH4]={x[ch4_index]:.6g}, Δx_i={delta_xi:.6g}).")
    x[i] += delta_xi
    x[ch4_index] -= delta_xi
    s2 = sum(x)
    if s2 <= 0.0:
        raise CalcThetaError("Сумма долей после нормализации ≤ 0.")
    return [max(0.0, v / s2) for v in x]

# ========= Формулы 10.28–10.31 =========
def formula_10_28(delta_rho_f: float,
                  theta_rho_T: float, delta_T: float,
                  theta_rho_p: float, delta_p: float) -> float:
    return sqrt(
        (delta_rho_f ** 2) +
        (theta_rho_T ** 2) * (delta_T ** 2) +
        (theta_rho_p ** 2) * (delta_p ** 2)
    )

def formula_10_29(delta_rho_f: float,
                  theta_rho_T: float, delta_T: float,
                  theta_rho_p: float, delta_p: float,
                  theta_rho_x: Sequence[float], delta_x: Sequence[float]) -> float:
    if len(theta_rho_x) != len(delta_x):
        raise CalcThetaError("Длины theta_rho_x и delta_x должны совпадать.")
    s = (delta_rho_f ** 2) + (theta_rho_T ** 2) * (delta_T ** 2) + (theta_rho_p ** 2) * (delta_p ** 2)
    for th, dx in zip(theta_rho_x, delta_x):
        s += (th ** 2) * (dx ** 2)
    return sqrt(s)

def theta_rho_xi_from_rho(rho: float, rho_star: float, delta_xi: float, x_i: float) -> float:
    if delta_xi == 0.0:
        raise ZeroDivisionError("Δx_i = 0 для вычисления ϑ_{ρx_i}.")
    return (rho_star - rho) * (x_i / (rho * delta_xi))

# ========= Простейшая «физика» ρ (для отладки алгоритма) =========
# ρ ~ Σ x_i * M_i (средняя мол. масса): достаточно для теста алгоритма (константа пропорц. сократится в (10.30))
MOLAR_MASS = {
    "Methane": 16.04, "Nitrogen": 28.0134, "Oxygen": 31.998, "CarbonDioxide": 44.01,
    "Ethane": 30.07, "Propane": 44.097, "iButane": 58.124, "nButane": 58.124,
    "iPentane": 72.151, "nPentane": 72.151, "Helium": 4.0026, "Hydrogen": 2.016,
}
def rho_from_composition_percent(comp_pct: Dict[str, float]) -> float:
    names, fracs = _as_fractions_from_percent_dict(comp_pct)
    M = 0.0
    for n, x in zip(names, fracs):
        M += x * MOLAR_MASS.get(n, 28.0)
    return M

# ========= Построение УПП и выбор режима =========
def build_upp_from_error(error_composition: Dict[str, dict], present: Sequence[str]) -> List[str]:
    upp = []
    for name in present:
        meta = error_composition.get(name) or {}
        intr = meta.get("intrError") or {}
        if intr.get("errorTypeId") == "UppErr":
            upp.append(name)
    return upp

def decide_policy_simple(composition: Dict[str,float],
                         error_composition: Dict[str,dict],
                         methane_name: str = "Methane",
                         force: Optional[str] = None) -> str:
    if force in (NormalizationPolicy.GENERAL, NormalizationPolicy.METHANE_BY_DIFF):
        return force
    if methane_name not in composition:
        return NormalizationPolicy.METHANE_BY_DIFF
    intr = (error_composition.get(methane_name) or {}).get("intrError") or {}
    if intr.get("errorTypeId") == "UppErr":
        return NormalizationPolicy.METHANE_BY_DIFF
    return NormalizationPolicy.GENERAL

# ========= Парсинг δxᵢ из блока ошибок состава =========
def _err_value_pp(kind: Optional[str], meta: Optional[dict], xi_percent: float) -> float:
    """
    Возвращает вклад в δx_i в ПРОЦЕНТНЫХ ПУНКТАХ.
    - AbsErr: берём как есть (в п.п.).
    - RelErr: δx_i(pp) = (rel%/100) * xi(%)  (процент от доли компонента в %).
    """
    if not meta:
        return 0.0
    v = meta.get("value") or {}
    unit = v.get("unit", "percent")
    real = float(v.get("real", 0.0))
    if unit != "percent":
        # при необходимости тут можно сделать маппинг единиц
        pass
    if kind == "AbsErr":
        return real  # уже п.п.
    if kind == "RelErr":
        return (real/100.0) * xi_percent
    return 0.0

def delta_pp_from_error_meta(xi_percent: float, err_meta: dict) -> float:
    """
    Комбинируем 'complError' и 'intrError' квадратично, возвращаем δx_i в ПРОЦЕНТНЫХ ПУНКТАХ.
    УПП -> 0 (их в сумму 10.29 не включаем).
    """
    compl = err_meta.get("complError") or {}
    intr  = err_meta.get("intrError") or {}

    # UPP? — не используем в 10.29
    if intr.get("errorTypeId") == "UppErr" or compl.get("errorTypeId") == "UppErr":
        return 0.0

    d_pp = 0.0
    for part in (compl, intr):
        k = part.get("errorTypeId")
        if not k:
            continue
        d_part = _err_value_pp(k, part, xi_percent)
        d_pp = sqrt(d_pp**2 + d_part**2)
    return d_pp  # п.п.

# ========= θ по (10.30) для одного компонента =========
def compute_theta_for_component(comp_pct: Dict[str, float],
                                target_name: str,
                                policy: str,
                                delta_x_abs: float,     # Δ в долях (0..1)
                                upp_names: Sequence[str],
                                methane_name: str = "Methane") -> float:
    names, fracs = _as_fractions_from_percent_dict(comp_pct)
    i = names.index(target_name)
    upp_idx = names_to_indices(names, upp_names) if upp_names else []
    ch4_idx = names.index(methane_name) if methane_name in names else None
    rho0 = rho_from_composition_percent(comp_pct)
    x_i = fracs[i]
    if policy == NormalizationPolicy.GENERAL:
        if i in upp_idx:
            raise CalcThetaError(f"Компонент '{target_name}' — УПП, нельзя варьировать в GENERAL.")
        fr_star = normalize_composition_general(fracs, i=i, delta_xi=delta_x_abs, upp_indices=upp_idx)
    elif policy == NormalizationPolicy.METHANE_BY_DIFF:
        if ch4_idx is None:
            raise CalcThetaError("Нет компонента Methane для режима 'по разности'.")
        fr_star = normalize_composition_methane_by_difference(fracs, i=i, delta_xi=delta_x_abs, ch4_index=ch4_idx)
    else:
        raise CalcThetaError("Неизвестная политика нормировки.")
    comp_star = _to_percent_dict(names, fr_star, decimals=None)  # без округлений
    rho_star = rho_from_composition_percent(comp_star)
    return theta_rho_xi_from_rho(rho=rho0, rho_star=rho_star, delta_xi=delta_x_abs, x_i=x_i)

def pp_to_fraction(pp: float) -> float:
    return pp / 100.0  # 0.1 п.п. -> 0.001

# ========= ГЛАВНАЯ «РУЧКА» =========
def run_method10(
    composition: Dict[str, float],
    error_composition: Dict[str, dict],
    *,

    mode: str = "auto",                       # "auto" | "general" | "methane_by_diff"
    methane_name: str = "Methane",

    # параметры 10.28/10.29:
    delta_rho_f: float = 0.08,
    theta_rho_T: float = -1.67e-3, delta_T: float = 0.20,
    theta_rho_p: float =  1.655e-2, delta_p: float = 0.15,

    # округление итогового состава (пример): None = без округлений
    decimals: Optional[int] = None,
    fix_sum_to: Optional[str] = None,

    # переопределение δx_i в п.п. (например, {"Ethane": 0.1, "CO2": 0.05})
    deltas_override_pp: Optional[Dict[str, float]] = None,
) -> Dict[str, object]:

    # --- Проверка входа (разок) ---
    names = list(composition.keys())
    upp_names = build_upp_from_error(error_composition, names)
    issues0 = validate_comp_once(composition, error_composition=error_composition, upp_names=upp_names)

    # --- Выбор политики ---
    if mode == "general":
        policy = NormalizationPolicy.GENERAL
    elif mode == "methane_by_diff":
        policy = NormalizationPolicy.METHANE_BY_DIFF
    else:
        policy = decide_policy_simple(composition, error_composition, methane_name=methane_name)

    # --- Собираем δx_i (в п.п.) из error_composition (или берём override) ---
    deltas_pp: Dict[str, float] = {}
    for n in names:
        if deltas_override_pp and n in deltas_override_pp:
            deltas_pp[n] = float(deltas_override_pp[n])
        else:
            deltas_pp[n] = delta_pp_from_error_meta(composition[n], error_composition.get(n) or {})

    # --- Формируем список целей для (10.30)/(10.29) ---
    targets: List[str] = []
    dx_frac: List[float] = []
    for n in names:
        # пропускаем УПП
        if n in upp_names:
            continue
        # режим "по разности" — исключаем CH4 из суммы (10.29)
        if policy == NormalizationPolicy.METHANE_BY_DIFF and n == methane_name:
            continue
        pp = deltas_pp.get(n, 0.0)
        if pp > 0.0:
            targets.append(n)
            dx_frac.append(pp_to_fraction(pp))

    # --- Считаем θ для всех целей ---
    theta_vec: List[float] = []
    for n, dfrac in zip(targets, dx_frac):
        th = compute_theta_for_component(composition, n, policy, dfrac, upp_names, methane_name=methane_name)
        theta_vec.append(th)

    # --- (10.29) и (10.28) ---
    delta_rho_1029 = formula_10_29(delta_rho_f, theta_rho_T, delta_T, theta_rho_p, delta_p, theta_vec, dx_frac)
    delta_rho_1028 = formula_10_28(delta_rho_f, theta_rho_T, delta_T, theta_rho_p, delta_p)

    # --- Пример "конечного" состава для проверки инвариантов ---
    final_comp = composition.copy()
    issues1: List[str] = []
    if targets:
        _, fr = _as_fractions_from_percent_dict(composition)

        if policy == NormalizationPolicy.GENERAL:
            # демонстрируем нормировку по первому таргету (как и раньше)
            i0 = names.index(targets[0])
            d0 = dx_frac[0]
            fr_star = normalize_composition_general(fr, i=i0, delta_xi=d0,
                                                    upp_indices=names_to_indices(names, upp_names))
            final_comp = _to_percent_dict(names, fr_star, decimals=decimals, fix_to=fix_sum_to or methane_name)

        else:
            # ВАЖНО: «метан по разности» — меняем ВСЕ таргеты и компенсируем метаном суммарно
            final_comp = final_comp.copy()
            total_delta_pp = 0.0
            for t, dfrac in zip(targets, dx_frac):
                d_pp = dfrac * 100.0  # перевод доли -> п.п.
                final_comp[t] = final_comp.get(t, 0.0) + d_pp
                total_delta_pp += d_pp

            if methane_name not in final_comp:
                raise CalcThetaError("Methane не найден для режима 'по разности'.")

            final_comp[methane_name] = final_comp[methane_name] - total_delta_pp

            # никаких дополнительных масштабирований и округлений
            # (сумма должна остаться ~100, если исходная была 100)

        # --- Проверка в конце ---
        issues1 = validate_comp_once(final_comp, error_composition=error_composition, upp_names=upp_names)
        issues1 += end_policy_invariants(composition, final_comp, policy=policy,
                                         target_names=targets, methane_name=methane_name, upp_names=upp_names)

    return {
        "policy": policy,
        "upp": upp_names,
        "targets": targets,
        "delta_pp_used": {n: deltas_pp[n] for n in targets},
        "theta_vec": theta_vec,
        "dx_frac": dx_frac,
        "delta_rho_1029": delta_rho_1029,
        "delta_rho_1028": delta_rho_1028,
        "begin_check_issues": issues0,   # проверка №1
        "end_check_issues": issues1,     # проверка №2 (по «финальному» примеру)
        "final_comp_example": final_comp # пример нормированного состава
    }

# ========= ДЕМО =========
if __name__ == "__main__":
    composition = {
        "CarbonDioxide": 2.5, "Ethane": 6, "Helium": 0.015, "Hydrogen": 0.005, "Methane": 87.535,
        "Nitrogen": 1, "Oxygen": 0.05, "Propane": 2, "iButane": 0.5, "iPentane": 0.045, "nButane": 0.3, "nPentane": 0.05
    }
    error_composition = {
        "CarbonDioxide": {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.05, "unit": "percent"}}},
        "Ethane":        {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.10, "unit": "percent"}}},
        "Helium":        {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.005, "max": 0.015}}}},
        "Hydrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.001, "max": 0.005}}}},
        "Methane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.10, "unit": "percent"}}},
        "Nitrogen":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.2, "max": 1.0}}}},
        "Oxygen":        {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.005, "max": 0.05}}}},
        "Propane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.5, "max": 2.0}}}},
        "iButane":       {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.1, "max": 0.5}}}},
        "iPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.018, "max": 0.045}}}},
        "nButane":       {"intrError": {"errorTypeId": "AbsErr", "value": {"real": 0.05, "unit": "percent"}}},
        "nPentane":      {"intrError": {"errorTypeId": "UppErr", "range": {"range": {"min": 0.01, "max": 0.05}}}},
    }

    res = run_method10(composition, error_composition, mode="methane_by_diff",
                       methane_name="Methane",
                       deltas_override_pp={"Ethane": 0.12, "CarbonDioxide": 0.07},
                       decimals=None)

    print("policy:", res["policy"])
    print("targets:", res["targets"])
    print("final_comp_example sum:", sum(res["final_comp_example"].values()))
    print("end_check_issues:", res["end_check_issues"])
