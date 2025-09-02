def calc_cylindrical_geometry(D: float, d: float, beta: float) -> dict:
    checks = {}

    checks['Толщина Ed'] = f"≤ {0.1 * D:.5f} м"

    lf_nom = d * (
        68.469302
        + 42.26572 * beta**2
        + 56.237191 * beta**4
        + 21.311556 * beta**6
    )
    tol_lf = 0.02 * lf_nom
    checks['Длина lf'] = f"{lf_nom:.5f} ± {tol_lf:.5f} м"

    half_diff_max = lf_nom / 2000
    checks['Полурасхождение конусообразности'] = f"≤ {half_diff_max:.5f} м"

    return checks
