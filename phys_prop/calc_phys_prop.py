from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Tuple, Sequence, Callable
from importlib import import_module
import json

from PyFizika import calc_phys_properties_from_requestList
from phys_prop_exceptions import ValidationError
from logger_config import get_logger




# -------------------- утилиты --------------------

def _coalesce(d: Mapping[str, Any], keys: List[str]) -> Any:
    """Первое непустое значение по альтернативным ключам."""
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def _ensure_min_request_list(
    data: Mapping[str, Any],
    candidate: Optional[List[Mapping[str, Any]]],
    values: List[str],
    default_doc: str = "GOST_30319_3_2015",
) -> List[Mapping[str, Any]]:
    """
    Возвращает:
      - если candidate задан и не пуст — как есть (с твоим documentId),
      - иначе — соберёт requestList из values и default_doc.
    """
    if isinstance(candidate, list) and len(candidate) > 0:
        return candidate
    return [{"documentId": default_doc, "physValueId": v} for v in values]


# -------------------- минимальный раннер --------------------

class PhysMinimalRunner:
    """
    Минимальный раннер PyFizika под твои нужды:
      - тянет только rho, rho_st, k, mu (+ их ошибки)
      - умеет падать на поэлементные вызовы, если батч вернул errorString
      - опционально считает теты (rho/k по T и p_abs)
    """

    NEED_VALUES = ["rho", "rho_st", "k", "mu"]

    def __init__(
        self,
        data: Mapping[str, Any],
        request_list: Optional[List[Mapping[str, Any]]] = None,
        *,
        theta_request_list: Optional[List[Mapping[str, Any]]] = None,
        require_gas_phase: bool = True,
    ) -> None:
        self.log = get_logger(self.__class__.__name__)
        self.data = dict(data)
        self.theta_request_list = theta_request_list
        self.require_gas_phase = require_gas_phase

        # --- physPackage
        try:
            phys_pkg = self.data["physPackage"]
            self.input_props: Mapping[str, Any] = phys_pkg["physProperties"]
            given_request_list: Optional[List[Mapping[str, Any]]] = phys_pkg.get("requestList", None)
        except KeyError as e:
            raise ValidationError(f"Отсутствует обязательное поле: {e}", __package__)

        # Если явный request_list передан в конструктор — используем его.
        self.request_list: List[Mapping[str, Any]] = _ensure_min_request_list(
            self.data,
            request_list if request_list is not None else given_request_list,
            self.NEED_VALUES,
        )

        # Результаты
        self._phys_raw: List[Dict[str, Any]] = []
        self._phys_norm: Dict[str, Any] = {}
        self._thetas: Dict[str, float] = {}

        self._run_pyfizika_with_fallback()
        self._maybe_run_thetas()

    # -------------------- публичный API --------------------

    def to_dict(self) -> Dict[str, Any]:
        nd = self._phys_norm
        out = {
            # значения
            "ro": nd.get("rho"),
            "ro_st": nd.get("rho_st"),
            "k": nd.get("k"),
            "mu": nd.get("mu"),
            # ошибки
            "err_ro": nd.get("error_rho"),
            "err_ro_st": nd.get("error_rho_st"),
            "err_k": nd.get("error_k"),
            "err_mu": nd.get("error_mu"),
            # теты
            "thetas": self._thetas or None,
        }

        # Предупреждения — чтобы быстро видеть недостающие поля
        for k, v in out.items():
            if k == "thetas":
                continue
            if v is None:
                pass#self.log.warning("'%s' == None", k)

        return out

    def augment_result(self, result: Dict[str, Any], key: str = "phys") -> Dict[str, Any]:
        result[key] = self.to_dict()
        return result

    # -------------------- внутренности --------------------

    def _call_pyfizika(self, rlist: List[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Вызывает PyFizika и возвращает (list_of_dicts, error_str_if_any)."""
        try:
            res = calc_phys_properties_from_requestList(rlist, self.input_props)
            # PyFizika иногда возвращает errorString в dict/внутри списка dict'ов
            if isinstance(res, dict) and "errorString" in res:
                return [res], res.get("errorString")
            if isinstance(res, list) and any(isinstance(x, dict) and "errorString" in x for x in res):
                return list(res), "batch-error"
            return list(res), None
        except Exception as e:
            return [{"errorString": f"{e}"}], str(e)

    def _run_pyfizika_with_fallback(self) -> None:
        # 1) батч
        raw, err = self._call_pyfizika(self.request_list)

        # 2) если ошибка — по одному
        if err:
            self.log.warning("PyFizika batch вернула ошибку (%s). Перехожу на поэлементные вызовы.", err)
            merged: List[Dict[str, Any]] = []
            for req in self.request_list:
                single_raw, single_err = self._call_pyfizika([req])
                merged.extend(single_raw)
                if single_err:
                    self.log.warning("Пропускаю physValueId=%s: %s", req.get("physValueId"), single_err)
            raw = merged

        self._phys_raw = raw

        # Собираем только успешные значения
        combined: Dict[str, Any] = {}
        for d in (self._phys_raw or []):
            if not isinstance(d, Mapping) or "errorString" in d:
                continue
            phase = d.get("phase")
            if self.require_gas_phase and phase and phase != "gas":
                raise ValidationError("Фаза не газ", __package__)
            for k, v in d.items():
                if k == "phase":
                    continue
                combined[k] = v

        # Нормализация имён (варианты из твоего лога: Ro/Ro_st/error_Ro/…)
        self._phys_norm = {
            "rho":         _coalesce(combined, ["rho", "Ro"]),
            "rho_st":      _coalesce(combined, ["rho_st", "Ro_st"]),
            "k":           _coalesce(combined, ["k", "K"]),
            "mu":          _coalesce(combined, ["mu", "Mu"]),

            "error_rho":    _coalesce(combined, ["error_rho", "error_Ro"]),
            "error_rho_st": _coalesce(combined, ["error_rho_st", "error_Ro_st"]),
            "error_k":      _coalesce(combined, ["error_k", "k_error"]),
            "error_mu":     _coalesce(combined, ["error_mu", "mu_error"]),
        }

    def _maybe_run_thetas(self) -> None:
        self._thetas = {}
        if not self.theta_request_list:
            return
        try:
            stp_mod = import_module("stp_errors")
            calc_thetas = getattr(stp_mod, "calc_thetas_from_requestList", None)
            if not callable(calc_thetas):
                self.log.warning("Не найден stp_errors.calc_thetas_from_requestList — пропускаю расчёт thetas")
                return
            # как в твоём примере: calc_thetas_from_requestList(theta_list, **data)
            self._thetas = calc_thetas(self.theta_request_list, **self.data) or {}
        except Exception as e:
            self.log.warning("Ошибка при расчёте thetas: %s", e)


# -------------------- генераторы списков --------------------

def make_theta_list() -> List[Dict[str, str]]:
    """Теты по rho и k — по T и p_abs."""
    return [
        {"value": "rho", "variable": "T"},
        {"value": "rho", "variable": "p_abs"},
        {"value": "k",   "variable": "T"},
        {"value": "k",   "variable": "p_abs"},
    ]


# -------------------- удобная обёртка «целый словарь → минимальный словарь» --------------------

def run_phys_minimal(data: Mapping[str, Any]) -> Dict[str, Any]:
    """
    Принимает твой полный словарь (data),
    возвращает минимальный словарь с: ro, ro_st, k, mu, err_ro, err_ro_st, err_k, err_mu, thetas.
    """
    theta_list = make_theta_list()
    runner = PhysMinimalRunner(data, theta_request_list=theta_list)
    return runner.to_dict()


# -------------------- пример использования --------------------

if __name__ == "__main__":
    # Твой примерный «целый» словарь (оставь свой, документ — как укажешь в requestList)
    ducis = {
        "physPackage": {
            "physProperties": {
                "K": None,
                "T": {"real": 20, "unit": "C"},
                "T_phi": None,
                "T_st": {"real": 20, "unit": "C"},
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
                "k": 1.3,
                "mu": None,
                "p_atm": {"real": 760, "unit": "mm_Hg"},
                "p_izb": None,
                "p_abs": {"real": 2, "unit": "MPa"},
                "p_phi": None,
                "p_s": None,
                "p_st": {"real": 0.101325, "unit": "MPa"},
                "phi": {"real": 0, "unit": "percent"},
                "rho": None,
                "rho_st": None
            },
            "requestList": [
                {"documentId": "GOST_30319_3_2015", "physValueId": "rho"},
                {"documentId": "GOST_30319_3_2015", "physValueId": "rho_st"},
                {"documentId": "GOST_30319_3_2015", "physValueId": "k"},
                {"documentId": "GOST_30319_3_2015", "physValueId": "mu"},
            ],
        }
    }

    result_min = run_phys_minimal(ducis)
    print(json.dumps(result_min, ensure_ascii=False, indent=2))
