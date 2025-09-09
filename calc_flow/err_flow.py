# calc_flow/err_flow.py
from __future__ import annotations

import math
from typing import Tuple, Mapping, Any


# --- утилиты ---
def _rss(values):
    s = 0.0
    for v in values:
        if v is None:
            continue
        x = float(v)
        s += x * x
    return s ** 0.5

def _rel_of(node: Any) -> float | None:
    """Берём node['rel'] если это словарь вида {'rel': ...}."""
    if isinstance(node, Mapping) and "rel" in node:
        try:
            return float(node["rel"])
        except Exception:
            return None
    return None


class SimpleErrFlow:
    """
    Минималистичный класс для расчёта:
      1) Геометрические чувствительности v_D, v_d (10.16–10.21) → sensitivities_geom()
      2) Вклад C и ε: coeff_C(), coeff_epsilon()  (ε по 10.22 — БЕЗ коэффициентов чувствительности)
      3) Итоговые погрешности расходов: flow_mass(), flow_vol_actual(), flow_vol_std()

    Никаких коэффициентов чувствительности здесь нет — только «чистые» относительные вклады.
    """

    def __init__(self, *, ssu_type: str, beta: float, d: float | None = None, D: float | None = None, phase: str = "gas"):
        self.type = (ssu_type or "").lower()
        self.beta = float(beta)
        self.d = None if d is None else float(d)
        self.D = None if D is None else float(D)
        self.phase = (phase or "gas").lower()

    # ------------- (1) Геом. чувствительности 10.16–10.21 -------------
    def sensitivities_geom(self) -> Tuple[float, float]:
        """
        Вернёт (v_D, v_d) по формулам 10.16–10.21.
        Используются self.type, self.beta, self.d, self.D.
        """
        if not (0.0 < self.beta < 1.0):
            raise ValueError("beta должна быть в (0,1) для расчёта v_D, v_d")

        b = self.beta
        t = self.type
        # считаем 'conical' как 'cone'
        if t in ("cone", "conical"):
            # 10.16–10.17 для конической
            v_D = 2 * (1 + b**2 + b**4) / (b**2 * (1 + b**2))
            v_d = 2 / (b**2 * (1 + b**2))
        elif t in ("wedge", "segment"):
            if not (self.d and self.D and self.D != 0.0):
                raise ValueError("для wedge/segment нужны d и D")
            otn = self.d / self.D  # d/D
            # 10.18–10.21
            root_term = max(otn * (1.0 - otn), 0.0)
            sqrt_val = math.sqrt(root_term)
            denom = math.pi * b**2 * (1.0 - b**4)
            if denom == 0.0:
                raise ZeroDivisionError("некорректная beta для wedge/segment")
            v_piece = (8.0 * otn * sqrt_val) / denom
            v_D = 2.0 - v_piece
            v_d = v_piece
        else:
            # generic sharp-edged orifice
            denom = (1.0 - b**4)
            if denom <= 0.0:
                raise ValueError("1 - beta^4 должно быть > 0")
            v_D = 2.0 * (b**4) / denom
            v_d = 2.0 / denom

        return float(v_D), float(v_d)

    # ------------- (2) Вклады C и ε -------------
    @staticmethod
    def coeff_C(u_d_Cm: float | None) -> float:
        """Относительная погрешность C: подаём уже посчитанную d_Cm (в долях)."""
        if u_d_Cm is None:
            return 0.0
        return abs(float(u_d_Cm))

    @staticmethod
    def coeff_epsilon(*, epsilon: float, u_epsm: float | None, u_dp: float | None, u_p: float | None, u_k: float = 0.0) -> float:
        """
        Формула 10.22 БЕЗ коэффициентов чувствительности:
            u_ε = sqrt( u_εm^2 + (ε - 1)^2 * (u_dp^2 + u_p^2 + u_k^2) )
        Все входы — относительные (доли), epsilon — числовое значение ε.
        """
        e = float(epsilon)
        ue = 0.0 if u_epsm is None else float(u_epsm)
        udp = 0.0 if u_dp   is None else float(u_dp)
        up  = 0.0 if u_p    is None else float(u_p)
        uk  = float(u_k or 0.0)
        return _rss([ue, (e - 1.0) * udp, (e - 1.0) * up, (e - 1.0) * uk])

    # ------------- (3) Итоговые расходы 10.13–10.15 (унифицированный вид) -------------
    @staticmethod
    def flow_mass(*, u_C: float, u_eps: float, u_dp: float, u_rho: float = 0.0, u_geom: float = 0.0, u_corr: float = 0.0) -> float:
        """
        Массовый расход (10.13—обобщённо): u_Qm = sqrt( u_C^2 + u_ε^2 + u_Δp^2 + u_ρ^2 + u_geom^2 + u_corr^2 )
        Все величины — относительные (доли).
        """
        return _rss([u_C, u_eps, u_dp, u_rho, u_geom, u_corr])

    @staticmethod
    def flow_vol_actual(*, u_C: float, u_eps: float, u_dp: float, u_rho: float = 0.0, u_geom: float = 0.0, u_corr: float = 0.0) -> float:
        """
        Объёмный в рабочих условиях (10.14—обобщённо): тот же корень — плотность берётся «рабочая».
        """
        return _rss([u_C, u_eps, u_dp, u_rho, u_geom, u_corr])

    @staticmethod
    def flow_vol_std(*, u_C: float, u_eps: float, u_dp: float, u_rho_std: float = 0.0, u_geom: float = 0.0, u_corr: float = 0.0) -> float:
        """
        Объёмный в стандартных условиях (10.15—обобщённо): вместо u_ρ — u_ρ,std.
        """
        return _rss([u_C, u_eps, u_dp, u_rho_std, u_geom, u_corr])

    # ------------- мини-репорт только по расходам -------------
    @staticmethod
    def report(u_Qm: float, u_Qv: float, u_Qstd: float) -> dict:
        return {
            "u_Qm":   {"rel": u_Qm,   "percent": u_Qm * 100.0},
            "u_Qv":   {"rel": u_Qv,   "percent": u_Qv * 100.0},
            "u_Qstd": {"rel": u_Qstd, "percent": u_Qstd * 100.0},
        }


# ======================================================================================
# Песочница: одна функция, чтобы быстро «поиграться» параметрами на твоём payload’е
# ======================================================================================

def try_errors_flow(payload: Mapping[str, Any], *, u_rho: float = 0.0, u_rho_std: float = 0.0, u_geom: float = 0.0, u_corr: float | None = None) -> dict:
    """
    Быстрый прогон на словаре как у тебя в result_dict.
    Возвращает словарь с (v_D, v_d), u_C, u_eps и errors_flow (три расхода).
    Ничего не валидирует жёстко – если чего нет, подставляет 0.
    """
    ssu_type = (payload.get("type") or "").lower()
    beta     = payload.get("beta")
    d        = payload.get("d")
    D        = payload.get("D")

    # конструктор
    ef = SimpleErrFlow(ssu_type=ssu_type, beta=float(beta), d=d, D=D, phase="gas")

    # 1) геометрические чувствительности, если нужны
    v_D = v_d = None
    try:
        v_D, v_d = ef.sensitivities_geom()
    except Exception:
        # ок, просто пропустим, если чего-то нет
        pass

    # 2) вклад C и ε
    u_C = SimpleErrFlow.coeff_C(payload.get("d_Cm"))

    epsilon  = payload.get("epsilon", 1.0)
    inputs   = (payload.get("errors") or {}).get("inputs_rel") or {}
    u_dp     = _rel_of(inputs.get("dp"))
    # берём p или p_abs — что найдём
    u_p      = _rel_of(inputs.get("p")) if _rel_of(inputs.get("p")) is not None else _rel_of(inputs.get("p_abs"))
    u_corr_  = _rel_of(inputs.get("corrector"))
    if u_corr is None:
        u_corr = 0.0 if u_corr_ is None else float(u_corr_)

    u_eps = SimpleErrFlow.coeff_epsilon(
        epsilon=float(epsilon),
        u_epsm=payload.get("d_Epsilonm"),
        u_dp=u_dp,
        u_p=u_p,
        u_k=0.0,
    )

    # 3) расходы
    u_dp_val = 0.0 if u_dp is None else float(u_dp)
    u_Qm   = SimpleErrFlow.flow_mass(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho=float(u_rho),     u_geom=float(u_geom), u_corr=float(u_corr))
    u_Qv   = SimpleErrFlow.flow_vol_actual(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho=float(u_rho),     u_geom=float(u_geom), u_corr=float(u_corr))
    u_Qstd = SimpleErrFlow.flow_vol_std(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho_std=float(u_rho_std), u_geom=float(u_geom), u_corr=float(u_corr))

    out = {
        "v_D": v_D,
        "v_d": v_d,
        "u_C": u_C,
        "u_eps": u_eps,
        "errors_flow": SimpleErrFlow.report(u_Qm, u_Qv, u_Qstd),
    }

    # печать для «поиграться»
    print("=== ERR FLOW DEMO ===")
    print(f"type={ssu_type}, beta={beta}, d={d}, D={D}")
    if v_D is not None:
        print(f"v_D={v_D:.6g}, v_d={v_d:.6g}")
    print(f"u_C={u_C:.6g}, u_eps={u_eps:.6g}, u_dp={u_dp_val:.6g}, u_rho={float(u_rho):.6g}, u_rho_std={float(u_rho_std):.6g}, u_geom={float(u_geom):.6g}, u_corr={float(u_corr):.6g}")
    print("u_Qm  = {rel:.6g} ({percent:.4f} %)".format(**out["errors_flow"]["u_Qm"]))
    print("u_Qv  = {rel:.6g} ({percent:.4f} %)".format(**out["errors_flow"]["u_Qv"]))
    print("u_Qstd= {rel:.6g} ({percent:.4f} %)".format(**out["errors_flow"]["u_Qstd"]))
    print("======================")

    return out


# --- пример локального запуска (закомментируй/оставь для теста) ---
if __name__ == "__main__":
    example = {
        'type': 'conical',
        'D': 0.0999978976, 'd': 0.029999369279999997,
        'epsilon': 0.9980521444907964, 'beta': 0.3,
        'd_Cm': 1.0, 'd_Epsilonm': None,
        'errors': {'inputs_rel': {
            'corrector': {'rel': 0.01}, 'T': {'rel': 0.00384},
            'p': {'rel': 0.0031869}, 'dp': {'rel': 0.02}
        }}
    }
    try_errors_flow(example, u_rho=0.0, u_rho_std=0.0, u_geom=0.0, u_corr=None)
