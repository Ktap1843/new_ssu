# path: controllers/calculation_adapter.py
"""
Связка блоков — по шагам и без «магии»:
1) Берём вход: run_calculation(prepared, values_si, raw)
2) Готовим геометрию при рабочей температуре:
   - используем D20/d20 и стали D20_steel/d20_steel + T (°C) из raw
   - температурную коррекцию делаем методами пакета материалов
   - дальше в конвейере используем только скорректированные D,d (D20/d20 дальше не тянем)
3) Создаём экземпляр ССУ через orifices_classes.main.create_orifice(name=raw['type'], **kwargs)
   - добавляем недостающие обязательные параметры (например, alpha из lenPackage.lenProperties.theta)
   - Re не считаем: если требуется — должен прийти в values_si
   - do_validate=False, затем валидируем после термокоррекции
4) Вызываем методы ССУ: update_geometry_from_temp → validate → validate_roughness → run_all
5) Когда ССУ готово, запускаем основной расчёт через calc_flow.calcflow (CalcFlow или функции)
"""
from __future__ import annotations

from importlib import import_module
from typing import Any, Mapping

# --- Logger (корневой, по проекту) ---
try:
    from logger_config import get_logger  # предпочтительно, как в проекте
    _log = get_logger("CalculationAdapter")
except Exception:
    try:
        from logger import get_logger  # альтернативное имя
        _log = get_logger("CalculationAdapter")
    except Exception:  # no-op
        class _Dummy:
            def info(self, *a, **k): pass
            def debug(self, *a, **k): pass
            def warning(self, *a, **k): pass
            def error(self, *a, **k): pass
        _log = _Dummy()


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

    # 0) Шаги (если есть)
    try:
        steps = list(raw.get("ctrlRequest", {}).get("steps", []))
    except Exception:
        steps = []

    # 1) Диаметры и температурная поправка (всегда переходим к «тёплым» D,d)
    v = dict(values)

    # Пытаемся взять исходные холодные размеры при 20°C
    D20 = v.get("D20")
    d20 = v.get("d20")
    # На всякий случай поддержим D/d, если уже готовы
    D = v.get("D")
    d = v.get("d")

    # Температура эксплуатации (°C) из raw
    try:
        T_val = raw.get("physPackage", {}).get("physProperties", {}).get("T", {}).get("real")
    except Exception:
        T_val = None
    if T_val is None and "T" in v:
        T_val = v["T"]

    # Стали для коэффициентов линейного расширения
    try:
        lp = raw.get("lenPackage", {}).get("lenProperties", {})
        d20_steel = lp.get("d20_steel")
        D20_steel = lp.get("D20_steel")
        Ra_raw = lp.get("Ra")
        # Нормализуем Ra в метры (поддержка unit: um, µm, mm, m)
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
                    # считаем в метрах по умолчанию
                    Ra_m = float(_ra_real)
        elif Ra_raw is not None:
            # если пришло число без unit — считаем в метрах
            Ra_m = float(Ra_raw)
        theta = lp.get("theta")
        alpha_raw = lp.get("alpha")
        alpha_lp = (alpha_raw.get("real") if isinstance(alpha_raw, dict) else alpha_raw)
    except Exception:
        d20_steel = D20_steel = Ra_um = theta = None

    # Если есть холодные размеры и данные для термокоррекции — используем их
    if D20 is not None and d20 is not None and T_val is not None and (d20_steel or D20_steel):
        try:
            from orifices_classes.materials import calc_alpha
            T_c = float(T_val)
            dT = T_c - 20.0
            alpha_D = float(calc_alpha(D20_steel, T_c)) if D20_steel else 0.0
            alpha_d = float(calc_alpha(d20_steel, T_c)) if d20_steel else 0.0
            D = float(D20) * (1.0 + alpha_D * dT)
            d = float(d20) * (1.0 + alpha_d * dT)
            _log.info("Термокоррекция: D20=%.6g→D=%.6g, d20=%.6g→d=%.6g (ΔT=%.3g°C)", D20, D, d20, d, dT)
        except Exception as e:
            _log.warning("Не удалось применить термокоррекцию: %s — используем исходные значения", e)
            D = float(D or D20)
            d = float(d or d20)
    else:
        # Иначе используем то, что уже пришло (D,d) или просто D20,d20 как есть
        if D is None and D20 is not None:
            D = float(D20)
        if d is None and d20 is not None:
            d = float(d20)
        if D is None or d is None:
            raise KeyError("Нужны диаметры: D и d (или D20 и d20)")

    # Фиксируем «тёплые» диаметры и больше D20/d20 не тянем
    v["D"], v["d"] = float(D), float(d)
    v.pop("D20", None); v.pop("d20", None)

    # 2) Создаём экземпляр ССУ через orifices_classes.main
    try:
        from orifices_classes.main import create_orifice
    except Exception as exc:
        _log.error("Импорт orifices_classes.main.create_orifice не удался: %s", exc)
        raise

    # Тип ССУ строго из raw
    try:
        ssu_name = str(raw.get("type", "")).strip().lower()
    except Exception:
        ssu_name = ""
    if not ssu_name:
        raise KeyError("В raw['type'] не задан тип ССУ (например: 'cone', 'orifice')")

    # Обязательные параметры: alpha для некоторых типов (например, cone)
    # приоритет: values_si['alpha'] → lenPackage.lenProperties.alpha → lenPackage.lenProperties.theta
    if "alpha" not in v:
        _alpha_val = alpha_lp if alpha_lp is not None else theta
        if _alpha_val is not None:
            v["alpha"] = _alpha_val

    # Давление для DoubleOrifice и др.: p ← p1/p_abs
    if "p" not in v:
        try:
            _p_node = raw.get("physPackage", {}).get("physProperties", {}).get("p_abs")
            _p_from_raw = _p_node.get("real") if isinstance(_p_node, dict) else _p_node
        except Exception:
            _p_from_raw = None
        v["p"] = v.get("p1", v.get("p_abs", _p_from_raw))

    # Шероховатость для EccentricOrifice и подобных: Ra в МЕТРАХ
    if Ra_m is not None:
        v["Ra"] = Ra_m

    # ВАЖНО: некоторым классам нужен Re в __init__. Берём из values_si, иначе пусковой.
    if "Re" not in v or v["Re"] is None:
        v["Re"] = 1.0e5

    kwargs = dict(v)
    kwargs.setdefault("do_validate", False)
    kwargs.setdefault("do_validate", False)

    _log.info("create_orifice(name=%s, kwargs=%s)", ssu_name, sorted([k for k in kwargs.keys() if k not in ("rho","mu","kappa","is_gas")]))
    ssu = create_orifice(ssu_name, **kwargs)

    # Гарантируем наличие давления в объекте ССУ для методов типа calculate_epsilon
    try:
        if "p" in v:
            ssu.p = float(v["p"])  # важно для DoubleOrifice
    except Exception:
        pass

    # 3) Методы ССУ: термокоррекция → validate → validate_roughness → run_all
    # Термокоррекция геометрии средствами класса (если метод доступен)
    try:
        if hasattr(ssu, "update_geometry_from_temp") and (D20 is not None and d20 is not None and T_val is not None):
            from orifices_classes.materials import calc_alpha  # уже импортировали выше — дублим локально на случай ограничений
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
            # После обновления — берём актуальные D,d внутрь values
            if hasattr(ssu, "D") and hasattr(ssu, "d"):
                v["D"] = float(getattr(ssu, "D"))
                v["d"] = float(getattr(ssu, "d"))
    except Exception as e:
        _log.warning("update_geometry_from_temp не выполнен: %s", e)

    # Валидация
    if hasattr(ssu, "validate"):
        if not ssu.validate():
            raise ValueError(f"Валидация геометрии ССУ '{ssu_name}' не пройдена")

    # Шероховатость, если задана (в метрах)
    try:
        if Ra_m is not None and hasattr(ssu, "validate_roughness"):
            valid_rough = ssu.validate_roughness(float(Ra_m))
            v["valid_roughness"] = bool(valid_rough)
    except Exception as e:
        _log.warning("validate_roughness не выполнен: %s", e)

    # Полный расчёт параметров ССУ, если есть метод run_all
    ssu_results = None
    try:
        if hasattr(ssu, "run_all"):
            # Выберем базовые аргументы из values/raw
            delta_p = v.get("dp")
            p_in = v.get("p1", v.get("p_abs"))
            k_val = v.get("k") or raw.get("physPackage", {}).get("physProperties", {}).get("k", {}).get("real") if isinstance(raw.get("physPackage", {}), dict) else None
            ssu_results = ssu.run_all(
                delta_p=delta_p, p=p_in, k=k_val,
                Ra=float(Ra_m) if Ra_m is not None else None,
                alpha=v.get("alpha"),
            )
            v["ssu_results"] = ssu_results
    except Exception as e:
        _log.warning("run_all не выполнен: %s", e)

    # 4) Запускаем CalcFlow (как и раньше)
    _log.info("Маршрут: calc_flow.calcflow → CalcFlow | функции")

    import inspect

    # 2) Идём напрямую в calc_flow.calcflow
    _log.info("Маршрут: calc_flow.calcflow → CalcFlow | функции")

    # Попытка: класс CalcFlow — создаём строго по сигнатуре и запускаем run_all
    try:
        cf_mod = import_module("calc_flow.calcflow")
        CF = getattr(cf_mod, "CalcFlow", None)
    except Exception as exc:
        CF = None
        _log.warning("Импорт calc_flow.calcflow не удался: %s", exc)

    if CF is not None:
        # Подготовим позиционные аргументы в точном порядке конструктора
        def _get_phys(key: str):
            try:
                node = raw.get("physPackage", {}).get("physProperties", {}).get(key)
                if isinstance(node, dict) and "real" in node:
                    return node["real"]
                return node
            except Exception:
                return None

        d_ = float(v["d"])  # уже тёплый
        D_ = float(v["D"])  # уже тёплый
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
        ssu_results = v.get("ssu_results") or {}
        try:
            # C
            C_val = ssu_results.get("C")
            if C_val is not None:
                cf.C = float(C_val)
            # E (или E_speed)
            E_val = ssu_results.get("E", ssu_results.get("E_speed"))
            if E_val is not None:
                cf.E = float(E_val)
            # epsilon (или Epsilon)
            eps_val = ssu_results.get("epsilon", ssu_results.get("Epsilon"))
            if eps_val is not None:
                cf.epsilon = float(eps_val)
            # beta (если нет — d/D)
            beta_val = ssu_results.get("beta")
            if beta_val is None and D_:
                beta_val = d_ / D_
            if beta_val is not None:
                cf.beta = float(beta_val)
        except Exception as e:
            _log.warning("Не удалось установить коэффициенты из SSU: %s", e)

        # Запуск полного расчёта
        if hasattr(cf, "run_all") and callable(cf.run_all):
            _log.info("Вызов CalcFlow.run_all()")
            return cf.run_all()
        # Резервные имена метода старта
        for mname in ("run", "run_calculations", "calculate", "calc", "compute", "main", "start"):
            method = getattr(cf, mname, None)
            if callable(method):
                _log.info("Вызов CalcFlow.%s()", mname)
                return method()

    # Фолбэк: модульные функции в calc_flow.calcflow и calc_flow.main
    for mod_name in ("calc_flow.calcflow", "calc_flow.main"):
        try:
            mod = import_module(mod_name)
        except Exception as exc:
            _log.debug("Модуль %s: импорт не удался: %s", mod_name, exc)
            continue
        # Подсветим, что вообще есть в модуле — поможет согласовать имена
        try:
            avail = [n for n in dir(mod) if not n.startswith("_")]
            _log.info("%s: доступно: %s", mod_name, ", ".join(sorted(avail)))
        except Exception:
            pass
        for fname in method_candidates:
            fn = getattr(mod, fname, None)
            if not callable(fn):
                continue
            for call in ((prepared, v, raw), (v, raw), (v,), tuple()):
                try:
                    _log.info("Вызов %s.%s(%d args)", mod_name, fname, len(call))
                    return fn(*call)
                except TypeError:
                    continue

    # Фолбэк 2: контроллер верхнего уровня (если есть в проекте)
    for ctrl_mod_name in ("controllers.calculation_controller", "calculation_controller"):
        try:
            ctrl_mod = import_module(ctrl_mod_name)
        except Exception as exc:
            _log.debug("Контроллер %s: импорт не удался: %s", ctrl_mod_name, exc)
            continue
        # Ищем CalculationController
        CC = getattr(ctrl_mod, "CalculationController", None)
        if CC is None:
            # попробуем найти любой класс с таким методом
            for n in dir(ctrl_mod):
                obj = getattr(ctrl_mod, n)
                if hasattr(obj, "__name__") and "CalculationController" in n:
                    CC = obj
                    break
        if CC is None:
            continue
        # Пытаемся создать и запустить run_calculations
        try:
            _log.info("Пробую %s.CalculationController(data, prepared)", ctrl_mod_name)
            cc = CC(raw, prepared)
            if hasattr(cc, "run_calculations") and callable(cc.run_calculations):
                return cc.run_calculations()
        except TypeError:
            try:
                _log.info("Пробую %s.CalculationController(prepared, raw)", ctrl_mod_name)
                cc = CC(prepared, raw)
                if hasattr(cc, "run_calculations") and callable(cc.run_calculations):
                    return cc.run_calculations()
            except Exception as exc:
                _log.debug("Controller вызов не удался: %s", exc)
                continue

    raise ImportError("Не найден CalcFlow, функции в calc_flow.* и CalculationController.run_calculations() не обнаружены/не вызвались")
    for mod_name in ("calc_flow.calcflow", "calc_flow.main"):
        try:
            mod = import_module(mod_name)
        except Exception:
            continue
        for fname in method_candidates:
            fn = getattr(mod, fname, None)
            if not callable(fn):
                continue
            for call in ((prepared, v, raw), (v, raw), (v,), tuple()):
                try:
                    _log.info("Вызов %s.%s(%d args)", mod_name, fname, len(call))
                    return fn(*call)
                except TypeError:
                    continue
    raise ImportError("Не найден CalcFlow и подходящие функции в calc_flow.calcflow / calc_flow.main")


__all__ = ["run_calculation"]
