import unittest
from copy import deepcopy

from errors.handle import process_package
from errors.ivk_branch import apply_ivk_branch

class TestIVKBranch(unittest.TestCase):
    def test_ivk_geometric_sum(self):
        payload = {
            "data": {
                "errorPackage": {
                    "errors": {
                        "ivkProState": {
                            "complError": {"errorTypeId": "RelErr", "value": {"real": 0.5, "unit": "percent"}},
                            "intrError":  {"errorTypeId": "RelErr", "value": {"real": 1.0, "unit": "percent"}}
                        }
                    }
                }
            }
        }
        out = apply_ivk_branch(deepcopy(payload))
        err = out["data"]["errorPackage"]["errors"]["error_ivk"]["value"]["real"]
        print(out)
        self.assertAlmostEqual(err, 1.1180339887, places=6)
        self.assertTrue(out["data"]["errorPackage"]["errors"]["has_ivk_priority"])

    def test_process_package_respects_ivk(self):
        payload = {
            "data": {
                "errorPackage": {
                    "errors": {
                        "ivkProState": {
                            "complError": {"errorTypeId": "RelErr", "value": {"real": 0.3, "unit": "percent"}},
                            "intrError":  {"errorTypeId": "RelErr", "value": {"real": 0.4, "unit": "percent"}}
                        }
                    }
                }
            }
        }
        out = process_package(deepcopy(payload))
        total = out["diagnostics"]["total_error"]
        print(out)
        self.assertEqual(total["source"], "IVK")
        self.assertAlmostEqual(total["value_percent"], 0.5, places=6)

    def test_abs_error_conversion_needs_base(self):
        payload = {
            "data": {
                "errorPackage": {
                    "errors": {
                        "ivkProState": {
                            "complError": {"errorTypeId": "RelErr", "value": {"real": 2.0, "unit": "units"}},
                            "intrError":  {"errorTypeId": "RelErr", "value": {"real": 1.0, "unit": "percent"}}
                        }
                    }
                }
            }
        }
        out = process_package(deepcopy(payload))
        print(out)
        self.assertAlmostEqual(out["diagnostics"]["total_error"]["value_percent"], 2.2360679, places=6)

    def test_abs_error_with_base(self):
        payload = {
            "data": {
                "errorPackage": {
                    "errors": {
                        "ivkProState": {
                            "quantityValue": {"real": 50.0, "unit": "m3_h"},
                            "complError": {"errorTypeId": "RelErr", "value": {"real": 0.25, "unit": "percent"}},
                            "intrError":  {"errorTypeId": "RelErr", "value": {"real": 0.6, "unit": "percent"}}
                        }
                    }
                }
            }
        }
        out = process_package(deepcopy(payload))
        print(out)
        self.assertAlmostEqual(out["diagnostics"]["total_error"]["value_percent"], 1.166190378, places=6)

if __name__ == "__main__":
    unittest.main()
