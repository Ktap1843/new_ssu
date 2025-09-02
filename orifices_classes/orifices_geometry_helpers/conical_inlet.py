import numpy as np

def calc_f_angle(beta, betas, f_degrees):
    return float(np.interp(beta, betas, f_degrees))

def calc_e1_nominal(d, beta, betas, d_over_e1_table):
    d_over_e1 = float(np.interp(beta, betas, d_over_e1_table))
    return d / d_over_e1

def calc_e_nominal(d):
    return 0.021 * d

def calc_e_tol(d):
    return min(0.0025 * d, 0.00004)
