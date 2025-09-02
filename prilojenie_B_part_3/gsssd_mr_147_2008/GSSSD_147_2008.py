import math
from prettytable import PrettyTable
from calc_A import get_A0, get_A1
from calc_output_value import get_H, get_Hdf, get_K, get_Kdf, get_Mu
from tables import R, Bj, Bj_, Cj_, Mj_, Nj, Nj_, Pkr, Tkr, Rokr, Zkr, Aj, Mj


# формула 40, 20, 21
def get_Pi_Tau(p, T):
    if p and T:
        pi = p / Pkr
        tau = T / Tkr
    elif T:
        tau = T / Tkr
        teta = 1 - tau
        pi = get_Pis(tau, teta)
    else:
        pi = p / Pkr
        tau = get_Taus(pi)
    return tau, pi


# формула 20
def get_Pis(tau, teta):
    return math.exp(sum((aj * teta ** (0.5 * mj) for aj, mj in zip(Aj, Mj))) / tau)


# формула 21
def get_Taus(pi):
    return 1 + sum((bj * (abs(math.log(pi))) ** (0.5 * nj) for bj, nj in zip(Bj, Nj)))


# формула 41-42 однофазная область
def get_W0(tau, pi):
    if tau < 1:
        teta = 1 - tau
        pis = get_Pis(tau, teta)
        if pi > pis:
            return 3.2
        return pi * Zkr / tau
    else:
        if pi < 1.05:
            return pi * Zkr / tau
        return 9 * pi * Zkr / (tau * (1.1 * pi) + 0.7)


# формула 43-44 насыщенная жидкость и пар
def get_W12(tau):
    W1 = 1 + sum((bj * (1 - tau) ** (nj / 3) for bj, nj in zip(Bj_, Nj_)))
    W2 = math.exp(sum((cj * (1 - tau) ** (mj / 6) for cj, mj in zip(Cj_, Mj_))))
    return W1, W2


# формула 22
def get_Wdf(w1, w2, x):
    return w1 * w2 / (w1 * x + w2 * (1 - x))


# формула 45, 46
def get_W(w0, pi, tau):
    dw = 1000
    while abs(dw/w0) > 10 ** (-6):
        A0 = get_A0(w0, tau)
        A1 = get_A1(w0, tau)
        dw = (pi * Zkr / tau - (1 + A0) * w0) / (1 + A1)
        w0 += dw
    return w0


# формула 47
def get_Ro(w):
    return w * Rokr


def calc_double_phase(x, p = None, T = None):
    tau, pi = get_Pi_Tau(p, T)
    if not p:
        Ps = pi * Pkr
    if not T:
        T = tau * Tkr
    w1, w2 = get_W12(tau)
    w1 = get_W(w1, pi, tau)
    w2 = get_W(w2, pi, tau)
    wdf = get_Wdf(w1, w2, x)
    Ro = get_Ro(wdf)
    if x == 0 or x == 1:
        K = get_K(T, wdf, tau)
        H = get_H(T, wdf, tau)
        Mu = get_Mu(T, Ro, wdf, tau)
    else:
        K = get_Kdf(w2, w1, x, tau, T)
        H = get_Hdf(T, w1, w2, tau, x)
        Mu = None
    if not p:
        return Ro, Ps, K, H, Mu
    return Ro, T, K, H, Mu


def calc_single_phase(p, T):
    tau, pi = get_Pi_Tau(p, T)
    w0 = get_W0(tau, pi)
    w = get_W(w0, pi, tau)
    Ro = get_Ro(w)
    K = get_K(T, w, tau)
    H = get_H(T, w, tau)
    Mu = get_Mu(T, Ro, w, tau)
    return Ro, H, K, Mu


def main(T = None, p = None, x = None):
    if x is not None:
        return calc_double_phase(x, p = p, T = T)
    return calc_single_phase(p, T)


if __name__ == '__main__':
    with open('result.txt', 'w') as file:
        Tlist = [273.15] * 2 + [647] * 2  + [373.15] * 2 + [873.15] * 2 + [1073.15]
        plist = [0.001, 100, 22.5, 100, 0.05, 0.1, 0.05, 30, 100]

        table = PrettyTable()
        table.field_names = ['T', 'p', 'Ro', 'H', 'K', 'Mu']
        for T, p in zip(Tlist, plist):
            Ro, H, K, Mu = list(map(lambda x: round(x, 6), main(p = p, T = T)))
            table.add_row([T, p, Ro, H, K, Mu])
        print(table)
        file.write(table.get_string())
        file.write('\n')

        Tlist = [273.16, 645] * 4
        x_list = [0] * 2 + [1] * 2 + [0.7] * 2 + [0.99999] * 2

        table = PrettyTable()
        table.field_names = ['T', 'x', 'Ro', 'Ps', 'K', 'H', 'Mu']
        for t, x in zip(Tlist, x_list):
            Ro, Ps, Kdf, Hdf, Mu = list(map(lambda x: round(x, 6) if x else x, main(x = x, T = t)))
            table.add_row([t, x, Ro, Ps, Kdf, Hdf, Mu])

        print(table)
        file.write(table.get_string())
        file.write('\n')
    
        table = PrettyTable()
        table.field_names = ['p', 'x', 'Ro', 'Ts', 'K', 'H', 'Mu']
        x_list = [0] * 2 + [0.5, 1] + [0.7] * 2 + [0.99999] * 2
        plist = [0.05, 10, 0.7, 10, 0.05, 0.1, 1]
        for p, x in zip(plist, x_list):
            Ro, Ts, Kdf, Hdf, Mu = list(map(lambda x: round(x, 6) if x else x, main(x = x, p=p)))
            table.add_row([p, x, Ro, Ts, Kdf, Hdf, Mu])
        print(table)
        file.write(table.get_string())