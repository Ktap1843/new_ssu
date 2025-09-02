from errors.errors_handler.packages.error_package import process_error_package
from errors.errors_handler.packages.composition_package import process_composition_package
from errors.errors_handler.packages.phys_package import process_phys_package
from errors.errors_handler.packages.flow_package import process_flow_package

def process_request(data: dict) -> dict:
    out = {"errors": {}, "phys": {}, "flow": {}, "composition": {}}

    if pkg := data.get("compositionErrorPackage"):
        out["composition"] = process_composition_package(pkg)

    if pkg := data.get("physPackage"):
        out["phys"] = process_phys_package(pkg)  # может вернуть подготовленные значения value/units

    if pkg := data.get("errorPackage"):
        out["errors"] = process_error_package(pkg, phys=out["phys"])

    if pkg := data.get("flowPackage"):
        out["flow"] = process_flow_package(pkg, errors=out["errors"], phys=out["phys"])

    # здесь же можешь собрать expected/итоги
    return out
