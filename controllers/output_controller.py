import os
import json
from typing import Any

class OutputController:
    """Контроллер для сохранения результатов и входных данных"""
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        os.makedirs(self.output_dir, exist_ok=True)

    def save_json(self, filename: str, data: dict, suffix: str = "_out"):
        base_name = os.path.splitext(filename)[0]
        output_path = os.path.join(self.output_dir, f"{base_name}{suffix}.json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def save_input_copy(self, filename: str, input_data: dict):
        self.save_json(filename, input_data, suffix="_input")

    def save_result(self, filename: str, result_data: dict):
        self.save_json(filename, result_data, suffix="_out")
