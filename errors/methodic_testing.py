import math
from math import sqrt

#(10.13) для ЖИДКОСТИ:
print("=== 10.13 (газ, рабочие условия) ===")
def formula_10_13(delta_C, theta_D, delta_D, theta_d, delta_d, delta_dp, delta_rho, delta_v):
    return sqrt(
        (delta_C)**2
        + (theta_D**2) * (delta_D**2)
        + (theta_d**2) * (delta_d**2)
        + 0.25 * ((delta_dp**2) + (delta_rho**2))
        + (delta_v**2)
    )

cases = [
    ("1", 0.50, 0.7, 0.01, 0.4, 0.7, 0.08, 0.18, 0.21),
    ("2", 0.20, 1.0, 0.30, 2.0, 0.10, 0.3, 0.5, 0.4),
    ("3", 0.10, 0.25, 0.10, 0.90, 0.70, 0.80, 0.60, 0.7),
    ("4", 0.70, 0.12, 0.480, 0.5, 0.00, 0.23, 0.42, 0.75),
    ("5", 0.15, 0.8, 0.25, 1.2, 0.12, 0.50, 0.40, 0.20),]

for title, dC, tD, dD, td, dd, ddp, drho, dv in cases:
    total = formula_10_13(dC, tD, dD, td, dd, ddp, drho, dv)
    print(f"--- {title} ---")
    print(f"δ {total}%")


def formula_10_14(delta_C, theta_D, delta_D, theta_d, delta_d, delta_dp, delta_rho, delta_eps, delta_v,
                  add_segment_1_2=False):
    base = sqrt(
        (delta_C)**2
        + (theta_D**2) * (delta_D**2)
        + (theta_d**2) * (delta_d**2)
        + 0.25 * ((delta_dp**2) + (delta_rho**2))
        + (delta_eps**2)
        + (delta_v**2)
    )
    return base + (1.2 if add_segment_1_2 else 0.0)

def formula_10_15(delta_C, theta_D, delta_D, theta_d, delta_d,
                  delta_dp, delta_rho, delta_eps, delta_v,
                  delta_p_st=0.0, delta_T_st=0.0, delta_Z_st=0.0,
                  add_segment_1_2=False):
    base_sq = (
        (delta_C)**2
        + (theta_D**2) * (delta_D**2)
        + (theta_d**2) * (delta_d**2)
        + 0.25 * ((delta_dp**2) + (delta_rho**2))
        + (delta_eps**2)
        + (delta_v**2)
        + 0.25 * ((delta_p_st**2) + (delta_T_st**2))
        + (delta_Z_st**2)
    )
    base = sqrt(base_sq)
    return base + (1.2 if add_segment_1_2 else 0.0)


print("=== 10.14 (газ, рабочие условия) ===")
cases_1014 = [
    ("1", 0.40, 0.8, 0.20, 1.1, 0.10, 0.50, 0.60, 0.30, 0.00),      # без 1.2%
    ("2", 0.20, 1.0, 0.30, 2.0, 0.10, 0.30, 0.50, 0.40, 0.00),      # без 1.2%
    ("3", 0.15, 0.6,  0.25, 1.3, 0.12, 0.40, 0.45, 0.20, 1.00),     # сегментная: +1.2%
    ("4", 0.05, 0.3,  0.05, 0.7, 0.04, 0.20, 0.20, 0.10, 0.00),     # низкие уровни
    ("5", 0.80, 1.0,  0.40, 2.0, 0.20, 0.90, 0.80, 0.50, 1.00),     # сегментная: +1.2%
]
for t, dC, tD, dD, td, dd, ddp, drho, deps, seg in cases_1014:
    total = formula_10_14(dC, tD, dD, td, dd, ddp, drho, deps, 0.0, add_segment_1_2=bool(seg))
    print(f"{t}: δ_q {total}%")

print("\n=== 10.15 (газ, приведённый к СУ) ===")
cases_1015 = [
    ("1", 0.40,0.8,0.20, 1.1,0.10, 0.50,0.60,0.30, 0.00,  0.20,  0.20,  0.10, 0),
    ("2", 0.20,1.0,0.30, 2.0,0.10, 0.30,0.50,0.40, 0.00,  0.30,  0.40,  0.20, 0),
    ("3", 0.15,0.6,0.25, 1.3,0.12, 0.40,0.45,0.20, 0.10,  0.20,  0.30,  0.15, 1),  # сегментная: +1.2%
    ("4", 0.05,0.3,0.05, 0.7,0.04, 0.20,0.20,0.10, 0.00,  0.10,  0.10,  0.00, 0),
    ("5", 0.80,1.0,0.40, 2.0,0.20, 0.90,0.80,0.50, 0.20,  0.60,  0.50,  0.30, 1),  # сегментная: +1.2%
]
for t, dC,tD,dD, td,dd, ddp,drho,deps, dv,  dp_st,dT_st,dZ_st, seg in cases_1015:
    total = formula_10_15(dC,tD,dD, td,dd, ddp,drho,deps, dv, dp_st,dT_st,dZ_st, add_segment_1_2=bool(seg))
    print(f"{t}: δ_q,std  {total}%")



from math import pi

print('=== (10.16)–(10.21) ===')

# конусные ССУ
def theta_cone_D(beta):            # (10.16)
    return 2*(1 + beta**2 + beta**4) / (beta**2 * (1 + beta**2))

def theta_cone_d(beta):            # (10.17)
    return 2 / (beta**2 * (1 + beta**2))

# клиновые и сегментные
def theta_wedge_seg_D(beta, h, D): # (10.18)
    otn = h / D
    return 2 - ((8 * otn) * (otn - (otn)**2)**0.5 ) / (pi * beta**2 * (1 - beta**4))    #todo проверить H во 2 части

def theta_wedge_seg_d(beta, h, D): # (10.19)
    otn = h / D
    return ((8 * otn) * (otn - (otn)**2)**0.5 ) / (pi * beta**2 * (1 - beta**4))    #todo проверить H во 2 части

# прочие типы ССУ
def theta_other_D(beta):           # (10.20)
    return (2 * beta**4) / (1 - beta**4)

def theta_other_d(beta):           # (10.21)
    return 2 / (1 - beta**4)

# контрольные кейсы
cases = [
    ("cone β=0.40",                "cone",      {"beta":0.40}),
    ("cone β=0.65",                "cone",      {"beta":0.65}),
    ("segment β=0.50, h/D=0.20",   "wedge_seg", {"beta":0.50, "h":20.0, "D":100.0}),
    ("wedge β=0.55, h/D=0.15",     "wedge_seg", {"beta":0.55, "h":15.0, "D":100.0}),
    ("other β=0.62",               "other",     {"beta":0.62}),
]

for title, kind, p in cases:
    beta = p["beta"]
    if kind == "cone":
        thD = theta_cone_D(beta)
        thd = theta_cone_d(beta)
    elif kind == "wedge_seg":
        thD = theta_wedge_seg_D(beta, p["h"], p["D"])
        thd = theta_wedge_seg_d(beta, p["h"], p["D"])
    else:
        thD = theta_other_D(beta)
        thd = theta_other_d(beta)
    print(f"{title}: θ_D={thD}  θ_d={thd}")



print('=== (10.22) ===')

def formula_10_22(delta_eps0, s_inv, delta_dp, delta_p, delta_kappa):
    k = s_inv - 1.0
    return (delta_eps0**2 + (k**2) * (delta_dp**2 + delta_p**2 + delta_kappa**2))**0.5

# 5 прогонов
cases = [
    ("1", 0.10, 1.00, 0.20, 0.20, 0.10),
    ("2", 0.10, 1.20, 0.20, 0.20, 0.10),
    ("3", 0.05, 1.50, 0.30, 0.25, 0.15),
    ("4", 0.20, 0.90, 0.10, 0.10, 0.10),
    ("5", 0.12, 2.00, 0.50, 0.40, 0.30),
]

for title, de0, s_inv, ddp, dp, dk in cases:
    total = formula_10_22(de0, s_inv, ddp, dp, dk)
    print(f"--- {title} ---")
    print(f"δε0={de0}%  s^-1={s_inv}  δΔp={ddp}%  δp={dp}%  δκ={dk}%")
    print(f"δε = {total}%\n")


from typing import List, Sequence

# --- Таблица 4 — коэффициенты чувствительности θ для формулы (10.23)
# Допустимые типы функций: 'Линейная', 'Квадратичная'
# Поддержаны кейсы из Таблицы 4: n=2 и n=3

def table4_theta(funcs: Sequence[str]) -> List[int]:
    """
    Возвращает список θ одинаковой длины с funcs по Таблице 4.
    funcs: список типов звеньев в порядке 1-го, 2-го, (3-го).
           Каждый элемент: 'Линейная' или 'Квадратичная'
    """
    f = tuple(funcs)
    n = len(f)
    # нормализуем регистр и пробелы
    f = tuple(s.strip().capitalize() for s in f)

    if n == 2:
        if f == ('Линейная', 'Линейная'):
            return [1, 1]
        if f == ('Линейная', 'Квадратичная'):
            return [1, 2]
        if f == ('Квадратичная', 'Линейная'):
            return [2, 2]
        raise ValueError("Таблица 4: поддержаны только три варианта для n=2: "
                         "Линейная+Линейная; Линейная+Квадратичная; Квадратичная+Линейная")

    if n == 3:
        if f == ('Линейная', 'Линейная', 'Линейная'):
            return [1, 1, 1]
        if f == ('Линейная', 'Линейная', 'Квадратичная'):
            return [1, 1, 2]
        if f == ('Линейная', 'Квадратичная', 'Линейная'):
            return [1, 2, 2]
        if f == ('Квадратичная', 'Линейная', 'Линейная'):
            return [2, 2, 2]
        raise ValueError("Таблица 4: поддержаны только четыре варианта для n=3: "
                         "Линейная/Линейная/Линейная; "
                         "Линейная/Линейная/Квадратичная; "
                         "Линейная/Квадратичная/Линейная; "
                         "Квадратичная/Линейная/Линейная")

    raise ValueError("Таблица 4 определяет коэффициенты для цепочек из 2 или 3 звеньев.")


# --- Формула (10.23): δ_chain = sqrt( sum_i θ_i * δ_i^2 )
def formula_10_23(deltas: Sequence[float], funcs: Sequence[str]) -> float:
    """
    deltas: относительные погрешности звеньев (в %, по порядку 1..n)
    funcs:  типы звеньев ('Линейная'/'Квадратичная'), столько же, сколько deltas
    """
    thetas = table4_theta(funcs)
    if len(thetas) != len(deltas):
        raise ValueError("Число θ и число δ должно совпадать.")
    s = 0.0
    for theta, d in zip(thetas, deltas):
        s += theta * (float(d) ** 2)
    return sqrt(s)


# ===== 5 прогонов (контроль) =====
cases = [
    # title, deltas(%), funcs
    ("1: n=2 L+L",   [0.20, 0.30],                ['Линейная','Линейная']),
    ("2: n=2 L+Q",   [0.20, 0.30],                ['Линейная','Квадратичная']),
    ("3: n=2 Q+L",   [0.20, 0.30],                ['Квадратичная','Линейная']),
    ("4: n=3 L+L+L", [0.10, 0.15, 0.12],          ['Линейная','Линейная','Линейная']),
    ("5: n=3 L+Q+L", [0.10, 0.15, 0.12],          ['Линейная','Квадратичная','Линейная']),
]

for title, deltas, funcs in cases:
    val = formula_10_23(deltas, funcs)
    thetas = table4_theta(funcs)
    print(f"--- {title} ---")
    print(f"θ = {thetas}  δ = {['%.3f%%'%d for d in deltas]}  =>  δ_chain = {val:.6g}%")


# theta_gost10/normalization.py

