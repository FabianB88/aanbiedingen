"""Volledig assortiment met normale prijzen, uit de open data van Checkjebon
(github.com/supermarkt/checkjebon, MIT). Alleen onze ketens. Per winkel een
compact bestand, dat de pagina pas laadt als je zoekt."""
import json
import os
import re

import requests

BRON = "https://raw.githubusercontent.com/supermarkt/checkjebon/main/data/supermarkets.json"
DOEL = os.path.join(os.path.dirname(__file__), "..", "data", "assortiment")
KETENS = {"ah": "ah", "jumbo": "jumbo", "lidl": "lidl", "plus": "plus"}   # checkjebon-code -> onze code
EENHEID_RX = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:x\s*(\d+(?:[.,]\d+)?)\s*)?(kg|kilo|g|gram|gr|l|liter|ltr|ml|milliliter|cl)\b", re.I)


def per_eenheid(prijs, maat, naam):
    m = EENHEID_RX.search(maat or "") or EENHEID_RX.search(naam or "")
    if not m or not prijs:
        return None, ""
    n = float(m.group(1).replace(",", "."))
    if m.group(2):
        n *= float(m.group(2).replace(",", "."))
    u = m.group(3).lower()
    f = {"kg": 1, "kilo": 1, "g": .001, "gram": .001, "gr": .001, "l": 1, "liter": 1,
         "ltr": 1, "ml": .001, "milliliter": .001, "cl": .01}[u]
    if n * f <= 0:
        return None, ""
    return round(prijs / (n * f), 2), ("kg" if u in ("kg", "kilo", "g", "gram", "gr") else "l")


def bijwerken():
    try:
        r = requests.get(BRON, timeout=90)
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        print(f"[assortiment] ophalen mislukt, vorige versie blijft staan: {e}")
        return
    os.makedirs(DOEL, exist_ok=True)
    overzicht = {}
    for keten in data:
        code = KETENS.get(keten.get("n"))
        if not code:
            continue
        basis = keten.get("u", "")
        rijen = []
        for p in keten.get("d", []):
            if not p.get("n") or not p.get("p"):
                continue
            per, eenheid = per_eenheid(p["p"], p.get("s", ""), p["n"])
            link = p.get("l", "")
            rijen.append([p["n"], p["p"], p.get("s", ""), per, eenheid,
                          link if link.startswith("http") else (basis + link if basis else "")])
        with open(os.path.join(DOEL, f"{code}.json"), "w", encoding="utf-8") as f:
            json.dump(rijen, f, ensure_ascii=False, separators=(",", ":"))
        overzicht[code] = len(rijen)
    with open(os.path.join(DOEL, "index.json"), "w", encoding="utf-8") as f:
        json.dump(overzicht, f)
    print(f"[assortiment] {overzicht}")


if __name__ == "__main__":
    bijwerken()
