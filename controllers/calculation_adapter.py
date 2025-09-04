# path: controllers/calculation_adapter.py
"""
Адаптер связки блоков без изменения алгоритмов расчёта.
Шаги:
  1) Термокоррекция геометрии → получаем «тёплые» D,d; D20/d20 далее не тянем.
  2) Создаём ССУ строго по raw["type"] через orifices_classes.main.create_orifice:
     - подставляем обязательные параметры из входа (alpha/θ, p, Ra, k, Re-пусковой)
     - update_geometry_from_temp → validate → validate_roughness → run_all
  3) Инициализация CalcFlow по явной сигнатуре и запуск run_all();
     переносим в CalcFlow коэффициенты из ССУ (C, E/E_speed, epsilon/Epsilon, beta).
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping, Optional, Tuple

# --- Logger (корневой, по проекту) ---
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


# -------------------- Вспомогательное: расчёт прямолинейных участков --------------------

def _maybe_calc_straightness(ssu_type: str, d: float, D: float, Ra_m: Optional[float], raw: Mapping[str, Any]) -> Optional[dict]:
    """Расчёт длин прямолинейных участков через flow_straightness.straightness_calculator.
    ВАЖНО: передаём *тёплые* диаметры `D` и `d` (после термокоррекции), а не D20/d20. Если конструктор
    требует `beta`/`Ra` — подставляем `beta=d/D` и `Ra=Ra_m` (если задано во входных данных).
    Флаг: lenPackage.straightness.skip (по умолчанию True — явное включение расчёта).
    Возвращаем словарь с ключом 'skip' всегда; при skip=False добавляем расчёт.
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
        import inspect
    except Exception as exc:
        _log.warning("Модуль CalcStraightness недоступен: %s", exc)
        return {"skip": True}

    try:
        # Инспекция сигнатуры конструктора и передача только поддерживаемых аргументов
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
        # Если конструктор требует beta/Ra, гарантируем подстановку при их наличии в allowed
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
        ms_before = straight.get("ms_before", []) or []
        ms_after = straight.get("ms_after", []) or []
    except Exception:
        return None

    try:
        from flow_straightness.straightness_calculator import CalcStraightness
    except Exception as exc:
        _log.warning("Модуль CalcStraightness недоступен: %s", exc)
        return None

    try:
        cs = CalcStraightness(
            ssu_type=ssu_type.lower() if isinstance(ssu_type, str) else ssu_type,
            beta=float(beta),
            D=float(D),
            ms_before=ms_before,
            ms_after=ms_after,
            skip=False,
        )
        res = cs.calculate()
        _log.info("Straightness: расчёт выполнен")
        return res
    except Exception as exc:
        _log.warning("Straightness: расчёт не выполнен: %s", exc)
        return None

# -------------------- Точка входа --------------------

def run_calculation(*args: Any, **kwargs: Any):
    """run_calculation(prepared, values_si, raw)
    Шаги: термокоррекция → создание ССУ → методы ССУ → запуск CalcFlow.
    """
    if len(args) < 2:
        raise ValueError("run_calculation(prepared, values_si[, raw]) — минимум 2 аргумента")

    prepared = args[0]
    values: Mapping[str, Any] = args[1] or {}
    raw: Mapping[str, Any] = args[2] if len(args) >= 3 else {}

    # -------------------- 1) Геометрия и температурная поправка --------------------
    v = dict(values)

    # Холодные и/или тёплые диаметры
    D20 = v.get("D20")
    d20 = v.get("d20")
    D = v.get("D")
    d = v.get("d")

    # Температура эксплуатации (°C) из raw/values
    def _get_phys(key: str):
        try:
            node = raw.get("physPackage", {}).get("physProperties", {}).get(key)
            if isinstance(node, dict) and "real" in node:
                return node["real"]
            return node
        except Exception:
            return None

    T_val = _get_phys("T")
    if T_val is None and "T" in v:
        T_val = v["T"]

    # Стали и шероховатость из lenPackage
    lp = (raw.get("lenPackage") or {}).get("lenProperties", {})
    d20_steel = lp.get("d20_steel")
    D20_steel = lp.get("D20_steel")

    Ra_raw = lp.get("Ra")
    # Нормализуем Ra → метры
    Ra_m = None
    if isinstance(Ra_raw, dict):
        _ra_real = Ra_raw.get("real")
        _ra_unit = str(Ra_raw.get("unit") or "").lower()
        if _ra_real is not None:
            if "µ" in _ra_unit or "um" in _ra_unit:
                Ra_m = float(_ra_real) * 1e-6
            elif "mm" in _ra_unit:
                Ra_m = float(_ra_real) * 1e-3
            else:
                Ra_m = float(_ra_real)  # считаем метрами по умолчанию
    elif Ra_raw is not None:
        Ra_m = float(Ra_raw)

    theta = lp.get("theta")
    alpha_raw = lp.get("alpha")
    alpha_lp = (alpha_raw.get("real") if isinstance(alpha_raw, dict) else alpha_raw)

    # kt (если вдруг есть уже в values)
    kt = v.get("kt")

    # Термокоррекция: приоритет D20/d20 + материалы + T; иначе используем имеющиеся D,d
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
        # если D,d уже есть — используем (при наличии kt умножаем)
        if D is not None and d is not None:
            D = float(D); d = float(d)
            if kt is not None:
                D *= float(kt); d *= float(kt)
        else:
            # иначе пробуем сырые D20/d20
            if D20 is None or d20 is None:
                raise KeyError("Нужны диаметры: D и d (или D20 и d20)")
            D = float(D20)
            d = float(d20)

    # Фиксируем тёплые диаметры и больше D20/d20 не тянем
    v["D"], v["d"] = float(D), float(d)
    v.pop("D20", None); v.pop("d20", None)

    # -------------------- 2) Создание ССУ через фабрику --------------------
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

    # Давление p для конструкторов, которые требуют именно 'p'
    if "p" not in v:
        v["p"] = v.get("p1", v.get("p_abs", _get_phys("p_abs")))

    # Шероховатость (для Eccentric и др.)
    if Ra_m is not None:
        v["Ra"] = Ra_m

    # k из physProperties.k
    if "k" not in v or v["k"] is None:
        kval = _get_phys("k")
        if kval is not None:
            v["k"] = float(kval)

    # Пусковой Re, если не пришёл заранее
    if "Re" not in v or v["Re"] is None:
        v["Re"] = 1.0e5

    kwargs = dict(v)
    kwargs.setdefault("do_validate", False)

    from orifices_classes.main import create_orifice
    _log.info("create_orifice(name=%s, kwargs=%s)", ssu_name, sorted([k for k in kwargs.keys() if k not in ("rho","mu","kappa","is_gas")]))
    ssu = create_orifice(ssu_name, **kwargs)

    # Гарантируем наличие давления в объекте (нужно для calculate_epsilon)
    try:
        if "p" in v:
            ssu.p = float(v["p"])  # важно для DoubleOrifice и Eccentric
    except Exception:
        pass

    # Термокоррекция геометрии средствами ССУ (если доступны данные и метод)
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
            # Обновим D,d в values из объекта
            if hasattr(ssu, "D") and hasattr(ssu, "d"):
                v["D"] = float(getattr(ssu, "D"))
                v["d"] = float(getattr(ssu, "d"))
    except Exception as e:
        _log.warning("update_geometry_from_temp не выполнен: %s", e)

    # Валидация геометрии
    if hasattr(ssu, "validate"):
        if not ssu.validate():
            raise ValueError(f"Валидация геометрии ССУ '{ssu_name}' не пройдена")

    # Шероховатость (в метрах)
    try:
        if Ra_m is not None and hasattr(ssu, "validate_roughness"):
            valid_rough = ssu.validate_roughness(float(Ra_m))
            v["valid_roughness"] = bool(valid_rough)
    except Exception as e:
        _log.warning("validate_roughness не выполнен: %s", e)

    # Полный расчёт параметров ССУ
    ssu_results = None
    try:
        if hasattr(ssu, "run_all"):
            delta_p = v.get("dp", _get_phys("dp"))
            p_in = v.get("p1", v.get("p_abs", _get_phys("p_abs")))
            k_val = v.get("k")
            ssu_results = ssu.run_all(
                delta_p=delta_p,
                p=p_in,
                k=k_val,
                Ra=float(Ra_m) if Ra_m is not None else None,
                alpha=v.get("alpha"),
            )
            v["ssu_results"] = ssu_results
    except Exception as e:
        _log.warning("run_all не выполнен: %s", e)

    # -------------------- 3) Запуск CalcFlow --------------------
    _log.info("Маршрут: calc_flow.calcflow → CalcFlow | run_all")

    cf_mod = import_module("calc_flow.calcflow")
    CF = getattr(cf_mod, "CalcFlow")

    # Подготовим позиционные аргументы под явную сигнатуру CalcFlow
    d_ = float(v["d"])  # тёплый
    D_ = float(v["D"])  # тёплый
    p1_ = float(v.get("p1", v.get("p_abs", _get_phys("p_abs"))))
    t_ = v.get("t1", v.get("T", _get_phys("T")))
    t1_ = float(t_) + 273.15 if t_ is not None and float(t_) < 200 else float(t_)
    dp_ = float(v.get("dp", _get_phys("dp")))
    mu_ = float(v.get("mu", _get_phys("mu")))
    Roc_ = float(v.get("Roc", _get_phys("Roc")))
    Ro_ = float(v.get("Ro", _get_phys("Ro")))
    k_ = float(v.get("k", _get_phys("k")))

    pos_args = (d_, D_, p1_, t1_, dp_, mu_, Roc_, Ro_, k_, ssu)
    _log.debug("Пробую CalcFlow(*positional %d args)", len(pos_args))
    cf = CF(*pos_args)

    # Прокинем коэффициенты из результатов ССУ (если есть)
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

    # Запуск полного расчёта расходов
    if hasattr(cf, "run_all") and callable(cf.run_all):
        _log.info("Вызов CalcFlow.run_all()")
        flow_res = cf.run_all()
        # Straightness (если заданы параметры)
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
        }
        return result

    # Резервные имена (на всякий случай)
    for mname in ("run", "run_calculations", "calculate", "calc", "compute", "main", "start"):
        method = getattr(cf, mname, None)
        if callable(method):
            _log.info("Вызов CalcFlow.%s()", mname)
            flow_res = method()
            straight_res = _maybe_calc_straightness(ssu_name, d_, D_, Ra_m, raw)
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
            }
            return result

    raise AttributeError("В CalcFlow не найден метод запуска расчёта")


__all__ = ["run_calculation"]
