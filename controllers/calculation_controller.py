import math
from orifices_classes.main import create_orifice, OrificeType
from orifices_classes.materials import calc_alpha
from calc_flow.calcflow import CalcFlow
from phys_prop.calc_phys_prop import CalcFizika
from flow_straightness.straightness_calculator import CalcStraightness
from logger_config import get_logger

log = get_logger("CalculationController")


class CalculationController:
    def __init__(self, data: dict, prepared_params):
        self.data = data
        self.cp = data["flowdata"]["constrictor_params"]
        self.ep = data["flowdata"]["environment_parameters"]
        self.pp = data["flowdata"]["physical_properties"]
        self.cs = data["flowdata"]["straightness_params"]
        self.params = prepared_params

    def run_calculations(self) -> dict:
        log.info("Запуск расчёта")
        self._calculate_physics()
        self._create_orifice()
        self._calculate_flow()
        self._calculate_straightness()

        return {
            "valid_roughness": self.valid_rough,
            "ssu_results": self.ssu_res,
            "flow_results": self.flow_res,
            "straightness_result": self.straightness_result
        }

    def _calculate_physics(self):
        log.info("Расчёт физ. свойств")
        fizika = CalcFizika(self.data)
        self.Z = fizika.Z
        self.Z_st = fizika.Z_st      # TODO <---- тут добавил физ-сва, переменные для расхода и погрешности
        self.z_err = fizika.z_error
        self.z_st_err = fizika.z_st_error
        log.debug(f"Z={self.Z}, Z_st={self.Z_st}, z_err={self.z_err}, z_st_err={self.z_st_err}")

    def _create_orifice(self):
        log.info("Создание ССУ")
        Re = self.pp["Ro"] * math.sqrt(2 * self.ep["dp"] / self.pp["Ro"]) * self.params.D / (self.pp["mu"] / 1e6)
        alpha_CCU = calc_alpha(self.cp["d20_steel"], self.ep["T"])
        alpha_T = calc_alpha(self.cp["D20_steel"], self.ep["T"])

        or_args = {
            "D": self.params.D,
            "d": self.params.d,
            "h": self.cp.get("h", 0) / 1000,    # TODO после изменения Prepare_controller, тут тоже внести изменения
            "d1": self.cp.get("d1", 0) / 1000,
            "d2": self.cp.get("d2", 0) / 1000,
            "d_k": self.cp.get("d_k", 0) / 1000,
            "Re": Re,
            "p": self.ep["p"],
            "p1": self.ep["p"],
            "Ra": self.cp.get("Ra", 0) / 1000,
            "alpha": self.cp.get("alpha", None),
            "k": self.pp["k"]
        }

        typ = OrificeType(self.cp.get("type", OrificeType.SHARP).lower())
        self.orifice = create_orifice(typ, **or_args)
        self.orifice.update_geometry_from_temp(self.params.d, self.params.D, alpha_CCU, alpha_T, self.ep["T"])

        self.valid_rough = self.orifice.validate_roughness(self.cp["Ra"] / 1000)
        self.ssu_res = self.orifice.run_all(
            delta_p=self.params.dp,
            p=self.ep["p"],
            k=self.pp["k"],
            Ra=self.cp.get("Ra") / 1000,
            alpha=self.cp.get("alpha")
        )
        log.debug(f"SSU результат: {self.ssu_res}")

    def _calculate_flow(self):
        log.info("Расчёт расхода")
        cf = CalcFlow(
            orifice=self.orifice,
            d=self.params.d,
            D=self.params.D,
            p1=self.params.p1,
            t1=self.params.t1,
            delta_p=self.params.dp,
            mu=self.pp["mu"] / 1e6,
            Roc=self.pp["Roc"],
            Ro=self.pp["Ro"],
            k=self.pp["k"]
        )

        cf.beta = self.ssu_res["beta"]
        cf.C = self.ssu_res["C"]
        cf.epsilon = self.ssu_res["Epsilon"]
        cf.E = self.ssu_res["E_speed"]

        self.flow_res = cf.run_all()
        log.debug(f"Результат расчёта расхода: {self.flow_res}")

    def _calculate_straightness(self):
        log.info("Расчёт длин прямолинейных участков")
        cs = CalcStraightness(  # TODO проверить все параметры для всех ССУ во всех вариантах
            ssu_type=self.cp["type"].lower(),  # TODO тесты функций контроллера добавить
            beta=self.ssu_res["beta"],
            D=self.params.D,
            ms_before=self.cs.get("ms_before", []),
            ms_after=self.cs.get("ms_after", []),
            skip=self.cs.get("skip", False)
        )

        self.straightness_result = cs.calculate()
        log.debug(f"Прямолинейные участки: {self.straightness_result}")
