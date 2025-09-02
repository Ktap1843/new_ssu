import numpy as np
from logger_config import get_logger

log = get_logger("rules_tables")

# Таблица 4 — Относительная шероховатость Ra/D
RELATIVE_ROUGHNESS_TABLE = {
    0.22: 25.0,
    0.32: 18.2,
    0.35: 12.9,
    0.36: 10.0,
    0.37: 8.3,
    0.39: 7.1,
    0.45: 5.6,
    0.50: 4.9,
    0.60: 4.2,
    0.70: 4.0,
    0.80: 3.9
}

LENGTH_AFTER_SSU = {
    0.05**0.5: 4.0,
    0.2**0.5: 6.0,
    0.4**0.5: 7.0,
    0.6**0.5: 8.0
}

# Таблица 11 — Клин
WEDGE_STRAIGHT_LENGTHS = {
    "elbow_90": 7,
    "elbow_90_double_same_plane": 21,
    "elbow_90_triple_parallel": 22,
    "diffuser": 7,
    "convergent": 7,
    "shutoff_valve": 15,
    "tee_straight": 7,
    "tee_angle": 8
}

# Таблица 12 — Конус
CONE_STRAIGHT_LENGTHS = {
    (0.45, 0.60): {
        "elbow_90": 3,
        "elbow_90_double_perpendicular": 3,
        "diffuser": 3,
        "shutoff_valve": 10
    },
    (0.60, 0.75): {
        "elbow_90": 6,
        "elbow_90_double_perpendicular": 6,
        "diffuser": 3,
        "shutoff_valve": 10
    }
}

# Таблица 9
BETWEEN_MS_LENGTHS = {
    "elbows_same_plane": 17.5,           # Группа колен в одной плоскости
    "elbows_different_planes": 30,       # Группа колен в разных плоскостях
    "elbow": 15,                         # Колено
    "tee": 15,                           # Тройник
    "convergent_reducer": 7.5,           # Конфузор 1:1.5–1:3
    "sudden_expansion": 40,              # Внезапное расширение
    "swirler_30": 45,                    # Закрутка 30°
    "swirler_45": 45,                    # Закрутка 45°
    "swirler_60": 50,                    # Закрутка 60°
    "orifice_beta_025": 12.5,            # Диафрагма β ≥ 0.25
    "chamber_symmetric_inlet": 12.5,     # Форкамера
    "expansion_1_2_to_1_4": 12.5,        # Расширение 1:2–1:4
    "thermowell_003D_013D": 10,          # Гильза 0.03D–0.13D
    "thermowell_lt_003D": 2.5,           # Гильза < 0.03D
    "ball_valve": 15,                    # Шаровой клапан
    "cock": 20,                          # Кран
    "gate_valve": 10,                    # Задвижка
    "stop_valve": 16,                    # Запорный вентиль
    "control_valve_025": 40,             # Рег. вентиль Н=0.25
    "control_valve_050": 30,             # Рег. вентиль Н=0.50
    "control_valve_075": 25,             # Рег. вентиль Н=0.75
    "control_valve_100": 15,             # Рег. вентиль Н=1.00
    "control_reg_valve_025": 22.5,       # Рег. клапан Н=0.25
    "control_reg_valve_050": 17.5,       # Рег. клапан Н=0.50
    "control_reg_valve_100": 12.5,       # Рег. клапан Н=1.00
    "control_damper": 22.5               # Заслонка
}

# Таблица 8 — МС неизвестного типа
UNKNOWN_MS_LENGTHS = {
    0.00: 68,
    0.32: 73,
    0.45: 79,
    0.55: 86,
    0.63: 92,
    0.71: 100,
    0.77: 110
}

# Таблица 5–8
GENERIC_MS_LENGTHS = {
    # Таблица 5
    "elbows_different_planes": {
        0.22: 34, 0.32: 34, 0.39: 36, 0.45: 38, 0.50: 40,
        0.55: 44, 0.59: 47, 0.63: 52, 0.67: 57, 0.71: 63,
        0.74: 69, 0.77: 75, 0.81: 80
    },
    "elbows_same_plane": {
        0.22: 14, 0.32: 16, 0.39: 17, 0.45: 18, 0.50: 20,
        0.55: 22, 0.59: 26, 0.63: 30, 0.67: 33, 0.71: 37,
        0.74: 41, 0.77: 45, 0.81: 50
    },
    "gate_valve": {
        0.22: 12, 0.32: 12, 0.39: 12, 0.45: 12, 0.50: 12,
        0.55: 14, 0.59: 14, 0.63: 15, 0.67: 18, 0.71: 20,
        0.74: 24, 0.77: 27, 0.81: 30
    },
    "stop_valve": {
        0.22: 50, 0.32: 50, 0.39: 50, 0.45: 60, 0.50: 60,
        0.55: 60, 0.59: 60, 0.63: 60, 0.67: 60, 0.71: 60,
        0.74: 60, 0.77: 60, 0.81: 60
    },
    "cock": {
        0.22: 20, 0.32: 20, 0.39: 20, 0.45: 20, 0.50: 30,
        0.55: 30, 0.59: 30, 0.63: 30, 0.67: 40, 0.71: 40,
        0.74: 40, 0.77: 50, 0.81: 60
    },
    "ball_valve": {
        0.22: 18, 0.32: 18, 0.39: 19, 0.45: 20, 0.50: 22,
        0.55: 24, 0.59: 26, 0.63: 28, 0.67: 30, 0.71: 33,
        0.74: 36, 0.77: 40, 0.81: 44
    },

    # Таблица 6
    "control_valve_025": {
        0.22: 30, 0.32: 40, 0.39: 40, 0.45: 50, 0.50: 60,
        0.55: 60, 0.59: 70, 0.63: 70, 0.67: 70, 0.71: 80,
        0.74: 80, 0.77: 80, 0.81: 80
    },
    "control_valve_050": {
        0.22: 30, 0.32: 30, 0.39: 40, 0.45: 40, 0.50: 40,
        0.55: 50, 0.59: 50, 0.63: 60, 0.67: 60, 0.71: 60,
        0.74: 60, 0.77: 70, 0.81: 70
    },
    "control_valve_075": {
        0.22: 30, 0.32: 30, 0.39: 30, 0.45: 30, 0.50: 30,
        0.55: 40, 0.59: 40, 0.63: 40, 0.67: 40, 0.71: 50,
        0.74: 50, 0.77: 50, 0.81: 50
    },
    "control_valve_100": {
        0.22: 20, 0.32: 20, 0.39: 20, 0.45: 20, 0.50: 30,
        0.55: 30, 0.59: 30, 0.63: 30, 0.67: 30, 0.71: 30,
        0.74: 40, 0.77: 40, 0.81: 40
    },
    "control_reg_valve_025": {
        0.22: 20, 0.32: 25, 0.39: 25, 0.45: 30, 0.50: 35,
        0.55: 35, 0.59: 40, 0.63: 45, 0.67: 45, 0.71: 45,
        0.74: 50, 0.77: 50, 0.81: 50
    },
    "control_reg_valve_050": {
        0.22: 15, 0.32: 20, 0.39: 20, 0.45: 25, 0.50: 25,
        0.55: 30, 0.59: 30, 0.63: 35, 0.67: 35, 0.71: 35,
        0.74: 40, 0.77: 40, 0.81: 40
    },
    "control_reg_valve_075": {
        0.22: 15, 0.32: 15, 0.39: 15, 0.45: 20, 0.50: 20,
        0.55: 25, 0.59: 25, 0.63: 25, 0.67: 30, 0.71: 30,
        0.74: 30, 0.77: 30, 0.81: 35
    },
    "control_reg_valve_100": {
        0.22: 15, 0.32: 15, 0.39: 15, 0.45: 15, 0.50: 20,
        0.55: 20, 0.59: 20, 0.63: 20, 0.67: 25, 0.71: 29,
        0.74: 35, 0.77: 40, 0.81: 46
    },
    "control_damper": {
        0.22: 30, 0.32: 30, 0.39: 35, 0.45: 35, 0.50: 40,
        0.55: 40, 0.59: 40, 0.63: 40, 0.67: 40, 0.71: 45,
        0.74: 45, 0.77: 50, 0.81: 50
    },
    "elbow_or_tee": {
        0.22: 30, 0.32: 30, 0.39: 40, 0.45: 30, 0.50: 30,
        0.55: 40, 0.59: 40, 0.63: 40, 0.67: 40, 0.71: 50,
        0.74: 50, 0.77: 50, 0.81: 50
    },

    # Таблица 7
    "swirler_30": {
        0.22: 60, 0.32: 60, 0.39: 70, 0.45: 70, 0.50: 70,
        0.55: 80, 0.59: 80, 0.63: 80, 0.67: 80, 0.71: 90,
        0.74: 90, 0.77: 90, 0.81: 90
    },
    "swirler_45": {
        0.22: 70, 0.32: 70, 0.39: 80, 0.45: 80, 0.50: 80,
        0.55: 90, 0.59: 90, 0.63: 90, 0.67: 90, 0.71: 90,
        0.74: 100, 0.77: 100, 0.81: 100
    },
    "swirler_60": {
        0.22: 60, 0.32: 70, 0.39: 70, 0.45: 80, 0.50: 80,
        0.55: 90, 0.59: 90, 0.63: 100, 0.67: 100, 0.71: 100,
        0.74: 100, 0.77: 110, 0.81: 110
    },
    "orifice_beta_025": {
        0.22: 15, 0.32: 15, 0.39: 15, 0.45: 15, 0.50: 20,
        0.55: 20, 0.59: 22, 0.63: 24, 0.67: 27, 0.71: 31,
        0.74: 37, 0.77: 45, 0.81: 54
    },
    "sudden_expansion": {
        0.22: 60, 0.32: 60, 0.39: 60, 0.45: 70, 0.50: 70,
        0.55: 70, 0.59: 80, 0.63: 80, 0.67: 80, 0.71: 80,
        0.74: 80, 0.77: 90, 0.81: 90
    },
    "diffuser_30_55": {
        0.22: 16, 0.32: 16, 0.39: 16, 0.45: 17, 0.50: 18,
        0.55: 20, 0.59: 22, 0.63: 24, 0.67: 27, 0.71: 29,
        0.74: 35, 0.77: 45, 0.81: 54
    },
    "convergent_reducer": {
        0.22: 5, 0.32: 5, 0.39: 5, 0.45: 5, 0.50: 6,
        0.55: 8, 0.59: 9, 0.63: 10, 0.67: 13, 0.71: 15,
        0.74: 20, 0.77: 25, 0.81: 30
    },

    "unknown_local_resistance": {
        0.00: 68, 0.32: 73, 0.45: 79,
        0.55: 86, 0.63: 92, 0.71: 100,
        0.77: 110
    }
}


def get_length_after_ssu(beta: float, prefer_ceiling: bool = False) -> float:
    # betas = np.array(sorted(LENGTH_AFTER_SSU.keys()))
    # lengths = np.array([LENGTH_AFTER_SSU[b] for b in betas])
    # return float(np.interp(beta, betas, lengths))
    #todo сделал до верхнего ближайшего большего значения
    table = LENGTH_AFTER_SSU
    keys = sorted(table.keys())
    if beta in table:
        return table[beta]

    if prefer_ceiling:
        for b in keys:
            if beta < b:
                return table[b]
        return table[keys[-1]]

    import numpy as np
    betas = np.array(keys)
    lengths = np.array([table[b] for b in betas])
    return float(np.interp(beta, betas, lengths))


def get_relative_roughness(beta: float) -> float:
    betas = np.array(sorted(RELATIVE_ROUGHNESS_TABLE.keys()))
    roughness = np.array([RELATIVE_ROUGHNESS_TABLE[b] for b in betas])
    return float(np.interp(beta, betas, roughness))


def get_wedge_length(ms_type: str) -> float:
    return WEDGE_STRAIGHT_LENGTHS.get(ms_type)


def get_cone_length(beta: float, ms_type: str) -> float:
    for (b_min, b_max), values in CONE_STRAIGHT_LENGTHS.items():
        if b_min <= beta <= b_max:
            return values.get(ms_type)
    return None


def get_unknown_ms_length(beta: float) -> float:
    # betas = np.array(sorted(UNKNOWN_MS_LENGTHS.keys()))
    # values = np.array([UNKNOWN_MS_LENGTHS[b] for b in betas])
    # return float(np.interp(beta, betas, values))
    """
    Изменение не по табл, а просто формула
    """
    length = (133.46 * beta**2 - 16.95 * beta + 67.81)
    return length


import bisect
def get_generic_ms_length(beta: float, ms_type: str) -> float:
    if ms_type in GENERIC_MS_LENGTHS:
        table = GENERIC_MS_LENGTHS[ms_type]
        betas = sorted(table.keys())
        # индекс первого элемента ≥ beta
        idx = bisect.bisect_left(betas, beta)
        # если β больше всех ключей, берём максимальный
        if idx >= len(betas):
            idx = len(betas) - 1
        selected_beta = betas[idx]
        return float(table[selected_beta])

    log.warning(f"Неизвестный тип МС: {ms_type} — используем значение из таблицы 8")
    return get_unknown_ms_length(beta)

def get_min_between_ms_length(ms1_type: str, ms2_type: str) -> float:
    l1 = BETWEEN_MS_LENGTHS.get(ms1_type, 0)
    l2 = BETWEEN_MS_LENGTHS.get(ms2_type, 0)
    return min(l1, l2)
