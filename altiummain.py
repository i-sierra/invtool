from __future__ import annotations
from typing import Optional
import pyaltiumlib, json, ast, re
from pyaltiumlib.libcomponent import LibComponent
from colorama import Fore as tcolor
from colorama import Style as tstyle

SCH_LIBRARIES = [
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_SemiDiscrete.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Resistors.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Misc.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Inductors.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_ICs.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Connectors.SchLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Capacitors.SchLib",
]

PCB_LIBRARIES = [
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Semi.PcbLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Passive.PcbLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Modules.PcbLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_EMech.PcbLib",
    "C:\\Users\\Public\\Documents\\Altium\\PCB_Project\\IRIS_Connectors.PcbLib",
]

OPTIONAL_PARAMS = ["supplier_2", "supplier_3", "supplier_pn_2", "supplier_pn_3"]


class Part:
    def __init__(self, ref: str, lib_ref: str, params: dict[str, str]):
        self.reference: str = ref
        self.lib: str = lib_ref
        self.params: dict[str, str] = params

    @staticmethod
    def from_dict(ref: str, lib: str, data: dict) -> Part:
        """Create a Part from a dictionary representation."""

        # Extract parameters
        filtered_data = {
            "iris_pn": data.get("IRIS PN", ""),
            "man": data.get("Manufacturer", ""),
            "man_pn": data.get("Manufacturer Part Number", ""),
            "status": data.get("Part Status", ""),
            "pkg": data.get("Package", ""),
            "value": data.get("Value", ""),
            "supplier_1": data.get("Supplier 1", ""),
            "supplier_pn_1": data.get("Supplier Part Number 1", ""),
            "supplier_2": data.get("Supplier 2", ""),
            "supplier_pn_2": data.get("Supplier Part Number 2", ""),
            "supplier_3": data.get("Supplier 3", ""),
            "supplier_pn_3": data.get("Supplier Part Number 3", ""),
        }

        # Extract all links in the part
        for k, v in data.items():
            regex = r"ComponentLink(\d+)Description"
            m = re.match(regex, k)
            if m and v == "Datasheet":
                filtered_data[f"datasheet"] = data.get(
                    f"ComponentLink{m.group(1)}URL", ""
                )

        return Part(ref, lib, filtered_data)


def load_parts_from_lib(lib_ref: str) -> list[Part]:
    parts: list[Part] = []
    lib = pyaltiumlib.read(lib_ref)

    for ref in lib.list_parts():
        c = lib.get_part(ref)
        if not isinstance(c, LibComponent):
            continue

        meta = c.read_meta()
        params = parse_params(meta.get("Parameter", "{}"))
        part = Part.from_dict(ref, lib_ref, params)
        parts.append(part)

    return parts


def parse_params(raw):
    """Parse the raw parameter input into a structured format."""

    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str):
        return {}

    txt = raw.strip()

    # Try parsing as JSON
    try:
        return json.loads(txt)
    except json.JSONDecodeError:
        pass

    # Try parsing as a Python literal dict
    try:
        return ast.literal_eval(txt)
    except (ValueError, SyntaxError):
        pass

    return {}


def save_to_csv(parts: list[Part], filename: Optional[str] = None):
    import csv

    if not filename:
        filename = "parts.csv"

    with open(filename, mode="w", newline="") as file:
        writer = csv.writer(file, delimiter=";")
        param_hdrs = parts[0].params.keys() if parts else []
        writer.writerow(["lib", "ref"] + list(param_hdrs))
        for part in parts:
            # Skip parts without proper IRIS PN
            iris_pn = part.params.get("iris_pn", "")
            if not re.match(r"^\d{6}-\d{2}$", iris_pn):
                if iris_pn not in ("N/A"):
                    print(
                        f"{tcolor.LIGHTCYAN_EX}INFO >>>{tstyle.RESET_ALL} Invalid IRIS part number "
                        f"{tcolor.CYAN}'{iris_pn}'{tstyle.RESET_ALL} in {tcolor.MAGENTA}'"
                        f"{part.reference}'{tstyle.RESET_ALL} {tcolor.BLACK}[{part.lib}]"
                        f"{tstyle.RESET_ALL}"
                    )
                continue

            row = [part.lib, part.reference]
            for h in param_hdrs:
                v = part.params.get(h, "")
                if v in ("", "*"):
                    # Print a warning if the parameter is not optional
                    if h not in OPTIONAL_PARAMS:
                        print(
                            f"{tcolor.LIGHTYELLOW_EX}WARN >>>{tstyle.RESET_ALL} {tcolor.GREEN}'{h}'"
                            f"{tstyle.RESET_ALL} is missing in part {tcolor.MAGENTA}'"
                            f"{part.reference}'{tstyle.RESET_ALL} {tcolor.BLACK}[{part.lib}]"
                            f"{tstyle.RESET_ALL}"
                        )
                    row.append("")
                else:
                    row.append(("'" + v) if re.match(r"^\d+$", v) else v)
            writer.writerow(row)


if __name__ == "__main__":
    parts = []
    for lib in SCH_LIBRARIES:
        parts.extend(load_parts_from_lib(lib))
    save_to_csv(parts)
