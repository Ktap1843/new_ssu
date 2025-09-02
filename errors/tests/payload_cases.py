from __future__ import annotations

# БАЗОВЫЙ БОЛЬШОЙ ПАКЕТ (можно редактировать/дополнять)
BIG_PAYLOAD = {
    "data": {
        "compositionErrorPackage": {
            "composition": {
                "CarbonDioxide": 2.5,
                "Ethane": 6,
                "Helium": 0.015,
                "Hydrogen": 0.005,
                "Methane": 87.535,
                "Nitrogen": 1,
                "Oxygen": 0.05,
                "Propane": 2,
                "iButane": 0.5,
                "iPentane": 0.045,
                "nButane": 0.3,
                "nPentane": 0.05
            },
            "error_composition": {
                "CarbonDioxide": {"complError": {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}}},
                "Ethane":        {"complError": {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId": "AbsErr","value":{"real":0,"unit":"percent"}}},
                "Helium":        {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.015,"min":0.005},"unit":"percent"}}},
                "Hydrogen":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.005,"min":0.001},"unit":"percent"}}},
                "Methane":       {"complError": {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}}},
                "Nitrogen":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":1,"min":0.2},"unit":"percent"}}},
                "Oxygen":        {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.05,"min":0.005},"unit":"percent"}}},
                "Propane":       {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":2,"min":0.5},"unit":"percent"}}},
                "iButane":       {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.5,"min":0.1},"unit":"percent"}}},
                "iPentane":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.045,"min":0.018},"unit":"percent"}}},
                "nButane":       {"complError": {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}},
                                  "intrError":  {"errorTypeId":"AbsErr","value":{"real":0,"unit":"percent"}}},
                "nPentane":      {"complError": None,
                                  "intrError":  {"errorTypeId":"UppErr","range":{"range":{"max":0.05,"min":0.01},"unit":"percent"}}},
            },
            "request": None
        },
        "errorPackage": {
            "errors": {
                "absPressureErrorProState": {
                    "errorInputMethod": "ByValue",
                    "intrError": {"errorTypeId":"RelErr","value":{"real":0.5,"unit":"percent"}},
                    "complError":{"errorTypeId":"RelErr","value":{"real":0.2,"unit":"percent"}},
                    "measInstRange":{"range":{"min":0.0,"max":2.5},"unit":"MPa"},
                    "converter1IntrError":{"errorTypeId":"RelErr","value":{"real":0.10,"unit":"percent"}},
                    "converter1ComplError":{"errorTypeId":"RelErr","value":{"real":0.10,"unit":"percent"}},
                    "converter2IntrError":{"errorTypeId":"RelErr","value":{"real":0.10,"unit":"percent"}},
                    "options":{"conv2_func":"quadratic"}
                },
                "temperatureErrorProState": {
                    "errorInputMethod": "ByValue",
                    "intrError": {"errorTypeId":"RelErr","value":{"real":0.3,"unit":"percent"}},
                    "complError":{"errorTypeId":"RelErr","value":{"real":0.1,"unit":"percent"}},
                    "measInstRange":{"range":{"min":-40,"max":60},"unit":"C"},
                    "converter1IntrError":{"errorTypeId":"RelErr","value":{"real":0.20,"unit":"percent"}},
                    "converter1ComplError":{"errorTypeId":"RelErr","value":{"real":0.10,"unit":"percent"}}
                },
                "stDensityErrorProState": {
                    "intrError": {"errorTypeId":"RelErr","value":{"real":0.6,"unit":"percent"}},
                    "complError":{"errorTypeId":"RelErr","value":{"real":0.2,"unit":"percent"}},
                    "converter1IntrError":{"errorTypeId":"RelErr","value":{"real":0.4,"unit":"percent"}},
                    "converter1ComplError":{"errorTypeId":"RelErr","value":{"real":0.3,"unit":"percent"}},
                    "converter2IntrError":{"errorTypeId":"RelErr","value":{"real":0.2,"unit":"percent"}},
                    "options":{"conv2_func":"quadratic"}
                }
            },
            "hasToCalcErrors": True
        },
        "physPackage": {
            "physProperties": {
                "T": {"real": -23.15, "unit": "C"},
                "p_abs": {"real": 2.1, "unit": "MPa"},
                "rho_st": {"real": 0.73, "unit": "kg_m3"}
            },
            "requestList": []
        }
    }
}

CASE_WITH_OVERRIDES = {
    **BIG_PAYLOAD,
    "data": {
        **BIG_PAYLOAD["data"],
        "compositionErrorPackage": {
            **BIG_PAYLOAD["data"]["compositionErrorPackage"],
        }
    }
}

# Регистр кейсов: имя -> payload (или callable, возвращающий payload)
CASES = {
    "default": lambda: BIG_PAYLOAD,             # по умолчанию
    "with_overrides": lambda: CASE_WITH_OVERRIDES,
}
