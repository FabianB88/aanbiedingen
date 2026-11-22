"""Haalt alle winkels op en schrijft data/aanbiedingen.json en data/status.json.
Faalt één winkel, dan blijven de vorige gegevens van die winkel staan."""
import datetime as dt
import json
import os
import re
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


def cat(titel, hint):
    return categorie(titel, hint)


GEWICHT_ACTIE = re.compile(r"(\d+)\s*(gram|gr|g|kilo|kg)\s*voor\s*€?\s*(\d+[.,]\d{2})", re.I)
GEWICHT_EENHEID = re.compile(r"(\d+(?:[.,]\d+)?)\s*(kg|kilo|g|gram)\b", re.I)


def per_gewicht(actie, eenheid, nu):
    """'100 GRAM VOOR 1.79' bij een pak van ca. 755 g: actieprijs voor het hele pak."""
    m = GEWICHT_ACTIE.search(actie or "")
    e = GEWICHT_EENHEID.search(eenheid or "")
    if not m or not e:
        return nu, False
    actie_g = float(m.group(1)) * (1000 if m.group(2).lower() in ("kilo", "kg") else 1)
    pak_g = float(e.group(1).replace(",", ".")) * (1000 if e.group(2).lower() in ("kilo", "kg") else 1)
    if actie_g <= 0 or pak_g <= 0:
        return nu, False
    return round(float(m.group(3).replace(",", ".")) * pak_g / actie_g, 2), True


NONFOOD_CATS = {"Overig"}
# kaartfragmenten die geen product zijn ("500 gram 2.99", "OP=OP", "coupons")
RUIS_TITEL = re.compile(r"^(\d+\s*(gram|g|kg|ml|l|stuks?)\s*[\d.,]+|op=op|niet verkrijgbaar|\d+\s*%|coupons|hot dog mit|biozidprodukte.*)$", re.I)


def normaliseer(winkel, a):
    nu = prijs(a.get("prijs_nu"))
    was = prijs(a.get("prijs_was"))
    nu, omgerekend = per_gewicht(a.get("actie", ""), a.get("eenheid", ""), nu)
    # bij een gewichtsactie is de prijsvergelijking leidend, niet de actietekst
    pct, tot = bereken("" if omgerekend else a.get("actie", ""), nu, was)
    tot = tot or bool(a.get("tot"))
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
        "categorie": cat(titel, a.get("cat_hint", "")),
        "img": a.get("img", ""),
        "url": a.get("url", ""),
        "geldig": a.get("geldig", ""),
        "nonfood": a.get("nonfood"),
        "bf": bool(a.get("bf")),
        "ref": a.get("ref", ""),
        "temp": a.get("temp"),
    }


HISTORIE = os.path.join(DATA, "prijshistorie.json")
MEERKOOP = re.compile(r"\d\s*\+\s*\d|\d\s*(e|de)\s|\d\s*voor|für", re.I)


def prijshistorie_en_echt(alles):
    """Bewaart per non-food product de dagprijs (60 dagen) en markeert 'echte' kortingen
    van 50% of meer. Echt = de referentieprijs is wettelijk (laagste prijs van 30 dagen)
    of de mediaanprijs van Amazon, niet een adviesprijs, en wij hebben het product in de
    afgelopen 30 dagen niet zelf al ver onder die referentie gezien."""
    vandaag = dt.date.today()
    hist = laad(HISTORIE, {})
    for a in alles:
        if not (a.get("nonfood") or a.get("bf")) or not a.get("prijs_nu"):
            continue
        k = f"{a['winkel']}|{a['titel'].lower()}"
        reeks = [r for r in hist.get(k, []) if (vandaag - dt.date.fromisoformat(r[0])).days <= 60]
        if not reeks or reeks[-1][0] != vandaag.isoformat():
            reeks.append([vandaag.isoformat(), a["prijs_nu"]])
        hist[k] = reeks
        recent = [p for d, p in reeks if (vandaag - dt.date.fromisoformat(d)).days <= 30 and d != vandaag.isoformat()]
        a["laagste_gezien"] = min(recent) if recent else None
        a["dagen_gemeten"] = len(reeks)
        a["echt"] = bool(
            (a.get("korting") or 0) >= 50 and not a.get("tot")
            and a.get("ref") in ("van", "mediaan", "pepper")
            and not MEERKOOP.search(a.get("actie", ""))
            and (a.get("prijs_was") or a.get("ref") == "pepper")
            and (a.get("ref") != "pepper" or (a.get("temp") or 0) >= 100)
            and not (a["laagste_gezien"] and a["laagste_gezien"] < a["prijs_was"] * 0.9)
        )
    with open(HISTORIE, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[echt] {sum(1 for a in alles if a.get('echt'))} echte kortingen van 50% of meer")


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
            items = [i for i in items if i["titel"] and not RUIS_TITEL.match(i["titel"])]
            for i in items:
                # onbekend: food, tenzij het taalmodel straks "Non-food" zegt
                i["nonfood"] = bool(i["nonfood"])
            if not items:
                raise RuntimeError("0 aanbiedingen herkend")
            # veel minder dan vorige keer: waarschijnlijk een haperende pagina, oude gegevens houden
            vorig = len(per_winkel.get(code, []))
            if vorig >= 50 and len(items) < 0.4 * vorig:
                raise RuntimeError(f"maar {len(items)} aanbiedingen (vorige keer {vorig}), vorige gegevens bewaard")
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
    try:
        from llm_categorie import deel_in
        deel_in(alles)
    except Exception as e:
        print("[categorie] indeling via model overgeslagen:", e)
    # non-food en Black Friday krijgen hun eigen categorieën
    from nonfood import nf_categorie
    for a in alles:
        if a.get("nonfood"):
            a["categorie"] = nf_categorie(a["titel"], a.get("eenheid", ""))
    # Tweakers-check voor Black Friday-deals
    try:
        from tweakers import check
        check(alles)
    except Exception as e:
        print("[tweakers] overgeslagen:", e)
    prijshistorie_en_echt(alles)
    # Kaufland non-food zit op de online marktplaats, niet in de filiaalfolder:
    # link naar een zoekopdracht op kaufland.de in plaats van naar de filiaalpagina
    from urllib.parse import quote_plus
    for a in alles:
        if a["winkel"] == "kaufland" and a.get("nonfood"):
            a["url"] = "https://www.kaufland.de/s/?search_value=" + quote_plus(a["titel"])
    with open(os.path.join(DATA, "aanbiedingen.json"), "w", encoding="utf-8") as f:
        json.dump({"bijgewerkt": nu, "aanbiedingen": alles}, f, ensure_ascii=False, separators=(",", ":"))
    with open(os.path.join(DATA, "status.json"), "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=1)
    print(json.dumps(status, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main(sys.argv[1].split(",") if len(sys.argv) > 1 else None)
