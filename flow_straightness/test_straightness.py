from flow_straightness.straightness_calculator import CalcStraightness
from logger_config import get_logger

log = get_logger("StraightnessTestRunner")

test_cases = [
    {
        "title": "1.isoqpms",
        "input": {
            "ssu_type": "sharp",
            "beta": 0.4081632653061224,
            "D": 0.049,             #TODO <---  диаметр после умножения на температурный коэфф?
            "Ra": 0.00003,
            "ms_before": [
                {"type": "elbows_same_plane"},
                {"type": "tee"}
            ],
            "ms_after": [],
            "skip": False
        }
    },
    {
        "title": "2.isoqpms",
        "input": {
            "ssu_type": "sharp",
            "beta": 0.4081632653061224,
            "D": 0.049,
            "Ra": 0.00003,
            "ms_before": [
                {"type": "gate_valve"},
                {"type": "control_valve_025"}
            ],
            "ms_after": [],
            "skip": False
        }
    },
    {
        "title": "3.isoqpms",
        "input": {
            "ssu_type": "sharp",
            "beta": 0.375,
            "D": 0.048,
            "Ra": 0.00003,
            "ms_before": [
                {"type": "swirler_60"},
                {"type": "control_damper"}
            ],
            "ms_after": [
                {"type": "thermowell_003D_013D"}
            ],
            "skip": False
        }
     },
     {
         "title": "4.isoqpms",
         "input": {
             "ssu_type": "sharp",
             "beta": 0.375,
             "D": 0.048,
            "Ra": 0.00003,
             "ms_before": [
                 {"type": "stop_valve"},
                 {"type": "convergent_reducer"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "5.isoqpms",
         "input": {
             "ssu_type": "sharp",
             "beta": 0.375,
             "D": 0.048,
            "Ra": 0.00003,
             "ms_before": [
                 {"type": "swirler_60"},
                 {"type": "swirler_45"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "6.isoqpms",
         "input": {
             "ssu_type": "double",
             "beta": 0.5,
             "D": 0.048,
            "Ra": 0.00003,
             "ms_before": [
                 {"type": "elbows_different_planes"},
                 {"type": "control_damper"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "7.isoqpms",
         "input": {
             "ssu_type": "double",
             "beta": 0.5,
             "D": 0.048,
            "Ra": 0.00003,
             "ms_before": [
                 {"type": "orifice_beta_025"},
                 {"type": "expansion_1_2_to_1_4"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "8.isoqpms",
         "input": {
             "ssu_type": "segment",
             "beta": 0.5,
             "D": 0.15,
            "Ra": 0.00003,
             "ms_before": [
                 {"type": "convergent_reducer"},
                 {"type": "control_reg_valve_100"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "9.isoqpms",
         "input": {
             "ssu_type": "segment",
             "beta": 0.5,
             "D": 0.15,
             "Ra": 0.00003,
             "ms_before": [
                 {"type": "elbows_same_plane"},
                 {"type": "cock"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "10.isoqpms",
         "input": {
             "ssu_type": "wear_resistant",
             "beta": 0.5003335557038025,
             "D": 0.1499,
             "Ra": 0.00003,
             "ms_before": [
                 {"type": "elbows_different_planes"},
                 {"type": "tee"}
             ],
             "ms_after": [
                    {"type": "thermowell_003D_013D"}
             ],
             "skip": False
         }
     },
     {
         "title": "11.isoqpms",
         "input": {
             "ssu_type": "wear_resistant",
             "beta": 0.3,
             "D": 0.5,
             "Ra": 0.00003,
             "ms_before": [
                 {"type": "control_valve_100"},
                 {"type": "elbows_different_planes"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
     {
         "title": "12.isoqpms",
         "input": {
             "ssu_type": "wear_resistant",
             "beta": 0.5,
             "D": 0.1,
             "Ra": 0.00003,
             "ms_before": [
                 {"type": "unknown_ms_1"},
                 {"type": "unknown_ms_2"}
             ],
             "ms_after": [],
             "skip": False
         }
     },
 {
     "title": "13.isoqpms",
     "input": {
         "ssu_type": "wear_resistant",
         "beta": 0.6,
         "D": 0.1,
         "Ra": 0.00003,
         "ms_before": [
             {"type": "90_degree_elbow"},
             {"type": "tee_straight"}
         ],
         "ms_after": [
             {"type": "cock"}
         ],
         "skip": False
     }
 },
 {
     "title": "14.isoqpms",
     "input": {
         "ssu_type": "wear_resistant",
         "beta": 0.55,
         "D": 0.12,
         "Ra": 0.00003,
         "ms_before": [
             {"type": "shutoff_valve"},
             {"type": "gate_valve"}
         ],
         "ms_after": [
             {"type": "elbow_90"}
         ],
         "skip": False
     }
 },
 {
     "title": "15.isoqpms",
     "input": {
         "ssu_type": "wear_resistant",
         "beta": 0.45,
         "D": 0.08,
         "Ra": 0.00003,
         "ms_before": [
             {"type": "ball_valve"},
             {"type": "thermowell_003D_to_013D"}
         ],
         "ms_after": [
             {"type": "stop_valve"}
         ],
         "skip": False
     }
 },
 {
     "title": "16.isoqpms",
     "input": {
         "ssu_type": "cone",
         "beta": 0.5,
         "D": 0.1,
         "Ra": 0.00003,
         "ms_before": [
             {"type": "cock"},
             {"type": "tee"}
         ],
         "ms_after": [
             {"type": "unknown_valve"}
         ],
         "skip": False
     }
 },
 {
     "title": "17.isoqpms",
     "input": {
         "ssu_type": "wedge",
         "beta": 0.5,
         "D": 0.1,
         "Ra": 0.00003,
         "ms_before": [
             {"type": "123"},
             {"type": "987"}
         ],
         "ms_after": [
             {"type": "thermowell_003D_013D"}
         ],
         "skip": False
     }
 },
{
    "title": "18.isoqpms",
    "input": {
        "ssu_type": "wedge",
        "beta": 0.5,
        "D": 0.150,
        "Ra": 0.00003,
        "ms_before": [
            {"type": "shutoff_valve"},
            {"type": "elbow_90"}
        ],
        "ms_after": [
            {"type": "thermowell_003D_013D"}
        ],
        "skip": False
    }
},
{
    "title": "19.isoqpms",
    "input": {
        "ssu_type": "wedge",
        "beta": 0.5,
        "D": 0.150,
        "Ra": 0.00003,
        "ms_before": [
            {"type": "1"},
            {"type": "2"}
        ],
        "ms_after": [
            {"type": "smth"}
        ],
        "skip": False
    }
},
{
    "title": "20.isoqpms",
    "input": {
        "ssu_type": "sharp",
        "beta": 0.5,
        "D": 0.150,
        "Ra": 0.00003,
        "ms_before": [
            {"type": "1"}
        ],
        "ms_after": [
            {"type": "smth"}
        ],
        "skip": False
    }
},
]

def run_tests():
    for case in test_cases:
        data = case["input"]
        log.info(f"--- {case['title']} ---")
        log.debug(f"Input: beta={data['beta']}, D={data['D']}, Ra={data['Ra']}, type={data['ssu_type']}")
        calc = CalcStraightness(**data)
        result = calc.calculate()
        log.info(f"Result: {result}\n")

if __name__ == "__main__":
    run_tests()
