class BaseStraightness:
    def __init__(self, beta: float, D: float, Ra: float,
                 ssu_type: str, ms_before: list,
                 ms_after: list = None, skip: bool = False):
        self.beta = beta
        self.D = D
        self.Ra = Ra
        self.ssu_type = ssu_type
        self.ms_before = ms_before
        self.ms_after = ms_after or []
        self.skip = skip

    def is_straightness_required(self) -> bool:
        return not self.skip

    def calculate(self):
        if not self.is_straightness_required():
            return None
        raise NotImplementedError("Must override calculate() in subclass")