"""Genera la tabla de referencia de ultrasonido desde el libro fuente.

Fuente: Shin et al. (2005), J Korean Med Sci, Tablas 2 y 3 (n = 3.053).
Entrada: _local/Ultrasonido.xlsx, hoja "Base Consolidada (Numerica)".
Salida:  backend/app/data/reference_ultrasound.json (versionado).

Uso:
    uv run python -m app.scripts.build_reference
    uv run python -m app.scripts.build_reference --xlsx "D:/otra/ruta.xlsx"
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from openpyxl import load_workbook

DEFAULT_XLSX = Path(__file__).resolve().parents[3] / "_local" / "Ultrasonido.xlsx"
OUTPUT = Path(__file__).resolve().parents[1] / "data" / "reference_ultrasound.json"

SEXES = {"hombres": "male", "mujeres": "female"}

# Indices (0-based) de la hoja consolidada.
COL_SEX = 0
COL_BAND = 1
COL_N = 2
COL_AGE_MEAN = 3
COL_BUA_MEAN = 5
COL_BUA_SD = 6
COL_SOS_MEAN = 7
COL_SOS_SD = 8


def _number(value: object) -> float:
    return float(str(value).replace(",", ".").strip())


def extract(xlsx_path: Path) -> dict:
    if not xlsx_path.exists():
        raise SystemExit(f"no existe el archivo fuente: {xlsx_path}")

    workbook = load_workbook(xlsx_path, data_only=True)
    sheet = workbook[workbook.sheetnames[1]]
    groups: list[dict] = []

    for row in sheet.iter_rows(min_row=2, values_only=True):
        if not row or row[COL_SEX] is None:
            continue
        sex_raw = str(row[COL_SEX]).strip().lower()
        if sex_raw not in SEXES:
            continue
        band = str(row[COL_BAND]).strip()
        if "-" not in band:
            continue
        low, high = (int(part) for part in band.split("-", 1))
        groups.append(
            {
                "sex": SEXES[sex_raw],
                "age_min": low,
                "age_max": high,
                "age_band": band,
                "n": int(row[COL_N]),
                "age_mean": _number(row[COL_AGE_MEAN]),
                "bua_mean": _number(row[COL_BUA_MEAN]),
                "bua_sd": _number(row[COL_BUA_SD]),
                "sos_mean": _number(row[COL_SOS_MEAN]),
                "sos_sd": _number(row[COL_SOS_SD]),
            }
        )

    groups.sort(key=lambda item: (item["sex"], item["age_min"]))
    if len(groups) != 12:
        raise SystemExit(f"se esperaban 12 grupos (2 sexos x 6 rangos), se leyeron {len(groups)}")

    return {
        "source": "Shin et al. (2005) - Journal of Korean Medical Science, Tables 2-3",
        "population": "Korean adults, n = 3,053",
        "bua_unit": "dB/MHz",
        "sos_unit": "m/s",
        "generated_from": xlsx_path.name,
        "groups": groups,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Genera la referencia de ultrasonido")
    parser.add_argument("--xlsx", type=Path, default=DEFAULT_XLSX)
    args = parser.parse_args()

    payload = extract(args.xlsx)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(payload['groups'])} grupos escritos en {OUTPUT}")
    for group in payload["groups"]:
        print(
            f"  {group['sex']:6} {group['age_band']:6} "
            f"BUA {group['bua_mean']:6.1f} +- {group['bua_sd']:4.1f}  "
            f"SOS {group['sos_mean']:7.1f} +- {group['sos_sd']:4.1f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
