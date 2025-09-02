from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

from logger_config import get_logger
from controllers.prepare_controller import PreparedController
from converters.units_validator import (
    convert_length,
    convert_pressure,
    kelvin_to_celsius,
)

log = get_logger("InputController")


# ------------------------ helpers ------------------------

def _dig(data: Dict[str, Any], path: Sequence[str]) -> Any:
    cur: Any = data
    for k in path:
        if not isinstance(cur, dict) or k not in cur:
            return None
        cur = cur[k]
    return cur


def _first(data: Dict[str, Any], *paths: Sequence[str]) -> Tuple[Optional[Any], Optional[Sequence[str]]]:
    for p in paths:
        v = _dig(data, p)
        if v is not None:
            return v, p
    return None, None


def _as_pressure_pa(node: Any, default_unit: str = "Pa") -> Optional[float]:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(convert_pressure(node, default_unit, "Pa"))
    if isinstance(node, dict):
        box = node.get("value") if "value" in node and isinstance(node["value"], dict) else node
        val = box.get("real")
        unit = box.get("unit", default_unit)
        if isinstance(val, (int, float)):
            return float(convert_pressure(val, unit, "Pa"))
    return None


def _as_length_m(node: Any, default_unit: str = "mm") -> Optional[float]:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        return float(convert_length(node, default_unit, "m"))
    if isinstance(node, dict):
        box = node.get("value") if "value" in node and isinstance(node["value"], dict) else node
        val = box.get("real")
        unit = box.get("unit", default_unit)
        if isinstance(val, (int, float)):
            return float(convert_length(val, unit, "m"))
    return None


def _as_temp_c(node: Any, default_unit: str = "C") -> Optional[float]:
    if node is None:
        return None
    if isinstance(node, (int, float)):
        if default_unit.lower().startswith("k"):
            return float(kelvin_to_celsius(node))
        return float(node)
    if isinstance(node, dict):
        box = node.get("value") if "value" in node and isinstance(node["value"], dict) else node
        val = box.get("real")
        unit = str(box.get("unit", default_unit)).lower()
        if not isinstance(val, (int, float)):
            return None
        if unit.startswith("k"):
            return float(kelvin_to_celsius(val))
        if unit in ("c", "°c", "celsius"):
            return float(val)
    return None


# ------------------------ parsed container ------------------------

@dataclass
class ParsedInput:
    remarks: List[str]
    values_si: Dict[str, float]


# ------------------------ controller ------------------------

class InputController:
    """Парсер входа + подготовка параметров для PreparedController.

    ВНИМАНИЕ: flowPackage игнорируется — расчёт всегда по одному сценарию.
    """

    def __init__(self) -> None:
        self._last_parsed: Optional[ParsedInput] = None

    # ---- public API ----

    def parse(self, data: Dict[str, Any]) -> ParsedInput:
        remarks: List[str] = []
        out: Dict[str, float] = {}

        def ok(name: str, path: Sequence[str], v_print: str) -> None:
            remarks.append(f"[OK] {name} <- {'/'.join(path)} → {v_print}")

        def miss(name: str, *alts: Sequence[str]) -> None:
            remarks.append(f"[INFO] Поле '{name}' не найдено (пути: {', '.join('/'.join(a) for a in alts)}).")

        # --- pressures ---
        p_abs_node, p_abs_path = _first(data,
            ("physPackage", "physProperties", "p_abs"),
            ("physPackage", "p_abs"),
        )
        p_abs = _as_pressure_pa(p_abs_node, "Pa")
        if p_abs is not None:
            out["p_abs"] = p_abs
            ok("p_abs", p_abs_path, f"{p_abs:.6g} Pa")

        p_atm_node, p_atm_path = _first(data,
            ("physPackage", "physProperties", "p_atm"),
            ("physPackage", "p_atm"),
        )
        p_atm = _as_pressure_pa(p_atm_node, "Pa")
        if p_atm is not None:
            out["p_atm"] = p_atm
            ok("p_atm", p_atm_path, f"{p_atm:.2f} Pa")
        else:
            miss("p_atm", ("physPackage", "physProperties", "p_atm"), ("physPackage", "p_atm"))

        p_st_node, p_st_path = _first(data,
            ("physPackage", "physProperties", "p_st"),
            ("physPackage", "p_st"),
        )
        p_st = _as_pressure_pa(p_st_node, "Pa")
        if p_st is not None:
            out["p_st"] = p_st
            ok("p_st", p_st_path, f"{p_st:.6g} Pa")
        else:
            miss("p_st", ("physPackage", "physProperties", "p_st"), ("physPackage", "p_st"))

        dp_node, dp_path = _first(data,
            ("physPackage", "physProperties", "dp"),
            ("physPackage", "dp"),
        )
        dp = _as_pressure_pa(dp_node, "Pa")
        if dp is not None:
            out["dp"] = dp
            ok("dp", dp_path, f"{dp:.6g} Pa")

        # --- temperatures ---
        T_node, T_path = _first(data,
            ("physPackage", "physProperties", "T"),
            ("physPackage", "T"),
        )
        T = _as_temp_c(T_node, "C")
        if T is not None:
            out["T"] = T
            ok("T", T_path, f"{T:.6g} C")

        Tst_node, Tst_path = _first(data,
            ("physPackage", "physProperties", "T_st"),
            ("physPackage", "T_st"),
        )
        Tst = _as_temp_c(Tst_node, "C")
        if Tst is not None:
            out["T_st"] = Tst
            ok("T_st", Tst_path, f"{Tst:.6g} C")
        else:
            miss("T_st", ("physPackage", "physProperties", "T_st"), ("physPackage", "T_st"))

        # --- lengths (mm→m) ---
        d20_node, d20_path = _first(data,
            ("lenPackage", "lenProperties", "d20"),
            ("flowdata", "constrictor_params", "d20"),  # если legacy
        )
        d20 = _as_length_m(d20_node, "mm")
        if d20 is not None:
            out["d20"] = d20
            ok("d20", d20_path, f"{d20:.3f} m")

        D20_node, D20_path = _first(data,
            ("lenPackage", "lenProperties", "D"),
            ("lenPackage", "lenProperties", "D20"),
            ("flowdata", "constrictor_params", "D20"),
            ("flowdata", "constrictor_params", "D"),
        )
        D20 = _as_length_m(D20_node, "mm")
        if D20 is not None:
            out["D20"] = D20
            ok("D20", D20_path, f"{D20:.3f} m")

        # ВНИМАНИЕ: flowPackage игнорируем — никаких q_v/q_st тут больше нет.

        parsed = ParsedInput(remarks=remarks, values_si=out)
        self._last_parsed = parsed
        return parsed

    def prepare_params(self, data: Dict[str, Any]) -> PreparedController:
        if not self._last_parsed:
            # в случае прямого вызова без parse()
            self.parse(data)
        assert self._last_parsed is not None
        v = self._last_parsed.values_si

        # R, Z — берём как есть (если есть), иначе дефолты
        phys = (data.get("physPackage") or {}).get("physProperties", {})
        R = phys.get("R", 8.314)
        Z = phys.get("Z", 1.0)

        # базовые проверки
        d_m = float(v.get("d20", 0.0))
        D_m = float(v.get("D20", 0.0))
        p_pa = float(v.get("p_abs", 0.0))
        dp_pa = float(v.get("dp", 0.0))
        t_c = float(v.get("T", 0.0))

        if not (d_m > 0 and D_m > 0 and d_m < D_m):
            raise ValueError(f"Некорректные диаметры: d20={d_m} м, D20={D_m} м")
        if p_pa <= 0:
            raise ValueError("Давление p_abs должно быть > 0 Па")
        if dp_pa <= 0:
            raise ValueError("Перепад давления dp должен быть > 0 Па")

        return PreparedController(
            d=d_m,
            D=D_m,
            p1=p_pa,
            t1=t_c,
            dp=dp_pa,
            R=R,
            Z=Z,
        )
