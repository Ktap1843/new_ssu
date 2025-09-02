# -*- coding: utf-8 -*-
from __future__ import annotations
import math
from dataclasses import dataclass, asdict, field
from typing import Optional, Dict, Any, Tuple

R_UNIVERSAL = 8.314462618
M_WATER = 0.01801528

from gsssd_mr_147_2008.GSSSD_147_2008 import calc_single_phase, get_Taus, get_W12, get_W, get_W0, get_Ro, get_Pi_Tau
from gsssd_mr_147_2008.tables import Pkr, Tkr

try:
    from gsssd_hooks import (
        Tsat_at_p as gsssd_Tsat_at_p,
        rho_sat_vapor_at_p as gsssd_rho_sat_vapor_at_p,
        rho_superheated as gsssd_rho_superheated,
    )
except Exception:
    gsssd_Tsat_at_p = gsssd_rho_sat_vapor_at_p = gsssd_rho_superheated = None


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


def Q_std_dry(m_dot_dry: float,
              rho_std_dry: Optional[float] = None,
              *, p_std: Optional[float] = None,
              T_std: Optional[float] = None,
              Mmix_dry: Optional[float] = None,
              Zc_std: Optional[float] = 1.0) -> Dict[str, float]:
    if rho_std_dry is None:
        if None in (p_std, T_std, Mmix_dry):
            raise ValueError("Нужно либо rho_std_dry, либо (p_std, T_std, Mmix_dry).")
        rho_std_dry = rho_std_dry_from_state(p_std, T_std, Mmix_dry, Zc_std)
    return {"Q_std_dry": m_dot_dry / rho_std_dry, "rho_std_dry": rho_std_dry}


def f_abs_from_phi(phi_rel: float, rho_sat: Optional[float]) -> Tuple[Optional[float], list[str]]:
    warns: list[str] = []
    if rho_sat is None:
        warns.append("Для f по φ нужна rho_vapor_sat_at_p (плотность насыщенного водяного пара при рабочих условиях).")
        return None, warns
    phi = phi_rel / 100.0 if phi_rel > 1.0 else phi_rel
    return phi * rho_sat, warns


def vapor_max_at_state(*,
                       p: Optional[float], T: Optional[float],
                       T_sat_at_p: Optional[float],
                       rho_vapor_sat_at_p: Optional[float],
                       rho_vapor_superheated: Optional[float]) -> Tuple[Optional[float], Dict[str, Any], list[str]]:
    meta: Dict[str, Any] = {}
    warns: list[str] = []
    if p is None or T is None:
        return None, meta, ["Нужны p_work и T_work для предела водяного пара."]
    if T_sat_at_p is None:
        if gsssd_Tsat_at_p is not None:
            T_sat_at_p = gsssd_Tsat_at_p(p)
        else:
            return None, meta, ["T_sat_at_p не задана."]
    mode = "saturated" if (T <= T_sat_at_p) else "superheated"
    meta["mode"] = mode
    if mode == "saturated":
        if rho_vapor_sat_at_p is None and gsssd_rho_sat_vapor_at_p is not None:
            rho_vapor_sat_at_p = gsssd_rho_sat_vapor_at_p(p)
        return rho_vapor_sat_at_p, meta, ([] if rho_vapor_sat_at_p is not None else ["rho_vapor_sat_at_p не задана."])
    else:
        if rho_vapor_superheated is None and gsssd_rho_superheated is not None:
            rho_vapor_superheated = gsssd_rho_superheated(p, T)
        return rho_vapor_superheated, meta, ([] if rho_vapor_superheated is not None else ["rho_vapor_superheated не задана."])


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


def compute(payload: Dict[str, Any]) -> ComputeResult:
    inp = ComputeInput(**payload)
    res = ComputeResult()

    rho_cap, meta_vp, warns_vp = vapor_max_at_state(
        p=inp.p_work, T=inp.T_work,
        T_sat_at_p=inp.T_sat_at_p,
        rho_vapor_sat_at_p=inp.rho_vapor_sat_at_p,
        rho_vapor_superheated=inp.rho_vapor_superheated,
    )
    res.details["vapor_cap"] = meta_vp
    res.warnings.extend(warns_vp)

    if inp.Q is None:
        raise ValueError("Не задан Q.")
    if inp.m_dot is None:
        if inp.rho_wet is None:
            raise ValueError("Нужно m_dot или (rho_wet и Q).")
        res.m_dot = mdot_from_rho_Q(inp.rho_wet, inp.Q)
    else:
        res.m_dot = inp.m_dot

    res.Q = inp.Q
    if inp.rho_wet is not None:
        res.rho_wet = inp.rho_wet
    elif res.m_dot is not None and inp.Q != 0:
        res.rho_wet = res.m_dot / inp.Q

    res.f_abs_input = inp.f_abs
    f_eff = inp.f_abs
    if f_eff is None and inp.phi_rel is not None:
        f_est, warns = f_abs_from_phi(inp.phi_rel, inp.rho_vapor_sat_at_p)
        res.warnings.extend(warns)
        f_eff = f_est
    if f_eff is None:
        f_eff = 0.0
    if inp.enforce_vapor_cap and (rho_cap is not None) and (f_eff is not None) and (f_eff > rho_cap):
        f_eff = rho_cap
        res.details["vapor_cap"]["cap_applied"] = True
    else:
        res.details["vapor_cap"]["cap_applied"] = False
    res.f_abs_effective = f_eff

    res.m_dot_dry = mdot_dry_core(res.m_dot, inp.Q, f_eff)

    if res.m_dot_dry is not None:
        try:
            qsd = Q_std_dry(res.m_dot_dry, rho_std_dry=inp.rho_std_dry,
                            p_std=inp.p_std, T_std=inp.T_std, Mmix_dry=inp.Mmix_dry, Zc_std=inp.Zc_std)
            res.Q_std_dry = qsd["Q_std_dry"]
            res.rho_std_dry = qsd["rho_std_dry"]
        except ValueError as e:
            res.warnings.append(str(e))

    re = reynolds(m_dot=res.m_dot, Q=res.Q, rho=res.rho_wet, mu=inp.mu_wet, D=inp.D_pipe)
    if re is not None:
        res.details["Re_wet"] = re

    return res


def compute_asdict(payload: Dict[str, Any]) -> Dict[str, Any]:
    return asdict(compute(payload))
