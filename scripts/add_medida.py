"""Actualiza las medidas corporales en data/medidas.json desde un issue.

La app abre un issue "cargar-medidas" con una plantilla `clave: valor`. Este
script parsea esos valores y los actualiza (sin borrar las claves que queden
vacías). Corre en GitHub Actions.
"""

import json
import os
import re
import sys
from datetime import date

PATH = os.path.join(os.path.dirname(__file__), "..", "data", "medidas.json")


def main():
    blob = f"{os.environ.get('ISSUE_TITLE', '')}\n{os.environ.get('ISSUE_BODY', '')}"
    try:
        with open(PATH, encoding="utf-8") as f:
            medidas = json.load(f)
    except Exception:
        medidas = []

    hoy = date.today().isoformat()
    cambios = 0
    for m in medidas:
        k = m.get("key")
        if not k:
            continue
        mt = re.search(rf"^\s*{re.escape(k)}\s*[:=]\s*([0-9]+(?:[.,][0-9]+)?)\s*$", blob, re.IGNORECASE | re.MULTILINE)
        if mt:
            m["value"] = float(mt.group(1).replace(",", "."))
            m["updated"] = hoy
            cambios += 1

    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(medidas, f, ensure_ascii=False, indent=1)
        f.write("\n")

    print(f"Medidas actualizadas: {cambios}")
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write(f"cambios={cambios}\n")
    if cambios == 0:
        print("::warning::No encontré valores en el issue (formato 'clave: valor').")


if __name__ == "__main__":
    main()
