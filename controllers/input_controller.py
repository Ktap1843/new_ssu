import os, json
from controllers.prepare_controller import PreparedController

class InputController:
    """Обработка входных данных"""
    def __init__(self, input_dir: str):
        self.input_dir = input_dir

    def load_file(self, filename: str) -> dict:
        path = os.path.join(self.input_dir, filename)
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def prepare_params(self, data: dict) -> PreparedController:
        cp = data["flowdata"]["constrictor_params"]
        ep = data["flowdata"]["environment_parameters"]
        pp = data["flowdata"]["physical_properties"]
        return PreparedController(d=cp["d20"]/1000,
            D=cp["D20"]/1000,
            p1=ep["p"],
            t1=ep["T"],
            dp=ep["dp"],
            R=pp.get("R", 8.314),
            Z=pp.get("Z", 1.0))
