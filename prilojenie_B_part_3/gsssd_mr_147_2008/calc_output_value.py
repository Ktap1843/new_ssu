import math
from calc_A import get_A0, get_A1, get_A2, get_A3, get_A5
from tables import Gamj, Pkr, Rokr, Tkr, Aj_, R, Zkr, ajm0, bijm1


# формула 27
def get_Ei(i, T):
    return math.exp(- Gamj[i] * (Tkr / T))

# формула 27
def get_Di(i, T):
    return Gamj[i] * (Tkr / T) / (1 - get_Ei(i, T))


# формула 26
def get_Hor(T):
    return 1 + Aj_[2] + Aj_[1] * (Tkr / T) + sum((Aj_[i] * get_Ei(i, T) * get_Di(i, T) for i in range(3, len(Aj_))))


# формула 25
def get_Cvor(T):
    return Aj_[2] + sum((Aj_[i] * get_Ei(i, T) * get_Di(i, T) ** 2 for i in range(3, len(Aj_))))


# формула 23
def get_H(T, w, tau):
    A3 = get_A3(w, tau)
    Hor = get_Hor(T)
    h = R * T * (Hor + A3)
    return h


# формула 24
def get_K(T, w, tau):
    Cvor = get_Cvor(T)
    A0 = get_A0(w, tau)
    A1 = get_A1(w, tau)
    A2 = get_A2(w, tau)
    A5 = get_A5(w, tau)
    K = 1 / (1 + A0) * (1 + A1 + (1 + A2) ** 2 / (Cvor + A5))
    return K


# формула 28
def get_Hdf(T, w1, w2, tau, x):
    A32 = get_A3(w2, tau)
    A31 = get_A3(w1, tau)
    Hor = get_Hor(T)
    h = R * T * (Hor + x * A32 + (1 - x) * A31)
    return h


# формула 29
def get_Kdf(w2, w1, x, tau, T):
    teta = get_Teta(w1, w2, tau)
    A01 = get_A0(w1, tau)
    Cvrdf = get_Cvrdf(w1, w2, tau, x, T)
    return w2 * teta ** 2 * (w1 * x + w2 * (1 - x)) / (Cvrdf * (1 + A01))



# формула 30
def get_Teta(w1, w2, tau):
    A32 = get_A3(w2, tau)
    A31 = get_A3(w1, tau)
    return (A32 - A31) / (w1 - w2)


# формула 33
def get_dCvr1(w1, w2, teta, tau):
    A21 = get_A2(w1, tau)
    A11 = get_A1(w1, tau)
    return ((1 + A21) - teta * w2) ** 2 / (1 + A11)


# формула 32
def get_dCvr2(w1, w2, teta, tau):
    A22 = get_A2(w2, tau)
    A12 = get_A1(w2, tau)
    return ((1 + A22) - teta * w1) ** 2 / (1 + A12)


# формула 31
def get_Cvrdf(w1, w2, tau, x, T):
    A51 = get_A5(w1, tau)
    A52 = get_A5(w2, tau)
    teta = get_Teta(w1, w2, tau)
    dCvr1 = get_dCvr1(w1, w2, teta, tau)
    dCvr2 = get_dCvr2(w1, w2, teta, tau)
    Cvor = get_Cvor(T)
    return Cvor + (A52 + dCvr2) * x + (A51 + dCvr1) * (1 - x)


# формула 34
def get_Mu(T, Ro, w, tau):
    teta = T / 647.226
    delta = Ro / 317.763
    return 55.071 * get_Mu0(teta) * get_Mu1(teta, delta) * get_Mu2(w, tau)


# формула 35
def get_Mu0(teta):
    return teta ** 0.5 * sum((aj * teta ** (-j) for j, aj in enumerate(ajm0))) ** (-1)


# формула 36
def get_Mu1(teta, delta):
    sumM = 0
    for j, row in enumerate(bijm1):
        for i, bij in enumerate(row):
            sumM += bij * (teta ** (-1) - 1) ** i * (delta - 1) ** j
    return math.exp(delta * sumM)


# формула 37
def get_Mu2(w, tau):
    A1 = get_A1(w, tau)
    Xt = (Rokr / 317.763) ** 2 * (22.115 / Pkr) * w * Zkr / (tau * (1 + A1))
    if Xt >= 21.93:
        return 0.922 * Xt ** 0.0263
    return 1
