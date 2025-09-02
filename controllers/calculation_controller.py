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

    def _create_orifice(self) -> None:
        log.info("Создание ССУ")

    from orifices_classes.main import create_orifice, OrificeType
    from orifices_classes.materials import calc_alpha

    # Аргументы для конструктора ССУ (холодные размеры при 20°C)
    typ = OrificeType((self.cp.get("type") or "sharp"))
    # Re берём из состояния, если нет — минимально допустимый для класса
    Re_val = getattr(getattr(self, "flow_state", None), "Re", None) or 1.0e5

    or_args = {
        "D": self.params.D,
        "d": self.params.d,
        "Re": Re_val,
    }
    # Типоспецифичные параметры, если есть во входе
    for k in ("alpha", "e", "Ed", "dk", "beta"):
        if k in self.cp and self.cp[k] is not None:
            or_args[k] = self.cp[k]

    # 1) Создание БЕЗ валидации
    self.orifice = create_orifice(typ, do_validate=False, **or_args)

    # 2) Термокоррекция геометрии на рабочую T
    d20_steel = self.cp.get("d20_steel") or "20"
    D20_steel = self.cp.get("D20_steel") or "20"
    alpha_CCU = calc_alpha(d20_steel, self.ep["T"])  # для d
    alpha_T = calc_alpha(D20_steel, self.ep["T"])  # для D

    self.orifice.update_geometry_from_temp(
        d_20=self.params.d,
        D_20=self.params.D,
        alpha_CCU=alpha_CCU,
        alpha_T=alpha_T,
        t=self.ep["T"],
    )

    # 3) Валидация УЖЕ после термокоррекции
    if not self.orifice.validate():
        raise ValueError(f"Валидация геометрии ССУ '{typ.value}' не пройдена")

    # 4) Проверка шероховатости
    Ra_um = self.cp.get("Ra")
    if Ra_um is not None:
        self.valid_rough = self.orifice.validate_roughness(Ra_um / 1000.0)
    else:
        self.valid_rough = True

    # 5) Полный расчёт параметров ССУ
    self.ssu_res = self.orifice.run_all(
        delta_p=self.params.dp,
        p=self.ep["p"],
        k=self.pp.get("k"),
        Ra=(Ra_um / 1000.0) if Ra_um is not None else None,
        alpha=self.cp.get("alpha"),
    )

    log.debug("SSU результат: %s", self.ssu_res)

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
