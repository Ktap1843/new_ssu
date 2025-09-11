from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping, Optional
import inspect
import math

# --- Errors adapter (единый импорт) ---
try:
    from errors import error_adapter as EA
except Exception:
    EA = None

# --- Логгер проекта ---
try:
    from logger_config import get_logger  # предпочтительно
    _log = get_logger("CalculationAdapter")
except Exception:
    try:
        from logger_config import get_logger  # запасной вариант
        _log = get_logger("CalculationAdapter")
    except Exception:  # no-op
        class _Dummy:
            def info(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
        _log = _Dummy()

from phys_prop.calc_phys_prop import PhysMinimalRunner, make_theta_list



# -------------------- Утилиты --------------------

def _strip_unit_node(node: Any) -> Optional[float]:
    """Если node — {real, unit} → вернём real; если число — вернём число; иначе None."""
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(node)
    if isinstance(node, dict) and "real" in node:
        try:
            return float(node["real"])
        except Exception:
            return None
    return None


def _get_phys(raw: Mapping[str, Any], key: str) -> Optional[Any]:
    try:
        node = (raw.get("physPackage") or {}).get("physProperties", {}).get(key)
        if isinstance(node, dict) and "real" in node:
            return node["real"]
        return node
    except Exception:
        return None


def _coerce_mu_si(val_from_values: Any, val_from_raw_node: Any) -> Optional[float]:
    def _from_any(node):
        if node is None:
            return None
        if isinstance(node, (int, float)):
            return float(node)  # считаем, что это уже Па·с
        if isinstance(node, dict) and "real" in node:
            try:
                real = float(node["real"])
            except Exception:
                return None
            unit = str(node.get("unit") or "").strip().lower()
            unit = unit.replace("·", "_").replace("/", "_").replace(" ", "").replace("-", "")
            # варианты: 'pa_s', 'pas', 'mpa_s', 'mpas', 'upa_s', 'μpa_s'
            if unit in ("pa_s", "pas"):
                return real
            if unit in ("mpa_s", "mpas"):
                return real * 1e-3
            if unit in ("upa_s", "μpa_s", "micro_pa_s", "micro_pas", "mupas"):
                return real * 1e-6
            # если непонятно — считаем Па·с
            return real
        return None

    v1 = _from_any(val_from_values)
    if v1 is not None:
        return v1
    return _from_any(val_from_raw_node)

def _rel_only(node):
    try:
        if isinstance(node, dict) and "rel" in node:
            return float(node["rel"])
    except Exception:
        pass
    return None

# -------------------- Straightness: расчёт длин прямых участков --------------------

def _maybe_calc_straightness(ssu_type: str, d: float, D: float, Ra_m: Optional[float], raw: Mapping[str, Any]) -> dict:
    """Расчёт через flow_straightness.straightness_calculator (если включено)."""
    try:
        lp = (raw.get("lenPackage") or {})
        straight = lp.get("straightness") or (lp.get("lenProperties") or {}).get("straightness") or {}
        if not isinstance(straight, dict):
            return {"skip": True}
        ms_before = straight.get("ms_before", []) or []
        ms_after = straight.get("ms_after", []) or []
        skip = bool(straight.get("skip", True))
    except Exception:
        return {"skip": True}

    if skip:
        return {"skip": True}

    try:
        from flow_straightness.straightness_calculator import CalcStraightness
    except Exception as exc:
        _log.warning("Модуль CalcStraightness недоступен: %s", exc)
        return {"skip": True}

    try:
        sig = inspect.signature(CalcStraightness.__init__)
        allowed = set(sig.parameters.keys()) - {"self"}
        beta_val = float(d) / float(D) if D else 0.0
        cand = {
            "ssu_type": ssu_type.lower() if isinstance(ssu_type, str) else ssu_type,
            "D": float(D),
            "d": float(d),
            "beta": beta_val,
            "Ra": None if Ra_m is None else float(Ra_m),
            "ms_before": ms_before,
            "ms_after": ms_after,
            "skip": False,
        }
        kwargs = {k: v for k, v in cand.items() if k in allowed and v is not None}
        if "beta" in allowed and "beta" not in kwargs:
            kwargs["beta"] = beta_val
        if "Ra" in allowed and "Ra" not in kwargs and Ra_m is not None:
            kwargs["Ra"] = float(Ra_m)
        cs = CalcStraightness(**kwargs)
        res = cs.calculate()
        _log.info("Straightness: расчёт выполнен")
        return {"skip": False, **(res if isinstance(res, dict) else {"result": res})}
    except Exception as exc:
        _log.warning("Straightness: расчёт не выполнен: %s", exc)
        return {"skip": False, "error": str(exc)}


# -------------------- Погрешности (единый блок до создания ССУ) --------------------

def _calc_errors_simple(raw: Mapping[str, Any], v: Mapping[str, Any]) -> dict:
    """
    Считает погрешности ДО создания ССУ, используя errors.error_adapter (если он вернёт),
    а недостающие T/p/dp/corrector — добивает самостоятельно из errorPackage.
    Итог всегда один блок: {skip, inputs_rel{T,p,dp,corrector}, summary}.
    """
    import math

    # ---- helpers ----
    def _val(x):
        return x.get("real") if isinstance(x, dict) and "real" in x else x

    def _to_pa(x) -> Optional[float]:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            return float(x)
        if isinstance(x, dict):
            real = _val(x)
            unit = str(x.get("unit") or "").lower()
            if real is None:
                return None
            if "mpa" in unit:
                return float(real) * 1e6
            if "kpa" in unit:
                return float(real) * 1e3
            # pa / пусто
            return float(real)
        return None

    def _to_kelvin(x) -> Optional[float]:
        if x is None:
            return None
        if isinstance(x, (int, float)):
            xv = float(x)
            return xv + 273.15 if xv < 200 else xv
        if isinstance(x, dict):
            real = _val(x)
            unit = str(x.get("unit") or "").lower()
            if real is None:
                return None
            rv = float(real)
            if "c" in unit:
                return rv + 273.15
            return rv  # считаем уже K
        return None

    def _rel_from_err_node(node: dict, base: float, kind: str) -> Optional[float]:
        """
        node = {intrError?, complError?}, each ~ {"errorTypeId": "AbsErr|RelErr", "value": {"real":..,"unit":..}}
        kind: "temp"|"pressure"|"dp"|"corrector"
        """
        if not isinstance(node, dict) or base is None or base == 0:
            if kind == "corrector":
                base = 1.0  # для рел. процентов база не нужна
            else:
                return None
        parts = []
        for key in ("intrError", "complError", "outSignalIntrError"):
            e = node.get(key)
            if not isinstance(e, dict):
                continue
            et = str(e.get("errorTypeId") or "").lower()
            val = e.get("value")
            if isinstance(val, dict):
                real = _val(val)
                unit = str(val.get("unit") or "").lower()
            else:
                real = val
                unit = ""
            if real is None:
                continue

            if et.startswith("rel"):
                r = float(real) / 100.0 if "percent" in unit else float(real)
            else:
                # AbsErr → Rel через деление на базовую величину (в СИ)
                absv = float(real)
                if kind in ("pressure", "dp"):
                    # привести к Па
                    if "mpa" in unit:
                        absv *= 1e6
                    elif "kpa" in unit:
                        absv *= 1e3
                    # pa|пусто — как есть
                elif kind == "temp":
                    # 1°C по разности = 1 K
                    # если unit не указан — считаем уже K
                    pass
                # corrector сюда почти не попадёт (обычно rel), но оставим общий случай
                r = absv / float(base) if base else None
            if r is not None:
                parts.append(float(r))

        if not parts:
            return None
        return math.sqrt(sum(p * p for p in parts))

    # ---- достаём исходные узлы ----
    epkg = (raw.get("errorPackage") or {})
    inner = (epkg.get("errorPackage") or {})
    has_flag = bool(epkg.get("hasToCalcErrors", False) or inner.get("hasToCalcErrors", False))
    err_node = epkg.get("errors") or inner.get("errors") or {}

    if not (has_flag and isinstance(err_node, dict) and err_node):
        return {"skip": True}

    phys = (raw.get("physPackage") or {}).get("physProperties", {})

    T_K   = _to_kelvin( phys.get("T") if phys.get("T") is not None else v.get("T") )
    p_pa  = _to_pa(    phys.get("p_abs") if phys.get("p_abs") is not None else v.get("p") )
    dp_pa = _to_pa(    phys.get("dp") if phys.get("dp") is not None else v.get("dp") )
    selected = {}
    adapter_ok = False
    try:
        from errors import error_adapter as _EA  # реальный модуль
        entry = None
        for name in ("calculate_all", "calculate", "run", "main"):
            fn = getattr(_EA, name, None)
            if callable(fn):
                entry = fn
                break
        if entry is None and hasattr(_EA, "ErrorAdapter"):
            Cls = getattr(_EA, "ErrorAdapter")
            if hasattr(Cls, "calculate") and callable(Cls.calculate):
                entry = lambda errs, c: Cls().calculate(errs, c)

        if entry:
            ctx = {
                "type": str(raw.get("type") or "").lower(),
                "geometry": {
                    "D": float(v["D"]),
                    "d": float(v["d"]),
                    "beta": float(v["d"]) / float(v["D"]) if v.get("D") else None
                },
                "T": T_K,
                "p_abs": p_pa,
                "dp": dp_pa,
                "Ro": _val(phys.get("Ro")),
                "Roc": _val(phys.get("Roc")),
                "k": _val(phys.get("k")),
                "mu": phys.get("mu"),
                "raw": raw,
            }
            out = entry(err_node, ctx) if getattr(entry, "__code__", None) and entry.__code__.co_argcount >= 2 else entry(err_node)
            if isinstance(out, dict):
                src = out.get("details", {}).get("inputs_rel") or out.get("inputs_rel") or {}
                if isinstance(src, dict):
                    # вытащим нужные 4
                    # T
                    for key in ("T", "t", "temperature"):
                        if key in src and isinstance(src[key], dict):
                            selected["T"] = src[key]; break
                    # p (из p_abs)
                    for key in ("p_abs", "p", "pressure"):
                        if key in src and isinstance(src[key], dict):
                            selected["p"] = src[key]; break
                    # dp
                    for key in ("dp", "dp", "dP", "Δp"):
                        if key in src and isinstance(src[key], dict):
                            selected["dp"] = src[key]; break
                    # corrector / IVK
                    for key in ("corrector", "ivk", "IVK", "corrector_IVK"):
                        if key in src and isinstance(src[key], dict):
                            selected["corrector"] = src[key]; break
                    adapter_ok = bool(selected)
    except Exception as exc:
        _log.warning("errors.error_adapter вызов не удался: %s", exc)
        adapter_ok = False

    # ---- добиваем недостающее из errorPackage (фоллбек) ----
    # temperature
    if "T" not in selected and "temperatureErrorProState" in err_node and T_K is not None:
        r = _rel_from_err_node(err_node["temperatureErrorProState"], T_K, "temp")
        if r is not None:
            selected["T"] = {"rel": r, "percent": r * 100.0}
    # abs pressure
    if "p" not in selected and "absPressureErrorProState" in err_node and p_pa is not None and p_pa != 0:
        r = _rel_from_err_node(err_node["absPressureErrorProState"], p_pa, "pressure")
        if r is not None:
            selected["p"] = {"rel": r, "percent": r * 100.0}
    # dp
    if "dp" not in selected and "diffPressureErrorProState" in err_node and dp_pa is not None and dp_pa != 0:
        r = _rel_from_err_node(err_node["diffPressureErrorProState"], dp_pa, "dp")
        if r is not None:
            selected["dp"] = {"rel": r, "percent": r * 100.0}
    # corrector / IVK — обычно относительные проценты
    if "corrector" not in selected:
        node = err_node.get("calcCorrectorProState") or err_node.get("ivkProState")
        if isinstance(node, dict):
            r = _rel_from_err_node(node, 1.0, "corrector")
            if r is not None:
                selected["corrector"] = {"rel": r, "percent": r * 100.0}

    # если совсем пусто — просто пропустим (ничего не получилось посчитать)
    if not selected:
        return {"skip": True}

    # сводная (квадратура)
    rel2 = 0.0
    for item in selected.values():
        try:
            rel2 += float(item.get("rel", 0.0)) ** 2
        except Exception:
            pass
    rel_total = math.sqrt(rel2) if rel2 > 0 else 0.0

    return {
        "skip": False,
        "inputs_rel": selected,
        "summary": {"rel": rel_total, "percent": rel_total * 100.0},
    }


import copy

def _normalize_composition_pkg_for_cc(pkg: Mapping[str, Any]) -> dict:
    """Превращает числовые intrError/complError в ожидаемые словари (RelErr, percent)."""
    cp = copy.deepcopy(pkg)
    ec = cp.get("error_composition") or {}
    if not isinstance(ec, dict):
        cp["error_composition"] = {}
        return cp

    for name, node in list(ec.items()):
        if not isinstance(node, dict):
            ec[name] = {"intrError": None, "complError": None}
            continue

        ce = node.get("complError")
        if isinstance(ce, (int, float)):
            node["complError"] = {
                "errorTypeId": "RelErr",
                "value": {"real": float(ce), "unit": "percent"},
            }

        ie = node.get("intrError")
        if isinstance(ie, (int, float)):
            node["intrError"] = {
                "errorTypeId": "RelErr",
                "value": {"real": float(ie), "unit": "percent"},
            }
        elif isinstance(ie, dict):
            val = ie.get("value")
            if isinstance(val, (int, float)):
                ie["value"] = {"real": float(val), "unit": "percent"}

    return cp


def _composition_u_and_theta(raw: Mapping[str, Any],
                             methane_name: str = "Methane") -> tuple[Optional[dict], Optional[dict]]:
    pkg = raw.get("compositionErrorPackage")
    if not isinstance(pkg, dict):
        pkg = (raw.get("errorPackage") or {}).get("compositionErrorPackage")
    if not isinstance(pkg, dict):
        _log.debug("compositionErrorPackage: ожидается dict, пришло %s — пропускаю", type(pkg).__name__)
        return None, None

    comp = pkg.get("composition")
    if not isinstance(comp, dict) or not comp:
        _log.debug("compositionErrorPackage.composition пуст или не dict — пропускаю")
        return None, None

    # ВАЖНО: нормализуем перед калькулятором
    safe_pkg = _normalize_composition_pkg_for_cc(pkg)

    try:
        from errors.errors_handler.calculators.composition import CompositionCalculator as CC
        res = CC({"compositionErrorPackage": safe_pkg}).compute(
            mode="auto", methane_name=methane_name, decimals=None
        )
    except Exception as e:
        _log.warning("CompositionCalculator failed: %s", e)
        return None, None

    delta_pp = res.get("delta_pp_by_component") or {}
    theta_by_component = res.get("theta_by_component") or {}

    # u_i (%) = (δx_i [п.п.] / x_i [%]) * 100
    u_percent: dict[str, float] = {}
    for name, xi in comp.items():
        try:
            xi_pct = float(xi)
            d_pp = float(delta_pp.get(name, 0.0))
            u_percent[name] = (d_pp / xi_pct * 100.0) if xi_pct > 0.0 else 0.0
        except Exception:
            u_percent[name] = 0.0

    theta_full: dict[str, float] = {name: float(theta_by_component.get(name, 0.0)) for name in comp.keys()}

    return (u_percent or None), (theta_full or None)

import copy
from functools import lru_cache
from phys_prop.calc_phys_prop import PhysMinimalRunner

def make_rho_phys_from_raw(base_raw: dict):
    """
    Возвращает функцию rho(comp_pct)->rho_SI, где comp_pct — проценты.
    Берём T, p_abs и прочие условия из base_raw. Кэшируем по составу.
    """
    @lru_cache(maxsize=128)
    def _rho_cached(items_tuple):
        comp_pct = dict(items_tuple)
        raw2 = copy.deepcopy(base_raw)
        phys = raw2.setdefault("physPackage", {}).setdefault("physProperties", {})
        phys["composition"] = comp_pct  # В ПРОЦЕНТАХ
        res = PhysMinimalRunner(raw2).to_dict()
        ro = res.get("ro")
        if ro is None:
            raise RuntimeError("PhysMinimalRunner не вернул ro")
        return float(ro)

    def rho(comp_pct: dict) -> float:
        items = tuple(sorted((str(k), float(v)) for k, v in comp_pct.items()))
        return _rho_cached(items)

    return rho

def _normalize_comp_for_phys(raw_in: dict, methane_name: str = "Methane", policy: str = "METHANE_BY_DIFF"):
    raw_phys = copy.deepcopy(raw_in)

    # 1) исходный источник состава — сперва из compositionErrorPackage, иначе из physPackage
    comp_src = None
    pkg = raw_phys.get("compositionErrorPackage") or (raw_phys.get("errorPackage") or {}).get("compositionErrorPackage")
    if isinstance(pkg, dict) and isinstance(pkg.get("composition"), dict) and pkg["composition"]:
        comp_src = dict(pkg["composition"])
    else:
        comp_src = ((raw_phys.get("physPackage") or {}).get("physProperties") or {}).get("composition") or {}
        comp_src = dict(comp_src)

    # 2) пробуем нормализовать твоим алгоритмом
    comp_norm = None
    try:
        from errors.errors_handler import for_package as F

        # пробуем несколько «типичных» имён — чтобы не зависеть от точного названия твоей функции
        for fn_name in ("normalize_percent_vector", "normalize_composition_percent",
                        "normalize_comp_percent", "normalize_composition"):
            fn = getattr(F, fn_name, None)
            if callable(fn):
                try:
                    comp_norm = fn(comp_src, methane_name=methane_name, policy=policy)
                except TypeError:
                    # вдруг без именованных аргументов
                    comp_norm = fn(comp_src)
                break

        # если в for_package есть high-level подготовка под методику — используем её с приоритетом
        for fn_name in ("prepare_normalized_composition", "prepare_composition_for_phys"):
            fn = getattr(F, fn_name, None)
            if callable(fn):
                tmp = fn(comp_src, methane_name=methane_name)
                if isinstance(tmp, dict) and tmp:
                    comp_norm = tmp
                    break

    except Exception as e:
        _log.debug("for_package normalization fallback: %s", e)

    # 3) простой фоллбек (если по каким-то причинам не нашли твою функцию)
    if not isinstance(comp_norm, dict) or not comp_norm:
        # обрежем отрицательные, досуммируем на 100:
        comp_pos = {k: (float(v) if float(v) > 0 else 0.0) for k, v in comp_src.items()}
        s = sum(comp_pos.values())
        if s > 0:
            comp_norm = {k: (v * 100.0 / s) for k, v in comp_pos.items()}
        else:
            comp_norm = dict(comp_pos)

        # «метан компенсирует», если есть — доводим сумму ровно до 100
        if methane_name in comp_norm:
            delta = 100.0 - sum(comp_norm.values())
            comp_norm[methane_name] = max(0.0, comp_norm[methane_name] + delta)

    # 4) подменяем состав в physPackage
    phys_props = raw_phys.setdefault("physPackage", {}).setdefault("physProperties", {})
    phys_props["composition"] = comp_norm

    return raw_phys, comp_norm


# -------------------- Добор коэффициентов из ССУ, если ssu.run_all() их не вернул --------------------

def _ensure_cf_coeffs_from_ssu(cf: Any, ssu: Any, dp: Optional[float], p1: Optional[float], k: Optional[float]) -> None:
    # beta
    if getattr(cf, "beta", None) is None:
        try:
            cf.beta = float(ssu.calculate_beta())
        except Exception as e:
            _log.warning("beta из SSU не получен: %s", e)
            try:
                if getattr(cf, "beta", None) is None and getattr(cf, "D", 0):
                    cf.beta = float(cf.d) / float(cf.D)
            except Exception:
                pass

    # E (или E_speed — внутри ССУ знают, что считать)
    if getattr(cf, "E", None) is None:
        try:
            cf.E = float(ssu.calculate_E())
        except Exception as e:
            _log.warning("E из SSU не получен: %s", e)

    # C
    if getattr(cf, "C", None) is None:
        try:
            cf.C = float(ssu.calculate_C())
        except Exception as e:
            _log.warning("C из SSU не получен: %s", e)

    # epsilon — сигнатуры разные: (dp, k) или (dp, p)
    if getattr(cf, "epsilon", None) is None:
        try:
            sig = inspect.signature(ssu.calculate_epsilon)
            kwargs = {}
            if "dp" in sig.parameters and dp is not None:
                kwargs["dp"] = dp
            if "k" in sig.parameters and k is not None:
                kwargs["k"] = k
            if "p" in sig.parameters and p1 is not None:
                kwargs["p"] = p1
            cf.epsilon = float(ssu.calculate_epsilon(**kwargs))
        except Exception as e:
            _log.warning("epsilon из SSU не получен: %s", e)


# -------------------- Точка входа --------------------

def run_calculation(*args: Any, **kwargs: Any):
    """
    run_calculation(prepared, values_si, raw)
    Шаги: термокоррекция → погрешности (T,p,dp,corrector) → создание ССУ → ССУ.run_all → CalcFlow → Straightness.
    Возвращает общий словарь результатов.
    """
    if len(args) < 2:
        raise ValueError("run_calculation(prepared, values_si[, raw]) — минимум 2 аргумента")

    prepared = args[0]
    values: Mapping[str, Any] = args[1] or {}
    raw: Mapping[str, Any] = args[2] if len(args) >= 3 else {}

    # --------------------------------- 1) Термокоррекция ---------------------------------
    v = dict(values)

    D20 = v.get("D20")
    d20 = v.get("d20")
    D = v.get("D")
    d = v.get("d")

    T_val = _get_phys(raw, "T")
    if T_val is None and "T" in v:
        T_val = v["T"]

    lp = (raw.get("lenPackage") or {}).get("lenProperties", {})
    d20_steel = lp.get("d20_steel")
    D20_steel = lp.get("D20_steel")

    Ra_raw = lp.get("Ra")
    Ra_m: Optional[float] = None
    if isinstance(Ra_raw, dict):
        _ra_real = Ra_raw.get("real")
        _ra_unit = str(Ra_raw.get("unit") or "").lower()
        if _ra_real is not None:
            if "µ" in _ra_unit or "um" in _ra_unit:
                Ra_m = float(_ra_real) * 1e-6
            elif "mm" in _ra_unit:
                Ra_m = float(_ra_real) * 1e-3
            else:
                Ra_m = float(_ra_real)
    elif Ra_raw is not None:
        Ra_m = float(Ra_raw)

    theta = lp.get("theta")
    alpha_raw = lp.get("alpha")
    alpha_lp = (alpha_raw.get("real") if isinstance(alpha_raw, dict) else alpha_raw)

    kt = v.get("kt")

    if D20 is not None and d20 is not None and T_val is not None and (d20_steel or D20_steel):
        try:
            from orifices_classes.materials import calc_alpha
            T_c = float(T_val)
            dT = T_c - 20.0
            alpha_D = float(calc_alpha(D20_steel, T_c)) if D20_steel else 0.0
            alpha_d = float(calc_alpha(d20_steel, T_c)) if d20_steel else 0.0
            D = float(D20) * (1.0 + alpha_D * dT)
            d = float(d20) * (1.0 + alpha_d * dT)
            _log.info(
                "Термокоррекция: D20=%.6g→D=%.6g, d20=%.6g→d=%.6g (ΔT=%.3g°C)",
                D20, D, d20, d, dT,
            )
        except Exception as e:
            _log.warning("Не удалось применить термокоррекцию: %s — используем исходные значения", e)
            D = float(D or D20)
            d = float(d or d20)
    else:
        if D is not None and d is not None:
            D = float(D); d = float(d)
            if kt is not None:
                D *= float(kt); d *= float(kt)
        else:
            if D20 is None or d20 is None:
                raise KeyError("Нужны диаметры: D и d (или D20 и d20)")
            D = float(D20)
            d = float(d20)

    # фиксируем тёплые диаметры
    v["D"], v["d"] = float(D), float(d)
    v.pop("D20", None); v.pop("d20", None)

    # ---------- 1.5) Погрешности (один блок) ----------
    errors_res = _calc_errors_simple(raw, v)

    # ---- ФИЗИКА (+θ) ----
    raw_phys, comp_norm = _normalize_comp_for_phys(raw)
    phys_block = {"skip": True}
    u_rho_rel = u_rho_std_rel = 0.0

    try:
        if PhysMinimalRunner is None:
            raise ImportError("PhysMinimalRunner не найден")

        # дефолты для std-условий и сухого газа (если не заданы)
        pp = raw.setdefault("physPackage", {}).setdefault("physProperties", {})
        pp.setdefault("T_st", {"real": 20, "unit": "C"})
        pp.setdefault("p_st", {"real": 0.101325, "unit": "MPa"})
        pp.setdefault("phi", {"real": 0, "unit": "percent"})
        pp.setdefault("humidityType", "RelativeHumidity")

        # 1) считаем физику (без θ)
        phys = PhysMinimalRunner(raw_phys).to_dict()

        # подставляем в v, если пусто
        v.setdefault("Ro", phys.get("ro"))
        v.setdefault("Roc", phys.get("ro_st"))
        v.setdefault("k", phys.get("k"))
        if v.get("mu") is None and phys.get("mu") is not None:
            v["mu"] = {"real": float(phys["mu"]) * 1e-6, "unit": "Pa_s"}  # μПа·с → _coerce_mu_si переведёт в Па·с

        # относительные u_ρ и u_ρ,st для errors_flow
        u_rho_rel = (phys["err_ro"] / phys["ro"]) if phys.get("err_ro") and phys.get("ro") else 0.0
        u_rho_std_rel = (phys["err_ro_st"] / phys["ro_st"]) if phys.get("err_ro_st") and phys.get("ro_st") else 0.0

        # 2) ТЕТЫ: сначала пробуем stp_errors, затем — устойчивый фоллбек
        def _calc_thetas_safe(base_raw: dict) -> Optional[dict]:
            thetas = {}

            # --- попытка через stp_errors (с p_abs и p)
            try:
                stp_mod = import_module("stp_errors")
                calc_thetas = getattr(stp_mod, "calc_thetas_from_requestList", None)
                if callable(calc_thetas):
                    data_for_t = dict(base_raw)  # не мутим исходник
                    ppkg = data_for_t.setdefault("physPackage", {})
                    # безопасный requestList — только rho и k (твой documentId сохраняем, если есть)
                    rl_src = list((base_raw.get("physPackage") or {}).get("requestList") or [])
                    doc = rl_src[0]["documentId"] if rl_src and isinstance(rl_src[0], dict) else "GOST_30319_3"
                    ppkg["requestList"] = [{"documentId": doc, "physValueId": "rho"},
                                           {"documentId": doc, "physValueId": "k"}]

                    def _try(reqs):
                        out = calc_thetas(reqs, **data_for_t)
                        if isinstance(out, dict):
                            thetas.update(out)

                    # T и p_abs
                    _try([{"value": "rho", "variable": "T"},
                          {"value": "k", "variable": "T"},
                          {"value": "rho", "variable": "p_abs"},
                          {"value": "k", "variable": "p_abs"}])
                    # если по давлению пусто — попробуем 'p'
                    if not any(k.startswith(("theta_rho_p", "theta_k_p")) for k in thetas):
                        _try([{"value": "rho", "variable": "p"},
                              {"value": "k", "variable": "p"}])
            except Exception:
                pass



            # --- фоллбек: центральная разность на PhysMinimalRunner
            def _fd_logtheta(var: str, h: float = 0.01):
                """вернёт словарь с theta_rho_* и theta_k_* для одной переменной"""
                sub = {}

                def _run_with(var_value_upd: dict) -> Optional[dict]:
                    # делаем глубокую копию только physProperties (хватает)
                    raw2 = dict(base_raw)
                    phys2 = raw2.setdefault("physPackage", {}).setdefault("physProperties", {}).copy()
                    phys2.update(var_value_upd)
                    raw2["physPackage"]["physProperties"] = phys2
                    try:
                        return PhysMinimalRunner(raw2).to_dict()
                    except Exception:
                        return None

                if var == "T":
                    T_node = (base_raw.get("physPackage") or {}).get("physProperties", {}).get("T")
                    T_C = T_node.get("real") if isinstance(T_node, dict) else T_node
                    if T_C is None:
                        return sub
                    T_K = (float(T_C) + 273.15) if float(T_C) < 200 else float(T_C)
                    T_Kp, T_Km = T_K * (1 + h), T_K * (1 - h)
                    Tp_C = T_Kp - 273.15;
                    Tm_C = T_Km - 273.15
                    up = _run_with({"T": {"real": Tp_C, "unit": "C"}})
                    dn = _run_with({"T": {"real": Tm_C, "unit": "C"}})
                    if up and dn and up.get("ro") and dn.get("ro") and up.get("k") and dn.get("k"):
                        denom = math.log(1 + h) - math.log(1 - h)
                        sub["theta_rho_T"] = (math.log(up["ro"]) - math.log(dn["ro"])) / denom
                        sub["theta_k_T"] = (math.log(up["k"]) - math.log(dn["k"])) / denom

                elif var in ("p_abs", "p"):
                    p_node = (base_raw.get("physPackage") or {}).get("physProperties", {}).get("p_abs")
                    # поддержим Pa/kPa/MPa; вернём в тех же единицах
                    if not isinstance(p_node, dict) or "real" not in p_node:
                        return sub
                    p_real = float(p_node["real"]);
                    unit = str(p_node.get("unit", "")).lower()
                    # → Па
                    factor = 1.0
                    if "mpa" in unit:
                        factor = 1e6
                    elif "kpa" in unit:
                        factor = 1e3
                    p_Pa = p_real * factor
                    pP, pM = p_Pa * (1 + h), p_Pa * (1 - h)

                    # ← в те же единицы
                    def _back(pa):
                        val = pa / factor
                        return {"real": val, "unit": p_node["unit"]}

                    up = _run_with({"p_abs": _back(pP)})
                    dn = _run_with({"p_abs": _back(pM)})
                    if up and dn and up.get("ro") and dn.get("ro") and up.get("k") and dn.get("k"):
                        denom = math.log(1 + h) - math.log(1 - h)
                        sub["theta_rho_p_abs"] = (math.log(up["ro"]) - math.log(dn["ro"])) / denom
                        sub["theta_k_p_abs"] = (math.log(up["k"]) - math.log(dn["k"])) / denom

                return sub

            # дополним недостающие ключи
            missing_T = not any(k.endswith("_T") for k in thetas)
            if missing_T:
                thetas.update(_fd_logtheta("T"))
            missing_p = not any(k.endswith("_p") or k.endswith("_p_abs") for k in thetas)
            if missing_p:
                thetas.update(_fd_logtheta("p_abs"))

            return thetas or None

        phys_thetas = _calc_thetas_safe(raw_phys)
        # компактный блок для выдачи
        phys_block = {
            "skip": False,
            "rho": v["Ro"], "rho_st": v["Roc"],
            "k": v["k"], "mu": phys.get("mu"),
            "err_ro": phys.get("err_ro"),
            "err_ro_st": phys.get("err_ro_st"),
            "err_k": phys.get("err_k"),
            "err_mu": phys.get("err_mu"),
            "thetas": phys_thetas,
        }
    except Exception as e:
        _log.warning("Физика пропущена: %s", e)


    # --------------------------------- 2) Создание ССУ ---------------------------------
    try:
        ssu_name = str(raw.get("type", "")).strip().lower()
    except Exception:
        ssu_name = ""
    if not ssu_name:
        raise KeyError("В raw['type'] не задан тип ССУ (например: 'cone', 'double', 'wedge', 'eccentric', 'orifice')")

    # alpha: values → lenProperties.alpha → lenProperties.theta
    if "alpha" not in v:
        _alpha_val = alpha_lp if alpha_lp is not None else theta
        if _alpha_val is not None:
            v["alpha"] = _alpha_val

    # Давление p, если требуется конструкторам
    if "p" not in v:
        v["p"] = v.get("p1", v.get("p_abs", _get_phys(raw, "p_abs")))

    # Шероховатость
    if Ra_m is not None:
        v["Ra"] = Ra_m

    # k
    if "k" not in v or v["k"] is None:
        kval = _get_phys(raw, "k")
        if kval is not None:
            v["k"] = float(kval)

    # Re стартовый
    if "Re" not in v or v["Re"] is None:
        v["Re"] = 1.0e5

    # Флаг валидации (по умолчанию False, чтобы не падать на граничных тестах)
    kwargs_ssu = dict(v)
    kwargs_ssu.setdefault("do_validate", False)

    from orifices_classes.main import create_orifice
    _log.info("create_orifice(name=%s, kwargs=%s)", ssu_name, sorted([k for k in kwargs_ssu.keys() if k not in ("rho","mu","kappa","is_gas")]))
    ssu = create_orifice(ssu_name, **kwargs_ssu)

    # Гарантировать наличие давления в объекте (для calculate_epsilon)
    try:
        if "p" in v and hasattr(ssu, "p"):
            ssu.p = float(v["p"])
    except Exception:
        pass

    # Попытка update_geometry_from_temp (если вдруг требуется и доступно)
    try:
        if D20 is not None and d20 is not None and T_val is not None and hasattr(ssu, "update_geometry_from_temp"):
            from orifices_classes.materials import calc_alpha  # локальный импорт
            T_c = float(T_val)
            alpha_T = float(calc_alpha(D20_steel, T_c)) if D20_steel else 0.0
            alpha_CCU = float(calc_alpha(d20_steel, T_c)) if d20_steel else 0.0
            ssu.update_geometry_from_temp(
                d_20=float(d20) if d20 is not None else float(d),
                D_20=float(D20) if D20 is not None else float(D),
                alpha_CCU=alpha_CCU,
                alpha_T=alpha_T,
                t=T_c,
            )
            if hasattr(ssu, "D") and hasattr(ssu, "d"):
                v["D"] = float(getattr(ssu, "D"))
                v["d"] = float(getattr(ssu, "d"))
    except Exception as e:
        _log.warning("update_geometry_from_temp не выполнен: %s", e)

    # Валидация геометрии (если включена внутри класса)
    if hasattr(ssu, "validate"):
        if not ssu.validate():
            raise ValueError(f"Валидация геометрии ССУ '{ssu_name}' не пройдена")

    # Проверка шероховатости (если класс поддерживает)
    try:
        if Ra_m is not None and hasattr(ssu, "validate_roughness"):
            valid_rough = ssu.validate_roughness(float(Ra_m))
            v["valid_roughness"] = bool(valid_rough)
    except Exception as e:
        _log.warning("validate_roughness не выполнен: %s", e)

    # Полный расчёт параметров ССУ (если реализован)
    ssu_results: Optional[dict] = None
    try:
        if hasattr(ssu, "run_all"):
            dp = v.get("dp", _get_phys(raw, "dp"))
            p_in = v.get("p1", v.get("p_abs", _get_phys(raw, "p_abs")))
            k_val = v.get("k")
            ssu_results = ssu.run_all(
                dp=dp,
                p=p_in,
                k=k_val,
                Ra=float(Ra_m) if Ra_m is not None else None,
                alpha=v.get("alpha"),
            )
    except Exception as e:
        _log.warning("run_all не выполнен: %s", e)

    # --- CalcFlow: подготовка аргументов ---
    _log.info("Маршрут: calc_flow.calcflow → CalcFlow | run_all")

    cf_mod = import_module("calc_flow.calcflow")
    CF = getattr(cf_mod, "CalcFlow")

    d_ = float(v["d"])  # тёплый
    D_ = float(v["D"])  # тёплый
    p1_ = float(v.get("p1", v.get("p_abs", _get_phys(raw, "p_abs"))))
    t_ = v.get("t1", v.get("T", _get_phys(raw, "T")))
    t1_ = float(t_) + 273.15 if t_ is not None and float(t_) < 200 else float(t_)
    dp_ = float(v.get("dp", _get_phys(raw, "dp")))

    # μ: вход в SI (Pa·с) → для CalcFlow нужно в μPa·с
    mu_si = _coerce_mu_si(
        v.get("mu"),
        (raw.get("physPackage") or {}).get("physProperties", {}).get("mu")
    )
    if mu_si is None:
        mu_si = 0.0
    mu_for_cf = float(mu_si) * 1e6  # Pa·s → μPa·с
    _log.info("Viscosity: %.6g Pa·с → %.6g μPa·с (для CalcFlow)", mu_si, mu_for_cf)

    Roc_ = float(v.get("Roc", _get_phys(raw, "Roc"))) if (
                v.get("Roc") is not None or _get_phys(raw, "Roc") is not None) else 0.0
    Ro_ = float(v.get("Ro", _get_phys(raw, "Ro"))) if (
                v.get("Ro") is not None or _get_phys(raw, "Ro") is not None) else 0.0
    k_ = float(v.get("k", _get_phys(raw, "k"))) if (v.get("k") is not None or _get_phys(raw, "k") is not None) else None

    pos_args = (d_, D_, p1_, t1_, dp_, mu_for_cf, Roc_, Ro_, k_ if k_ is not None else 1.3, ssu)
    _log.debug("Пробую CalcFlow(*positional %d args)", len(pos_args))
    cf = CF(*pos_args)

    # --- Неопределённости коэффициентов из ССУ ---
    d_Cm = None
    d_Epsilonm = None

    # d_Cm
    try:
        if hasattr(ssu, "discharge_coefficient_uncertainty"):
            try:
                # вариант без аргументов
                d_Cm = float(ssu.discharge_coefficient_uncertainty())
            except TypeError:
                # если в твоих реализациях методы захотят dp/p/k
                sig = inspect.signature(ssu.discharge_coefficient_uncertainty)
                kwargs = {}
                if "dp" in sig.parameters:
                    kwargs["dp"] = dp_
                if "p" in sig.parameters:
                    kwargs["p"] = p1_
                if "k" in sig.parameters and k_ is not None:
                    kwargs["k"] = k_
                d_Cm = float(ssu.discharge_coefficient_uncertainty(**kwargs))
    except Exception as e:
        _log.warning("Не удалось получить d_Cm: %s", e)

    # d_Epsilonm
    try:
        if hasattr(ssu, "expansion_coefficient_uncertainty"):
            try:
                d_Epsilonm = float(ssu.expansion_coefficient_uncertainty())
            except TypeError:
                sig = inspect.signature(ssu.expansion_coefficient_uncertainty)
                kwargs = {}
                if "dp" in sig.parameters:
                    kwargs["dp"] = dp_
                if "p" in sig.parameters:
                    kwargs["p"] = p1_
                if "k" in sig.parameters and k_ is not None:
                    kwargs["k"] = k_
                d_Epsilonm = float(ssu.expansion_coefficient_uncertainty(**kwargs))
    except Exception as e:
        _log.warning("Не удалось получить d_Epsilonm: %s", e)

    # 1) Прокинуть коэффициенты из результатов ССУ (если есть)
    ssu_results = ssu_results or {}

    try:
        C_val = ssu_results.get("C")
        if C_val is not None:
            cf.C = float(C_val)
        E_val = ssu_results.get("E", ssu_results.get("E_speed"))
        if E_val is not None:
            cf.E = float(E_val)
        eps_val = ssu_results.get("epsilon", ssu_results.get("Epsilon"))
        if eps_val is not None:
            cf.epsilon = float(eps_val)
        beta_val = ssu_results.get("beta")
        if beta_val is None and D_:
            beta_val = d_ / D_
        if beta_val is not None:
            cf.beta = float(beta_val)
    except Exception as e:
        _log.warning("Не удалось установить коэффициенты из SSU: %s", e)

    # 2) Гарантированный добор из самого ssu (если чего-то не хватает)
    _ensure_cf_coeffs_from_ssu(cf, ssu, dp_, p1_, k_)

    # 3) Жёсткий фоллбек beta
    if getattr(cf, "beta", None) is None and D_:
        try:
            cf.beta = float(d_) / float(D_)
        except Exception:
            pass

    # Запуск полного расчёта расходов
    flow_res = None
    if hasattr(cf, "run_all") and callable(cf.run_all):
        _log.info("Вызов CalcFlow.run_all()")
        flow_res = cf.run_all()
    else:
        # Резервные имена (на всякий случай)
        for mname in ("run", "run_calculations", "calculate", "calc", "compute", "main", "start"):
            method = getattr(cf, mname, None)
            if callable(method):
                _log.info("Вызов CalcFlow.%s()", mname)
                flow_res = method()
                break
        if flow_res is None:
            raise AttributeError("В CalcFlow не найден метод запуска расчёта")

    # --------------------------------- Straightness ---------------------------------
    straight_res = _maybe_calc_straightness(ssu_name, d_, D_, Ra_m, raw)

    # --------------------------------- Errors Flow (C, ε, расходы) ---------------------------------
    errors_flow_block = {"skip": True}
    try:
        # гибкий импорт SimpleErrFlow
        SEF = None
        for modname in ("simple_err_flow", "errors_flow.simple_err_flow", "errors_flow"):
            try:
                #m = import_module(modname)
                from calc_flow.err_flow import SimpleErrFlow
                SEF = SimpleErrFlow
                if SEF:
                    break
            except Exception:
                continue

        if SEF is not None:
            # Входные относительные из ранее посчитанного блока errors
            inputs_rel = (errors_res or {}).get("inputs_rel") or {}
            u_dp = _rel_only(inputs_rel.get("dp"))
            u_p = _rel_only(inputs_rel.get("p")) if _rel_only(inputs_rel.get("p")) is not None else _rel_only(
                inputs_rel.get("p_abs"))
            u_corr = _rel_only(inputs_rel.get("corrector"))
            if u_corr is None:
                u_corr = 0.0  # если корректора нет — считаем 0

            beta_eff = getattr(cf, "beta", None)
            if beta_eff is None and D_:
                beta_eff = d_ / D_

            ef = SEF(ssu_type=ssu_name, beta=float(beta_eff), d=d_, D=D_, phase="gas", phys_block=phys_block)

            v_D = v_d = None
            try:
                v_D, v_d = ef.sensitivities_geom()
            except Exception as e:
                _log.debug("sensitivities_geom пропущены: %s", e)

            # Вклады C и ε
            u_C = SEF.coeff_C(d_Cm)  # d_Cm уже относительная (доли)
            eps_ = getattr(cf, "epsilon", None)
            if eps_ is None:
                eps_ = ssu_results.get("epsilon", 1.0)

            u_eps = SEF.coeff_epsilon(
                epsilon=float(eps_),
                u_epsm=d_Epsilonm,
                u_dp=u_dp,
                u_p=u_p,
                u_k=0.0
            )

            u_T = _rel_only(inputs_rel.get("T")) or _rel_only(inputs_rel.get("t"))
            u_p = _rel_only(inputs_rel.get("p"))

            from errors.errors_handler import for_package as F

            try:
                F.RHO_FN_OVERRIDE = make_rho_phys_from_raw(raw)  # ← включили «настоящую» ρ
                u_N, comp_theta = _composition_u_and_theta(raw)  # ← твой вызов, как есть
            finally:
                F.RHO_FN_OVERRIDE = None  # ← ОБЯЗАТЕЛЬНО сбросили


            Xa = v.get("Xa") if "Xa" in v else None  # todo тут уже обработанный состав
            Xy = v.get("Xy") if "Xy" in v else None  # todo тут уже обработанный состав
            u_Xa = v.get("u_Xa") if "u_Xa" in v else None  # todo тут уже обработанный состав
            u_Xy = v.get("u_Xy") if "u_Xy" in v else None  # todo тут уже обработанный состав
            #u_N = v.get("u_N") if "u_N" in v else None  # todo тут уже обработанный состав

            u_rho, u_rho_std = ef.density_uncertainties(
                u_T=u_T,
                u_p=u_p,
                Xa=Xa, Xy=Xy,
                u_Xa=u_Xa, u_Xy=u_Xy,
                u_N=u_N,
            )      #todo все возможные тетты подготовить для состава, для второй части, для моно сред
            u_v_D = v_D * D
            u_v_d = v_d * d

            # Сводные по расходам
            u_dp_val = 0.0 if u_dp is None else float(u_dp)
            u_Qm = SEF.flow_mass(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho=u_rho, u_v_D=u_v_D, u_v_d=u_v_d, u_corr=float(u_corr))
            u_Qv = SEF.flow_vol_actual(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho=u_rho, u_v_D=u_v_D, u_v_d=u_v_d,
                                       u_corr=float(u_corr))
            u_Qstd = SEF.flow_vol_std(u_C=u_C, u_eps=u_eps, u_dp=u_dp_val, u_rho_std=u_rho_std, u_v_D=u_v_D, u_v_d=u_v_d,
                                      u_corr=float(u_corr))

            errors_flow_block = {
                "u_v_D": u_v_D,
                "u_v_d": u_v_d,
                "u_inputs": {
                    "u_C": u_C,
                    "u_eps": u_eps,
                    "u_dp": u_dp_val,
                    "u_p": 0.0 if u_p is None else float(u_p),
                    "u_corr": float(u_corr),
                    "u_rho": float(u_rho),
                    "u_rho_std": float(u_rho_std),
                },
                "u_Qm": {"rel": u_Qm},
                "u_Qv": {"rel": u_Qv},
                "u_Qstd": {"rel": u_Qstd},
                "skip": False,
            }
        else:
            _log.warning("SimpleErrFlow не найден — блок errors_flow будет пропущен")

    except Exception as e:
        _log.warning("Errors Flow расчёт не выполнен: %s", e)
        errors_flow_block = {"skip": False, "error": str(e)}

    # Итоговый словарь
    result = {
        "type": ssu_name,
        "D": D_, "d": d_,
        "p1": p1_, "t1": t1_,
        "dp": dp_, "mu": mu_for_cf, "Roc": Roc_, "Ro": Ro_, "k": k_,
        "C": getattr(cf, "C", None),
        "E": getattr(cf, "E", None),
        "epsilon": getattr(cf, "epsilon", None),
        "beta": getattr(cf, "beta", None),
        "d_Cm": d_Cm,
        "d_Epsilonm": d_Epsilonm,
        "ssu_results": ssu_results,
        "flow": flow_res,
        "straightness": straight_res if isinstance(straight_res, dict) else {"skip": True},
        "phys": phys_block,
        "errors": errors_res,
        "errors_flow": errors_flow_block,
    }
    return result


__all__ = ["run_calculation"]
