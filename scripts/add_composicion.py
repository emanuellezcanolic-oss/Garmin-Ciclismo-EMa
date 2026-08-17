"""Agrega una medición de composición corporal al archivo data/composicion.json.

Corre en GitHub Actions cuando la app abre un issue "cargar-peso" con una
plantilla de claves (fecha, peso, grasa, masa_grasa, musculo). Así el atleta
carga las mediciones de su balanza desde la app, sin depender de que la balanza
sincronice con Garmin.
"""

import json
import os
import re
import sys
from datetime import date

PATH = os.path.join(os.path.dirname(__file__), "..", "data", "composicion.json")


def parse_from_issue():
    blob = f"{os.environ.get('ISSUE_TITLE', '')}\n{os.environ.get('ISSUE_BODY', '')}"

    def grab(*keys):
        for k in keys:
            m = re.search(rf"{k}\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)", blob, re.IGNORECASE)
            if m:
                return float(m.group(1).replace(",", "."))
        return None

    md = re.search(r"fecha\s*[:=]\s*(\d{4}-\d{2}-\d{2})", blob, re.IGNORECASE)
    entry = {
        "date": md.group(1) if md else date.today().isoformat(),
        "weight": grab("peso", "weight"),
        "body_fat": grab("grasa", "pgc", "body_fat"),
        "fat_mass": grab("masa_grasa", "masa de grasa", "fat_mass"),
        "muscle": grab("musculo", "músculo", "mme", "muscle"),
        "source": "app",
    }
    # completar masa magra
    if entry["weight"] and entry["fat_mass"] is not None:
        entry["lean"] = round(entry["weight"] - entry["fat_mass"], 1)
    elif entry["weight"] and entry["body_fat"] is not None:
        entry["fat_mass"] = round(entry["weight"] * entry["body_fat"] / 100, 1)
        entry["lean"] = round(entry["weight"] * (1 - entry["body_fat"] / 100), 1)
    return entry


def main():
    entry = parse_from_issue()
    if not any(entry.get(k) is not None for k in ("weight", "body_fat", "fat_mass", "muscle")):
        print("::error::No encontré ningún valor (peso/grasa/masa_grasa/musculo) en el issue.")
        sys.exit(1)

    try:
        with open(PATH, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        data = []

    # reemplaza si ya hay una medición de esa fecha; si no, la agrega
    data = [e for e in data if e.get("date") != entry["date"]]
    data.append(entry)
    data.sort(key=lambda e: e.get("date", ""))

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"Agregada medición {entry['date']}: {json.dumps(entry, ensure_ascii=False)}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"fecha={entry['date']}\n")
            f.write(f"grasa={entry.get('body_fat')}\n")
            f.write(f"musculo={entry.get('muscle')}\n")


if __name__ == "__main__":
    main()
