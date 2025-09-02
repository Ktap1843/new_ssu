from __future__ import annotations
import math
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, Tuple
from gsssd_mr_147_2008.GSSSD_147_2008 import calc_single_phase, get_Taus, get_W12, get_W, get_W0, get_Ro, get_Pi_Tau
from gsssd_mr_147_2008.tables import Pkr, Tkr



# хуки ДЛЯ ГСССД 147-2008
def gsssd_Tsat_at_p(p: float) -> float:
    """На линии насыщения температура водняного пара"""
    pi = p / Pkr
    tau = get_Taus(pi)
    T = tau * Tkr
    return T

def gsssd_rho_sat_vapor_at_p(p: float) -> float:
    """На линии насыщения плотность водняного пара"""
    pi = p / Pkr
    tau_s = get_Taus(pi)
    W1, W2 = get_W12(tau_s)
    w2 = get_W(W2, pi, tau_s)
    rho_sat = get_Ro(w2)
    return rho_sat

def gsssd_rho_superheated(p: float, T: float) -> float:
    Ro, H, K, Mu = calc_single_phase(p, T)
    return Ro

def gsssd_Z_vapor(p_Pa: float, T_K: float) -> float:
    raise NotImplementedError("gsssd_Z_vapor(p,T)")


@dataclass
class ComputeInput:
    Q: Optional[float] = None
    m_dot: Optional[float] = None
    rho_wet: Optional[float] = None

    f_abs: Optional[float] = None
    phi_rel: Optional[float] = None

    rho_std_dry: Optional[float] = None
    p_std: Optional[float] = None
    T_std: Optional[float] = None
    Mmix_dry: Optional[float] = None
    Zc_std: Optional[float] = None

    p_work: Optional[float] = None
    T_work: Optional[float] = None
    T_sat_at_p: Optional[float] = None
    rho_vapor_sat_at_p: Optional[float] = None
    rho_vapor_superheated: Optional[float] = None
    Z_vapor: Optional[float] = None

    enforce_vapor_cap: bool = True

    mu_wet: Optional[float] = None
    D_pipe: Optional[float] = None


@dataclass
class ComputeResult:
    Q: Optional[float] = None
    m_dot: Optional[float] = None
    rho_wet: Optional[float] = None
    f_abs_input: Optional[float] = None
    f_abs_effective: Optional[float] = None
    m_dot_dry: Optional[float] = None
    Q_std_dry: Optional[float] = None
    rho_std_dry: Optional[float] = None
    warnings: list[str] = field(default_factory=list)
    details: Dict[str, Any] = field(default_factory=dict)


def mdot_from_rho_Q(rho: float, Q: float) -> float:
    return rho * Q

def mdot_dry_core(m_dot: float, Q: float, f_abs_effective: float) -> float:
    return m_dot - f_abs_effective * Q

def rho_std_dry_from_state(p_std: float, T_std: float, Mmix_dry: float, Zc_std: Optional[float] = 1.0) -> float:
    Z = 1.0 if (Zc_std is None or Zc_std == 0) else Zc_std
    return p_std * Mmix_dry / (Z * R_UNIVERSAL * T_std)
R_UNIVERSAL = 8.314462618
M_WATER = 0.01801528
def Q_std_dry(m_dot_dry: float,
              rho_std_dry: Optional[float] = None,
              *, p_std: Optional[float] = None,
              T_std: Optional[float] = None,
              Mmix_dry: Optional[float] = None,
              Zc_std: Optional[float] = 1.0) -> Dict[str, float]:
    """(Б.4–Б.5)"""
    used = {"variant": "Q_std_dry = m_dot_dry / rho_std_dry"}
    if rho_std_dry is None:
        if None in (p_std, T_std, Mmix_dry):
            raise ValueError("Нужно либо rho_std_dry, либо (p_std, T_std, Mmix_dry).")
        rho_std_dry = rho_std_dry_from_state(p_std, T_std, Mmix_dry, Zc_std)
        used["rho_std_dry_source"] = "state_equation"
    else:
        used["rho_std_dry_source"] = "input"
    return {"Q_std_dry": m_dot_dry / rho_std_dry, "rho_std_dry": rho_std_dry, "used": used}

def reynolds(m_dot: Optional[float] = None,
             Q: Optional[float] = None,
             rho: Optional[float] = None,
             mu: Optional[float] = None,
             D: Optional[float] = None) -> Optional[float]:
    if mu is None or D is None:
        return None
    if Q is not None and D > 0:
        v = 4.0 * Q / (math.pi * D * D)
        return (rho if rho else 0.0) * v * D / mu
    if (m_dot is not None) and (rho is not None) and D > 0:
        v = 4.0 * m_dot / (math.pi * rho * D * D)
        return rho * v * D / mu
    return None

def vapor_max_at_state(
    *, p: Optional[float], T: Optional[float],
    T_sat_at_p: Optional[float],
    rho_vapor_sat_at_p: Optional[float],
    rho_vapor_superheated: Optional[float]) -> Tuple[Optional[float], Optional[float], Dict[str, Any], list[str]]:
    """
    Возвращает (rho_vp_max, p_vp_max, meta, warnings):
      - если T ≤ T_sat(p):  rho_(в.п max)=rho_нас,  p_(в.п max)=p_нас
      - если T > T_sat(p):  rho_(в.п max)=rho(перегретого), p_(в.п max)=p (газа)
    """
    meta: Dict[str, Any] = {}
    warnings: list[str] = []
    if p is None or T is None:
        warnings.append("Для предела по пару нужны p_work и T_work.")
        return None, None, meta, warnings

    if T_sat_at_p is None:
        warnings.append("T_sat_at_p не задана — сравнение T с T_sat(p) невозможно.")
    else:
        meta["T_sat_at_p"] = T_sat_at_p

    mode = None
    if T_sat_at_p is not None:
        mode = "saturated" if (T <= T_sat_at_p) else "superheated"
    meta["mode"] = mode

    rho_vp_max: Optional[float] = None
    p_vp_max: Optional[float] = None

    if mode == "saturated":
        if rho_vapor_sat_at_p is not None:
            rho_vp_max = rho_vapor_sat_at_p
            meta["rho_source"] = "rho_vapor_sat_at_p"
        else:
            warnings.append("rho_нас не задана (rho_vapor_sat_at_p).")
        p_vp_max = p
        meta["p_vp_max_reason"] = "saturated"
    elif mode == "superheated":
        if rho_vapor_superheated is not None:
            rho_vp_max = rho_vapor_superheated
            meta["rho_source"] = "rho_vapor_superheated"
        else:
            warnings.append("rho(перегретого) не задана (rho_vapor_superheated).")
        p_vp_max = p
        meta["p_vp_max_reason"] = "superheated"
    else:
        # Без T_sat(p) — берём, что есть
        if rho_vapor_superheated is not None:
            rho_vp_max = rho_vapor_superheated
            meta["rho_source"] = "rho_vapor_superheated_no_Tsat"
            p_vp_max = p
        elif rho_vapor_sat_at_p is not None:
            rho_vp_max = rho_vapor_sat_at_p
            meta["rho_source"] = "rho_vapor_sat_at_p_no_Tsat"
            p_vp_max = p
        else:
            warnings.append("Нет данных для rho_(в.п max). Передай T_sat_at_p и/или плотности пара.")

    return rho_vp_max, p_vp_max, meta, warnings


def f_abs_from_phi(phi_rel: float, rho_sat: Optional[float]) -> Tuple[Optional[float], list[str]]:
    """Б.8–Б.10"""
    warns: list[str] = []
    if rho_sat is None:
        warns.append("Для f по fi нужна rho_нас (rho_vapor_sat_at_p).")
        return None, warns
    phi = phi_rel / 100.0 if phi_rel > 1.0 else phi_rel
    return phi * rho_sat, warns



def compute(payload: Dict[str, Any]) -> ComputeResult:
    inp = ComputeInput(**payload)
    res = ComputeResult()

    rho_vp_max, p_vp_max, meta_vp, warns_vp = vapor_max_at_state(
        p=inp.p_work, T=inp.T_work,
        T_sat_at_p=inp.T_sat_at_p,
        rho_vapor_sat_at_p=inp.rho_vapor_sat_at_p,
        rho_vapor_superheated=inp.rho_vapor_superheated,
    )
    res.details["vapor_cap"] = {"rho_vp_max": rho_vp_max, "p_vp_max": p_vp_max, **meta_vp}
    res.warnings.extend(warns_vp)

    #(Б.2)
    if inp.Q is None:
        raise ValueError("Не задан Q (м³/с).")
    if inp.m_dot is None:
        if inp.rho_wet is None:
            raise ValueError("Нужно задать либо m_dot, либо пару (rho_wet и Q).")
        res.m_dot = mdot_from_rho_Q(inp.rho_wet, inp.Q)
    else:
        res.m_dot = inp.m_dot

    # 2) rho_wet
    res.Q = inp.Q
    if inp.rho_wet is not None:
        res.rho_wet = inp.rho_wet
    elif res.m_dot is not None and inp.Q > 0:
        res.rho_wet = res.m_dot / inp.Q

    # 3) Абсолютная влажность
    res.f_abs_input = inp.f_abs
    f_eff = inp.f_abs
    if f_eff is None and inp.phi_rel is not None:
        f_est, warns = f_abs_from_phi(inp.phi_rel, inp.rho_vapor_sat_at_p)
        res.warnings.extend(warns)
        f_eff = f_est
    if f_eff is None:
        f_eff = 0.0
        res.warnings.append("f_abs не задан — принято 0.0 (условно сухой газ).")

    # 4)rho_(в.п max)
    if inp.enforce_vapor_cap and (rho_vp_max is not None):
        if f_eff > rho_vp_max:
            res.warnings.append(
                f"f={f_eff:g} кг/м³ ограничена сверху rho_(в.п max)={rho_vp_max:g} кг/м³ (примечание Прил. Б)."
            )
            f_eff = rho_vp_max
        res.details["vapor_cap"]["cap_applied"] = True
    else:
        res.details["vapor_cap"]["cap_applied"] = False
    res.f_abs_effective = f_eff

    #Б.1/Б.3
    res.m_dot_dry = mdot_dry_core(res.m_dot, inp.Q, f_eff)

    # Б.4–Б.5
    if res.m_dot_dry is not None:
        try:
            qsd = Q_std_dry(
                res.m_dot_dry,
                rho_std_dry=inp.rho_std_dry,
                p_std=inp.p_std, T_std=inp.T_std,
                Mmix_dry=inp.Mmix_dry, Zc_std=inp.Zc_std
            )
            res.Q_std_dry = qsd["Q_std_dry"]
            res.rho_std_dry = qsd["rho_std_dry"]
            res.details["std_variant"] = qsd.get("used", {})
        except ValueError as e:
            res.warnings.append(str(e))

    # Б.11
    re = reynolds(m_dot=res.m_dot, Q=res.Q, rho=res.rho_wet, mu=inp.mu_wet, D=inp.D_pipe)
    if re is not None:
        res.details["Re_wet"] = re

    return res


def compute_asdict(payload: Dict[str, Any]) -> Dict[str, Any]:
    return asdict(compute(payload))
