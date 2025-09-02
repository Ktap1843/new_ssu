import os
import argparse
import json
from controllers.input_controller import InputController
from controllers.calculation_controller import CalculationController
from controllers.output_controller import OutputController
from logger_config import get_logger

BASE_DIR = os.path.dirname(__file__)
INPUT_DIR = os.path.join(BASE_DIR, "inputdata")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputdata")
os.makedirs(OUTPUT_DIR, exist_ok=True)


logger = get_logger("FlowProcessor")


class FlowProcessor:
    def __init__(self, input_dir: str, output_dir: str):
        self.input_controller = InputController(input_dir)
        self.output_controller = OutputController(output_dir)

    def process_file(self, filename: str):
        try:
            logger.info(f"Обработка файла: {filename}")
            data = self.input_controller.load_file(filename)
            prepared_params = self.input_controller.prepare_params(data)
            self.output_controller.save_input_copy(filename, data)

            calc_controller = CalculationController(data, prepared_params)
            result = calc_controller.run_calculations()
            result["input_file"] = filename

            self.output_controller.save_result(filename, result)
            logger.info(f"Файл успешно обработан: {filename}")
        except Exception as e:
            logger.warning(f"Предупреждение: проблема с {filename}: {e}")


def process_single_file_if_exists(filename: str):
    input_path = os.path.join(INPUT_DIR, filename)
    if os.path.exists(input_path):
        processor = FlowProcessor(INPUT_DIR, OUTPUT_DIR)
        processor.process_file(filename)
    else:
        logger.warning(f"Файл '{filename}' не найден в папке inputdata")


def process_all_files():
    processor = FlowProcessor(INPUT_DIR, OUTPUT_DIR)
    for filename in os.listdir(INPUT_DIR):
        if filename.endswith(".json"):
            #logger.info(f"Обработка файлов: {filename}")
            processor.process_file(filename)


if __name__ == "__main__":
    DEBUG_SINGLE_FILE = False
    FILENAME_TO_DEBUG = "check_algoritm_2.json"

    if DEBUG_SINGLE_FILE:
        process_single_file_if_exists(FILENAME_TO_DEBUG)
    else:
        process_all_files()
