import math
from tables import Baj, Raj, Taj, Gaj, Laj, alphaj, betaj, epsj, gamj

Cj = 0.32
Bj = 0.2
aj = 3.5
lamj = 0.3
d54 = 0.85
d55 = 0.95


# формула 4
def get_A0(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Xj = get_Xj(j, w, tau)
        A += bj * Fi * Xj
    return A


# формула 5
def get_A1(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Xj = get_Xj(j, w, tau)
        Uj = get_Uj(j, w, tau)
        A += bj * Fi * (Xj * (Xj + 1) + Uj)
    return A


# формула 6
def get_A2(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Xj = get_Xj(j, w, tau)
        Sj = get_Sj(j, w, tau)
        Yj = get_Yj(j, w, tau)
        A += bj * Fi * (Xj * (Yj + 1) + Sj)
    return A


# формула 7
def get_A3(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Xj = get_Xj(j, w, tau)
        Yj = get_Yj(j, w, tau)
        A += bj * Fi * (Xj - Yj)
    return A


# формула 8
def get_A4(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Yj = get_Yj(j, w, tau)
        A -= bj * Fi * (Yj + 1)
    return A


# формула 6
def get_A5(w, tau):
    A = 0
    for j, bj in enumerate(Baj):
        Fi = get_Fij(j, w, tau)
        Qj = get_Qj(j, w, tau)
        Yj = get_Yj(j, w, tau)
        A -= bj * Fi * (Yj * (Yj + 1) + Qj)
    return A


# формула 10
def get_Xj(j, w, tau):
    if j <= 50:
        return Raj[j] + Gaj[j] * Laj[j] * w ** Laj[j]
    elif 51 <= j <= 53:
        return Raj[j] - 2 * alphaj[j - 51] * w * (w - epsj[j - 51])
    else:
        deljw = get_deljw(w, tau)
        delj = get_delj(w, tau)
        return Raj[j] - 2 * alphaj[j - 51] * w * (w - epsj[j - 51]) + w * eval(f'd{j}') * deljw / delj


# формула 11
def get_Uj(j, w, tau):
    if j <= 50:
        return Gaj[j] * Laj[j] ** 2 * w ** Laj[j]
    elif 51 <= j <= 53:
        return - 2 * alphaj[j - 51] * w * (2 * w - epsj[j - 51])
    else:
        deljw = get_deljw(w, tau)
        delj = get_delj(w, tau)
        Vj = get_Vj(w, tau)
        return - 2 * alphaj[j - 51] * w * (2 * w - epsj[j - 51]) + w * eval(f'd{j}') / (delj ** 2) * \
                (delj * deljw + w * delj * (deljw / (w - epsj[j - 51]) + 2 * (w - epsj[j - 51]) ** 2 * Vj) - 
                 w * deljw ** 2)


# формула 12
def get_Sj(j, w, tau):
    if j <= 53:
        return 0
    deljwt = get_deljwt(w, tau)
    deljw = get_deljw(w, tau)
    delj = get_delj(w, tau)
    deljt = get_deljt(w, tau)
    return w * eval(f'd{j}') * tau / (delj ** 2) * (delj * deljwt - deljw * deljt)


# формула 13
def get_Yj(j, w, tau):
    if j <= 50:
        return - Taj[j]
    elif 51 <= j <= 53:
        return 2 * betaj[j - 51] * 1 / tau * (1 / tau - gamj[j - 51]) - Taj[j] 
    else:
        teta = get_Tetaj(w, tau)
        delj = get_delj(w, tau)
        return 2 * betaj[j - 51] * 1 / tau * (1 / tau - gamj[j - 51]) - Taj[j] + 2 * eval(f'd{j}') * \
                teta / (tau * delj)


# формула 14
def get_Qj(j, w, tau):
    if j <= 50:
        return 0
    elif 51 <= j <= 53:
        return - 2 * betaj[j - 51] * 1 / tau * (2 / tau - gamj[j - 51])
    else:
        teta = get_Tetaj(w, tau)
        delj = get_delj(w, tau)
        return - 2 * betaj[j - 51] * 1 / tau * (2 / tau - gamj[j - 51]) + 2 * eval(f'd{j}') * (delj *
                (1 - tau * teta) - 2 * teta ** 2) / (tau * delj) ** 2


# формула 3
def get_Tetaj(w, tau):
    return (1 - tau ** (-1)) + Cj * ((w - 1) ** 2) ** (1 / (2 * lamj))


# формула 3
def get_delj(w, tau):
    teta = get_Tetaj(w, tau)
    return teta ** 2 + Bj * ((w - 1) ** 2) ** aj


# формула 2
def get_Fij(j, w, tau):
    if j <= 50:
        return w ** Raj[j] * tau ** (-Taj[j]) * math.exp(Gaj[j] * w ** Laj[j])
    elif 51 <= j <= 53:
        return w ** Raj[j] * tau ** (-Taj[j]) * math.exp(- alphaj[j - 51] * (w - epsj[j - 51]) ** 2 -
                        betaj[j - 51] * (tau ** (-1) - gamj[j - 51]) ** 2)
    else:
        delj = get_delj(w, tau)
        return w ** Raj[j] * tau ** (-Taj[j]) * math.exp(- alphaj[j - 51] * (w - epsj[j - 51]) ** 2 -
                        betaj[j - 51] * (tau ** (-1) - gamj[j - 51]) ** 2) * delj ** (eval(f'd{j}'))


# формула 18
def get_deljwt(w, tau):
    dw = w - 1
    return 2 * dw * Cj / (lamj * tau ** 2) * (dw ** 2) ** (1 / (2 * lamj) - 1)


# формула 17
def get_deljt(w, tau):
    teta = get_Tetaj(w, tau)
    return 2 * teta / (tau ** 2)


# формула 15
def get_deljw(w, tau):
    dw = w - 1
    teta = get_Tetaj(w, tau)
    return 2 * dw * (Cj / lamj * (dw ** 2) ** (1 / (2 * lamj) - 1) * teta + Bj * aj * (dw ** 2) ** (aj - 1))


# формула 16
def get_Vj(w, tau):
    dw = w - 1
    teta = get_Tetaj(w, tau)
    return (Cj / lamj * (dw ** 2) ** (1 / (2 * lamj) - 1)) ** 2 + (2 * teta * Cj / lamj * (1 / (2 * lamj) - 1) * (dw ** 2) ** (1 / (2 * lamj) - 2)) + \
            (2 * Bj * aj * (aj - 1) * (dw ** 2) ** (aj - 2))