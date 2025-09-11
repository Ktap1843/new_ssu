from __future__ import annotations
import math
from typing import Tuple, Mapping, Any

def _rss(values):
    s = 0.0
    for v in values:
        if v is None:
            continue
        x = float(v)
        s += x * x
    return s ** 0.5

def _rel_of(node: Any) -> float | None:
    if isinstance(node, Mapping) and "rel" in node:
        try:
            return float(node["rel"])
        except Exception:
            return None
    return None


class SimpleErrFlow:
    def __init__(self, *, ssu_type: str, beta: float, d: float | None = None, D: float | None = None, phase: str = "gas", phys_block: dict):
        self.type = (ssu_type or "").lower()
        self.beta = float(beta)
        self.d = None if d is None else float(d)
        self.D = None if D is None else float(D)
        self.phase = (phase or "gas").lower()
        self.phys_block = phys_block


    def sensitivities_geom(self) -> Tuple[float, float]:
        if not (0.0 < self.beta < 1.0):
            raise ValueError("beta должна быть в (0,1) для расчёта v_D, v_d")

        b = self.beta
        t = self.type
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
            denom = (1.0 - b**4)
            if denom <= 0.0:
                raise ValueError("1 - beta^4 должно быть > 0")
            v_D = 2.0 * (b**4) / denom
            v_d = 2.0 / denom

        return float(v_D), float(v_d)

    def density_uncertainties(self, Xa: float | None = None, Xy: float | None = None, u_Xa: float = 0.0, u_Xy: float = 0.0,
                              u_T: float = 0.0, u_p: float = 0.0, u_N: dict | None = None ) -> dict:
        try:
            pb = self.phys_block or {}
            th = (pb.get("thetas") or {})

            err_rho = pb.get("err_ro", pb.get("err_rho"))
            err_rho_st = pb.get("err_ro_st", pb.get("err_rho_st"))
            rho = pb.get("rho")
            rho_st = pb.get("rho_st")
            u_rho_ref = (float(err_rho) / float(rho)) if (err_rho is not None and rho) else 0.0
            u_rho_stdref = (float(err_rho_st) / float(rho_st)) if (err_rho_st is not None and rho_st) else 0.0
            th_T = float(th.get("theta_rho_T", 0.0))
            th_p = float(th.get("theta_rho_p_abs", th.get("theta_rho_p", 0.0)))
            th_Xa = float(th.get("theta_rho_Xa", 0.0))
            th_Xy = float(th.get("theta_rho_Xy", 0.0))
            th_N = float(th.get("theta_rho_N", 0.0))
            s2 = u_rho_ref ** 2 + (th_T * u_T) ** 2 + (th_p * u_p) ** 2
            if not u_N and (Xa is None and Xy is None):
                pass
            elif (Xa is not None) or (Xy is not None):
                s2 += (th_Xa * u_Xa) ** 2 + (th_Xy * u_Xy) ** 2
            elif u_N:
                dx = float(u_N.get("N", 0.0))
                s2 += (th_N * dx) ** 2

            u_rho = s2 ** 0.5

            s2c = u_rho_stdref ** 2

            if not u_N and (Xa is None and Xy is None):
                pass
            elif (Xa is not None) or (Xy is not None):
                s2c += (th_Xa * u_Xa) ** 2 + (th_Xy * u_Xy) ** 2
            elif u_N:
                dx = float(u_N.get("N", 0.0))
                s2c += (th_N * dx) ** 2

            u_rhoc = s2c ** 0.5

            return u_rho, u_rhoc

        except Exception:
            log.error("Упал расчет огрешности плотности")
            return None

    @staticmethod
    def coeff_C(u_d_Cm: float | None) -> float:
        if u_d_Cm is None:
            return 0.0
        return abs(float(u_d_Cm))

    @staticmethod
    def coeff_epsilon(*, epsilon: float, u_epsm: float | None, u_dp: float | None, u_p: float | None, u_k: float = 0.0) -> float:
        e = float(epsilon)
        ue = 0.0 if u_epsm is None else float(u_epsm)
        udp = 0.0 if u_dp   is None else float(u_dp)
        up  = 0.0 if u_p    is None else float(u_p)
        uk  = float(u_k or 0.0)
        return _rss([ue, (e - 1.0) * udp, (e - 1.0) * up, (e - 1.0) * uk])

    @staticmethod
    def flow_mass(*, u_C: float, u_eps: float, u_dp: float, u_rho: float = 0.0, u_v_D, u_v_d: float = 0.0, u_corr: float = 0.0) -> float:
        return _rss([u_C, u_eps, u_dp, u_rho, u_v_D, u_v_d, u_corr])

    @staticmethod
    def flow_vol_actual(*, u_C: float, u_eps: float, u_dp: float, u_rho: float = 0.0, u_v_D, u_v_d: float = 0.0, u_corr: float = 0.0) -> float:
        return _rss([u_C, u_eps, u_dp, u_rho, u_v_D, u_v_d, u_corr])

    @staticmethod
    def flow_vol_std(*, u_C: float, u_eps: float, u_dp: float, u_rho_std: float = 0.0, u_v_D, u_v_d: float = 0.0, u_corr: float = 0.0) -> float:
        return _rss([u_C, u_eps, u_dp, u_rho_std, u_v_D, u_v_d, u_corr])


    @staticmethod
    def report(u_Qm: float, u_Qv: float, u_Qstd: float) -> dict:
        return {
            "u_Qm":   {"rel": u_Qm},
            "u_Qv":   {"rel": u_Qv},
            "u_Qstd": {"rel": u_Qstd},
        }








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
        'type': 'sharp',
        'D': 0.0499973825, 'd': 0.019998953,
        'epsilon': 0.9980521444907964, 'beta': 0.4,
        'd_Cm': 0.46573788716181386, 'd_Epsilonm': 0.028,
        'errors': {'inputs_rel': {
            'corrector': {'rel': 0.01}, 'T': {'rel': 0.00384},
            'p': {'rel': 0.0031869}, 'dp': {'rel': 0.02}
        }}
    }
    try_errors_flow(example, u_rho=0.0, u_rho_std=0.0, u_geom=0.0, u_corr=None)
