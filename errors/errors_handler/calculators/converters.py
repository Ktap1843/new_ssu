# errors/errors_handler/calculators/converters.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Sequence, Dict, Any
from errors.errors_handler.geom_sum import geometric_sum

# ==========================
# МОДЕЛИ
# ==========================

@dataclass
class InfluenceRel:
    """Относительная погрешность отдельного влияния компонента, %."""
    rel_percent: float  # уже в %

@dataclass
class ConverterSpecRel:
    """
    Спецификация одного преобразователя (компонента цепочки) в относительных %.
    main_rel_percent — внутренняя (intrinsic) составляющая компонента.
    influences — список дополнительных влияний (compl, др.), каждое — в %.
    """
    main_rel_percent: float
    influences: List[InfluenceRel]

    def total_rel_percent(self) -> float:
        """Суммарная относительная погрешность компонента δ_i = RSS(main, influences...)."""
        parts = [self.main_rel_percent] + [inf.rel_percent for inf in self.influences]
        return geometric_sum(*parts)

@dataclass
class ChainComponent:
    """
    Компонент цепи:
      - func: "linear" | "quadratic" (влияет на коэффициент чувствительности k из табл.7)
      - spec: ConverterSpecRel — внутр. и дополнительные влияния компонента в %
    """
    func: str
    spec: ConverterSpecRel


# ==========================
# ВСПОМОГАТЕЛЬНЫЕ ЧТЕНИЯ И ПРЕОБРАЗОВАНИЯ
# ==========================

def _read_rel_from_ui(node: Optional[dict]) -> float:
    """
    Читает относительную погрешность (%) из узла UI-формата:
      {"errorTypeId":"RelErr","value":{"real": <num>, "unit":"percent"}}
    Если node=None или значение некорректно — возвращает 0.0 (твои правила: None -> 0).
    Примечание: здесь считаем, что конвертеры подаются в относительных %, как мы договаривались.
    """
    if not node:
        return 0.0
    v = (node.get("value") or {})
    try:
        unit = str(v.get("unit", "")).lower()
        if unit not in ("percent", "%", "percents"):
            # Если внезапно не в процентах — трактуем как 0, чтобы не ломать
            return 0.0
        val = float(v.get("real", 0.0))
        return abs(val)
    except Exception:
        return 0.0


def _read_component_rel(payload: dict, idx: int, compl_keys: Sequence[str]) -> ConverterSpecRel:
    """
    Универсальное чтение i-го преобразователя:
      - intrinsic: payload[f"converter{idx}IntrError"] (None -> 0)
      - influences: перечень ключей compl_keys (каждый — узел UI; None -> 0)
    Возвращает спецификацию компонента в относительных процентах.
    """
    intr_node = payload.get(f"converter{idx}IntrError")
    intr_rel = _read_rel_from_ui(intr_node)

    influences: List[InfluenceRel] = []
    for key in compl_keys:
        node = payload.get(key)
        influences.append(InfluenceRel(_read_rel_from_ui(node)))

    return ConverterSpecRel(main_rel_percent=intr_rel, influences=influences)


def build_component_from_payload(
    payload: dict,
    idx: int,
    func: str = "linear",
    compl_keys: Optional[Sequence[str]] = None,
) -> ChainComponent:
    """
    Строит ChainComponent для произвольного idx (1, 2, 3, ...).
    compl_keys — список дополнительных влияний. Если не задан, берём дефолт: ["converter{idx}ComplError"].
    Все отсутствующие/None значения трактуются как 0 (твой контракт).
    """
    if compl_keys is None:
        compl_keys = [f"converter{idx}ComplError"]
    spec = _read_component_rel(payload, idx, compl_keys)
    return ChainComponent(func=func or "linear", spec=spec)


def combine_chain_relative(components: List[ChainComponent]) -> float:
    """
    Итоговые границы относительной погрешности цепи (%, RSS с k):
      δ_chain = sqrt( Σ (k_i * δ_i)^2 ),
    где δ_i — total_rel_percent() i-го компонента, k_i — коэф. чувствительности (табл.7):
        linear    -> k=1
        quadratic -> k=2
    """
    if not components:
        return 0.0

    def _k(func: str) -> float:
        return 2.0 if str(func).lower() == "quadratic" else 1.0

    squares = []
    for comp in components:
        delta_i = comp.spec.total_rel_percent()
        k = _k(comp.func)
        squares.append((k * delta_i) ** 2)
    return (sum(squares)) ** 0.5
