"""Haalt alle winkels op en schrijft data/aanbiedingen.json en data/status.json.
Faalt één winkel, dan blijven de vorige gegevens van die winkel staan."""
import datetime as dt
import json
import os
import sys
import traceback

from categorie import categorie
from korting import bereken, prijs
from winkels import WINKELS

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA = os.path.join(ROOT, "data")


def laad(pad, standaard):
    try:
        with open(pad, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return standaard


def normaliseer(winkel, a):
    nu = prijs(a.get("prijs_nu"))
    was = prijs(a.get("prijs_was"))
    pct, tot = bereken(a.get("actie", ""), nu, was)
    titel = " ".join(str(a.get("titel", "")).split())
    return {
        "winkel": winkel,
        "titel": titel,
        "merk": a.get("merk", ""),
        "eenheid": a.get("eenheid", ""),
        "actie": " ".join(str(a.get("actie", "")).split()),
        "korting": pct,
        "tot": tot,
        "prijs_nu": nu,
        "prijs_was": was,
        "categorie": categorie(titel, a.get("cat_hint", "")),
        "img": a.get("img", ""),
        "url": a.get("url", ""),
        "geldig": a.get("geldig", ""),
    }


def main(alleen=None):
    os.makedirs(DATA, exist_ok=True)
    oud = laad(os.path.join(DATA, "aanbiedingen.json"), {"aanbiedingen": []})
    status = laad(os.path.join(DATA, "status.json"), {})
    nu = dt.datetime.now(dt.timezone.utc).isoformat(timespec="minutes")

    per_winkel = {}
    for a in oud.get("aanbiedingen", []):
        per_winkel.setdefault(a["winkel"], []).append(a)

    for code, (naam, land, functie) in WINKELS.items():
        if alleen and code not in alleen:
            continue
        print(f"=== {naam}")
        try:
            ruw = functie()
            items = [normaliseer(code, a) for a in ruw]
            items = [i for i in items if i["titel"]]
            if not items:
                raise RuntimeError("0 aanbiedingen herkend")
            per_winkel[code] = items
            status[code] = {"naam": naam, "land": land, "ok": True, "aantal": len(items),
                            "met_korting": sum(1 for i in items if i["korting"] is not None),
                            "bijgewerkt": nu, "fout": ""}
            print(f"    {len(items)} aanbiedingen")
        except Exception as e:
            traceback.print_exc()
            vorige = status.get(code, {})
            status[code] = {"naam": naam, "land": land, "ok": False,
                            "aantal": len(per_winkel.get(code, [])),
                            "met_korting": vorige.get("met_korting", 0),
                            "bijgewerkt": vorige.get("bijgewerkt", ""),
                            "fout": f"{type(e).__name__}: {e}"[:300], "geprobeerd": nu}

    alles = [a for code in WINKELS for a in per_winkel.get(code, [])]
    with open(os.path.join(DATA, "aanbiedingen.json"), "w", encoding="utf-8") as f:
        json.dump({"bijgewerkt": nu, "aanbiedingen": alles}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    print(json.dumps(status, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else None)
