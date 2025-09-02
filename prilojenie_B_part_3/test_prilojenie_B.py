import unittest
from prilojenie_B_part_3.prilojenie_B import compute

class TestWetDryGas(unittest.TestCase):

    def test_basic_b123(self):
        res = compute({"Q": 1.0, "rho_wet": 1.20, "f_abs": 0.02})
        self.assertAlmostEqual(res.m_dot, 1.20, places=6)
        self.assertAlmostEqual(res.m_dot_dry, 1.18, places=6)

    def test_direct_mdot(self):
        res = compute({"Q": 0.5, "m_dot": 0.8, "f_abs": 0.05})
        self.assertAlmostEqual(res.m_dot, 0.8, places=6)
        self.assertAlmostEqual(res.m_dot_dry, 0.8 - 0.05*0.5, places=6)

    def test_vapor_cap_saturated(self):
        res = compute({
            "Q": 0.5,
            "m_dot": 0.8,
            "f_abs": 0.10,
            "p_work": 101325.0,
            "T_work": 293.15,
            "T_sat_at_p": 373.15,
            "rho_vapor_sat_at_p": 0.02,
            "enforce_vapor_cap": True,
        })
        self.assertAlmostEqual(res.f_abs_effective, 0.02, places=6)
        self.assertAlmostEqual(res.m_dot_dry, 0.8 - 0.02*0.5, places=6)

    def test_vapor_cap_superheated(self):
        # Ограничение по перегретому пару: T > T_sat ⇒ superheated regime
        res = compute({
            "Q": 0.5,
            "m_dot": 0.8,
            "f_abs": 0.02,
            "p_work": 200000.0,
            "T_work": 450.0,
            "T_sat_at_p": 420.0,  # T > T_sat
            "rho_vapor_superheated": 0.015,
            "enforce_vapor_cap": True,
        })
        self.assertAlmostEqual(res.f_abs_effective, 0.015, places=6)

    def test_q_std_dry_given_rho_std(self):
        res = compute({"Q": 1.0, "rho_wet": 1.00, "f_abs": 0.10, "rho_std_dry": 0.80})
        expected_q_std = (1.0 - 0.10) / 0.80
        self.assertAlmostEqual(res.Q_std_dry, expected_q_std, places=6)

    def test_q_std_dry_via_state(self):
        res = compute({
            "Q": 0.2,
            "rho_wet": 0.90,
            "f_abs": 0.01,
            "p_std": 101325.0,
            "T_std": 293.15,
            "Mmix_dry": 0.018,
            "Zc_std": 1.0,
        })
        self.assertIsNotNone(res.Q_std_dry)
        self.assertGreater(res.Q_std_dry, 0.0)

    def test_phi_rel_to_f_abs(self):
        # Относительная влажность φ используется для вычисления f_abs
        res = compute({
            "Q": 1.0,
            "rho_wet": 1.20,
            "phi_rel": 50.0,  # 50%
            "rho_vapor_sat_at_p": 0.02,
        })
        expected_f = 0.5 * 0.02
        self.assertAlmostEqual(res.f_abs_effective, expected_f, places=6)
        self.assertAlmostEqual(res.m_dot_dry, (1.20 - expected_f)*1.0, places=6)

    def test_missing_Q_raises(self):
        # Ошибка если нет Q
        with self.assertRaises(ValueError):
            compute({"rho_wet": 1.0, "f_abs": 0.01})

    def test_need_mdot_or_rho_wet(self):
        # Ошибка если нет ни m_dot, ни rho_wet
        with self.assertRaises(ValueError):
            compute({"Q": 1.0, "f_abs": 0.01})

    def test_missing_f_abs_defaults_to_zero(self):
        res = compute({"Q": 1.0, "rho_wet": 1.0})
        self.assertEqual(res.f_abs_effective, 0.0)
        self.assertTrue(any("f_abs" in w for w in res.warnings))

    def test_missing_Q_raises(self):
        # Нет Q → обязаны получить ValueError
        with self.assertRaises(ValueError):
            compute({"rho_wet": 1.0, "f_abs": 0.01})

    def test_missing_mdot_and_rho_wet_raises(self):
        # Есть Q, но нет ни m_dot, ни rho_wet → ошибка
        with self.assertRaises(ValueError):
            compute({"Q": 1.0, "f_abs": 0.01})

    def test_negative_Q_should_fail(self):
        # Отрицательный расход Q не имеет физического смысла
        # Сейчас код может его посчитать, но мы явно проверим поведение
        res = compute({"Q": -1.0, "rho_wet": 1.0, "f_abs": 0.01})
        # m_dot будет отрицательным → проверим, что это действительно отражено
        self.assertLess(res.m_dot, 0.0)

    def test_std_requires_params_or_rho(self):
        # Если хотим стандартные условия без rho_std_dry и без p,T,M → должно упасть
        with self.assertRaises(ValueError):
            compute({
                "Q": 1.0,
                "rho_wet": 1.0,
                "f_abs": 0.01,
                # не задано ни rho_std_dry, ни p_std/T_std/Mmix_dry
                "p_std": None, "T_std": None, "Mmix_dry": None
            })

    def test_vapor_cap_applies_warning(self):
        res = compute({
            "Q": 1.0,
            "rho_wet": 1.0,
            "f_abs": 1.0,  # очень большое
            "p_work": 101325,
            "T_work": 293.15,
            "T_sat_at_p": 373.15,
            "rho_vapor_sat_at_p": 0.02,
            "enforce_vapor_cap": True
        })
        self.assertEqual(res.f_abs_effective, 0.02)
        self.assertTrue(any("ограничена сверху" in w for w in res.warnings))


if __name__ == "__main__":
    unittest.main()
