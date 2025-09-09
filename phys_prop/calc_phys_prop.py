from PyFizika import calc_phys_properties_from_requestList
from phys_prop_exceptions import ValidationError
from logger_config import get_logger

#todo осталось закинуть физику и можно делать контролньые примеры для состава

class CalcFizika:
    def __init__(self, data: dict):
        self.logger = get_logger(self.__class__.__name__)
        self.data = data
        if self.data['physPackage']['requestList'] == []:
        self.combined_phys_properties: dict = {}

        self.Z = None
        self.Z_st = None
        self.z_error = None
        self.z_st_error = None

        self.Ro = None
        self.Roc = None
        self.mu = None
        self.k = None
        self.Ro_error = None
        self.Roc_error = None
        self.mu_error = None
        self.k_error = None

        self._calc_phys_prp()

    def _calc_phys_prp(self) -> None:
        try:
            request_list = self.data['physPackage']['requestList']
            input_properties = self.data['physPackage']['physProperties']
        except KeyError as e:
            raise ValidationError(f"Отсутствует обязательное поле: {e}", __package__)

        try:
            phys_properties = calc_phys_properties_from_requestList(request_list, input_properties)
        except Exception as e:
            raise ValidationError(f"Ошибка при вызове PyFizika: {e}", __package__)

        for d in phys_properties:
            if d.get('phase') != 'gas':
                raise ValidationError('Фаза не газ', __package__)
            self.combined_phys_properties.update(d)

        self.Z = self.get("z")
        self.Z_st = self.get("z_st")
        self.z_error = self.get("error_z")
        self.z_st_error = self.get("error_z_st")

        self.Ro = self.get("rho")
        self.Roc = self.get("rho_st")
        self.mu = self.get("mu")
        self.k = self.get("k")

        self.Ro_error = self.get("error_rho")
        self.Roc_error = self.get("error_rho_st")
        self.mu_error = self.get("error_mu")
        self.k_error = self.get("error_k")

    def get(self, key):
        return self.combined_phys_properties.get(key)

    def to_dict(self):
        result = {
            "Z": self.Z,
            "Z_st": self.Z_st,
            "z_error": self.z_error,
            "z_st_error": self.z_st_error,
            "Ro": self.Ro,
            "Roc": self.Roc,
            "mu": self.mu,
            "k": self.k,
            "Ro_error": self.Ro_error,
            "Roc_error": self.Roc_error,
            "mu_error": self.mu_error,
            "k_error": self.k_error
        }

        for key, value in result.items():
            if value is None:
                self.logger.warning(f"'{key}'== None")

        return result


#todo сделать проверку phys_props -- если requestlist = []. то прост беерем значения из переменных!
#todo +++++++
#todo добавить сразу состав и весь список из физ пакаге + поменять input params


ducis = {"physPackage": {
            "physProperties": {
                "K": None,
                "T": {
                    "real": 20,
                    "unit": "C"
                },
                "T_phi": None,
                "T_st": {
                    "real": 20,
                    "unit": "C"
                },
                "W": None,
                "Z": None,
                "Z_st": None,
                "composition": {
                    "CarbonDioxide": 0.25,
                    "Ethane": 5.7,
                    "Methane": 90,
                    "Nitrogen": 0.25,
                    "Propane": 3,
                    "iButane": 0.2,
                    "iPentane": 0.2,
                    "nButane": 0.2,
                    "nPentane": 0.2
                },
                "containsHydrogenSulfide": None,
                "error_K": None,
                "error_W": None,
                "error_Z": None,
                "error_Z_st": None,
                "error_k": None,
                "error_mu": None,
                "error_p_s": None,
                "error_rho": None,
                "error_rho_st": None,
                "humidityType": "RelativeHumidity",
                "k": None,
                "mu": None,
                "p_atm": {
                    "real": 760,
                    "unit": "mm_Hg"
                },
                "p_izb": {
                    "real": 0.8,
                    "unit": "MPa"
                },
                "p_abs": None,
                "p_phi": None,
                "p_s": None,
                "p_st": {
                    "real": 0.101325,
                    "unit": "MPa"
                },
                "phi": {
                    "real": 0,
                    "unit": "percent"
                },
                "rho": None,
                "rho_st": None
            },
            "requestList": [
                {
                    "documentId": "GOST_30319_3_2015",
                    "physValueId": "Z"
                },
                {
                    "documentId": "GOST_30319_3_2015",
                    "physValueId": "Z_st"
                }
            ]
        }}

if __name__ == "__main__":
    from pprint import pprint

    try:
        fiz = CalcFizika(ducis)
        out = fiz.to_dict()
        pprint(out, sort_dicts=False)
    except ValidationError as e:
        # в бою лучше логировать и прокидывать наверх
        print(f"[ValidationError] {e}")

