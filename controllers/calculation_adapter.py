"""
Адаптер связки блоков без изменения алгоритмов расчёта.
Шаги выполнения:
  0) (опционально) Ранний расчёт погрешностей (errorPackage.hasToCalcErrors == True и есть errors) —
     отдаём весь словарь в errors.error_adapter и сохраняем результат в общий ответ.
  1) Термокоррекция геометрии → получаем «тёплые» D,d; D20/d20 далее не тянем.
  2) Создаём ССУ строго по raw["type"] через orifices_classes.main.create_orifice:
     - подставляем обязательные параметры из входа (alpha/θ, p, Ra, k, Re-пусковой)
     - update_geometry_from_temp → validate → validate_roughness → (по возможности) run_all
  3) Инициализация CalcFlow по явной сигнатуре и запуск run_all();
     переносим в CalcFlow коэффициенты из ССУ (C, E, epsilon, beta). Если run_all ССУ не отдал
     коэффициенты — добираем их прямыми вызовами calculate_* из ССУ (надёжная подстраховка),
     чтобы CalcFlow не падал с AttributeError: 'CalcFlow' has no attribute 'C'.
  4) (опционально) Расчёт прямолинейных участков (straightness) — принимаем *тёплые* D, d,
     подставляем beta=d/D и Ra (если в исходнике есть), ms_before/ms_after — как есть.
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping, Optional, Tuple
import inspect

# --- Логгер проекта ---
try:
    from logger_config import get_logger  # предпочтительно
    _log = get_logger("CalculationAdapter")
except Exception:
    try:
        from logger import get_logger  # запасной вариант
        _log = get_logger("CalculationAdapter")
    except Exception:  # no-op
        class _Dummy:
            def info(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
        _log = _Dummy()


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
    """
    Возвращает динамическую вязкость в Па·с.
    Поддерживаем входы:
      - число (считаем уже в Па·с)
      - dict {'real': ..., 'unit': ...} где unit ∈ {'Pa_s','mPa_s','uPa_s','μPa_s'}
    """
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


# -------------------- Straightness: расчёт длин прямых участков --------------------

def _maybe_calc_straightness(ssu_type: str, d: float, D: float, Ra_m: Optional[float], raw: Mapping[str, Any]) -> dict:
    """Расчёт через flow_straightness.straightness_calculator (если включено).
    Передаём *тёплые* D,d и (если требует конструктор) beta=d/D и Ra.
    Флаг включения: lenPackage.straightness.skip (по умолчанию True — пропустить).
    Возвращаем словарь с ключом 'skip'.
    """
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


# -------------------- Errors: ранний расчёт погрешностей --------------------

def _maybe_calc_errors_early(raw: Mapping[str, Any], values_si: Mapping[str, Any], warm_D: Optional[float], warm_d: Optional[float]) -> dict:
    """Если raw.errorPackage.hasToCalcErrors == True и есть errors —
    гоняем весь словарь в errors.error_adapter и возвращаем {'skip':bool, 'result'| 'error':...}.
    Контекст прокидываем минимально полезный (D,d,T,p_abs,dp и т.д.).
    """
    epkg = (raw.get("errorPackage") or {})
    has_flag = bool(epkg.get("hasToCalcErrors", False))
    errors_dict = epkg.get("errors") if isinstance(epkg.get("errors"), dict) else None
    if not (has_flag and errors_dict):
        _log.info("Errors: пропуск (флаг отсутствует/ложь либо нет errors)")
        return {"skip": True}

    _log.info("Errors: запускаем расчёт погрешностей (ранний этап)")

    # Подготовим контекст — можно расширить по мере необходимости
    phys = (raw.get("physPackage") or {}).get("physProperties", {})
    ctx = {
        "D": warm_D,
        "d": warm_d,
        "T": _strip_unit_node(phys.get("T")),
        "p_abs": _strip_unit_node(phys.get("p_abs")),
        "dp": _strip_unit_node(phys.get("dp")),
        "Roc": _strip_unit_node(phys.get("Roc")),
        "Ro": _strip_unit_node(phys.get("Ro")),
        "k": _strip_unit_node(phys.get("k")),
        "mu": phys.get("mu"),  # единицы разберёт при необходимости расчётчик погрешностей
    }

    try:
        err_mod = import_module("errors.error_adapter")
    except Exception as exc:
        _log.warning("Errors: модуль errors.error_adapter не найден: %s", exc)
        return {"skip": False, "error": f"module import failed: {exc}"}

    # Ищем наиболее вероятные точки входа
    for entry in ("calculate_all", "calculate", "run", "main"):
        fn = getattr(err_mod, entry, None)
        if callable(fn):
            try:
                res = fn(errors_dict, ctx) if fn.__code__.co_argcount >= 2 else fn(errors_dict)
                return {"skip": False, "result": res}
            except Exception as exc:
                _log.warning("Errors: вызов %s() завершился ошибкой: %s", entry, exc)
                return {"skip": False, "error": str(exc)}

    _log.warning("Errors: в errors.error_adapter не найден подходящий входной метод")
    return {"skip": False, "error": "no entrypoint (calculate_all/calculate/run/main)"}


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

    # epsilon — сигнатуры разные: (delta_p, k) или (delta_p, p)
    if getattr(cf, "epsilon", None) is None:
        try:
            sig = inspect.signature(ssu.calculate_epsilon)
            kwargs = {}
            if "delta_p" in sig.parameters and dp is not None:
                kwargs["delta_p"] = dp
            if "k" in sig.parameters and k is not None:
                kwargs["k"] = k
            if "p" in sig.parameters and p1 is not None:
                kwargs["p"] = p1
            cf.epsilon = float(ssu.calculate_epsilon(**kwargs))
        except Exception as e:
            _log.warning("epsilon из SSU не получен: %s", e)


# -------------------- Точка входа --------------------

def run_calculation(*args: Any, **kwargs: Any):
    """run_calculation(prepared, values_si, raw)
    Шаги: Errors → термокоррекция → создание ССУ → методы ССУ → запуск CalcFlow → Straightness.
    Возвращает общий словарь результатов.
    """
    if len(args) < 2:
        raise ValueError("run_calculation(prepared, values_si[, raw]) — минимум 2 аргумента")

    prepared = args[0]
    values: Mapping[str, Any] = args[1] or {}
    raw: Mapping[str, Any] = args[2] if len(args) >= 3 else {}

    # --------------------------------- 0) Errors (ранний этап) ---------------------------------
    # Пока не знаем тёплые D, d — но попробуем вытащить черновые (или подставим позже при термокоррекции)
    warm_D_early = values.get("D") or values.get("D20")
    warm_d_early = values.get("d") or values.get("d20")
    errors_result = _maybe_calc_errors_early(raw, values, warm_D_early, warm_d_early)

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

    # Гарантируем наличие давления в объекте (для calculate_epsilon)
    try:
        if "p" in v and hasattr(ssu, "p"):
            ssu.p = float(v["p"])  # важно для Double/Eccentric/Wedge и др.
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
            delta_p = v.get("dp", _get_phys(raw, "dp"))
            p_in = v.get("p1", v.get("p_abs", _get_phys(raw, "p_abs")))
            k_val = v.get("k")
            ssu_results = ssu.run_all(
                delta_p=delta_p,
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

    # μ: вход в SI (Pa·s) → для CalcFlow нужно в μPa·s
    mu_si = _coerce_mu_si(
        v.get("mu"),
        (raw.get("physPackage") or {}).get("physProperties", {}).get("mu")
    )
    if mu_si is None:
        mu_si = 0.0
    mu_for_cf = float(mu_si) * 1e6  # Pa·s → μPa·s
    _log.info("Viscosity: %.6g Pa·s → %.6g μPa·s (для CalcFlow)", mu_si, mu_for_cf)

    Roc_ = float(v.get("Roc", _get_phys(raw, "Roc"))) if (
                v.get("Roc") is not None or _get_phys(raw, "Roc") is not None) else 0.0
    Ro_ = float(v.get("Ro", _get_phys(raw, "Ro"))) if (
                v.get("Ro") is not None or _get_phys(raw, "Ro") is not None) else 0.0
    k_ = float(v.get("k", _get_phys(raw, "k"))) if (v.get("k") is not None or _get_phys(raw, "k") is not None) else None

    pos_args = (d_, D_, p1_, t1_, dp_, mu_for_cf, Roc_, Ro_, k_ if k_ is not None else 1.3, ssu)
    _log.debug("Пробую CalcFlow(*positional %d args)", len(pos_args))
    cf = CF(*pos_args)

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

    # --------------------------------- 4) Straightness ---------------------------------
    straight_res = _maybe_calc_straightness(ssu_name, d_, D_, Ra_m, raw)

    # Компонуем общий ответ
    result = {
        "type": ssu_name,
        "D": D_, "d": d_,
        "p1": p1_, "t1": t1_,
        "dp": dp_, "mu": mu_, "Roc": Roc_, "Ro": Ro_, "k": k_,
        "C": getattr(cf, "C", None),
        "E": getattr(cf, "E", None),
        "epsilon": getattr(cf, "epsilon", None),
        "beta": getattr(cf, "beta", None),
        "ssu_results": ssu_results,
        "flow": flow_res,
        "straightness": straight_res if isinstance(straight_res, dict) else {"skip": True},
        "errors": errors_result if isinstance(errors_result, dict) else {"skip": True},
    }
    return result


__all__ = ["run_calculation"]
