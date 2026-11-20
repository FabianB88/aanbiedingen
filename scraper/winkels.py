"""Per winkel: hoe de aanbiedingen worden opgehaald en omgezet.

Elke functie geeft een lijst dicts terug met minimaal:
  titel, actie, prijs_nu, prijs_was, img, url, geldig
"""
import json
import re
import time

import requests

import os

from browser import haal, DEBUG
from korting import prijs

UA_APP = "Appie/8.22.3 Model/phone Android/14"


# ---------------------------------------------------------------- AH (API)
def ah():
    try:
        return _ah_api()
    except Exception as e:
        print("[ah] API-fout:", e, "- val terug op de website")
        return _generiek("ah", ["https://www.ah.nl/bonus"])


def _ah_api():
    os.makedirs(DEBUG, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA_APP, "Content-Type": "application/json",
                      "x-application": "AHWEBSHOP", "x-clientname": "appie-android"})
    r = s.post("https://api.ah.nl/mobile-auth/v1/auth/token/anonymous",
               json={"clientId": "appie"}, timeout=30)
    r.raise_for_status()
    s.headers["Authorization"] = "Bearer " + r.json()["access_token"]

    uit = {}
    for pagina in range(0, 40):
        r = s.get("https://api.ah.nl/mobile-services/product/search/v2",
                  params={"sortOn": "RELEVANCE", "page": pagina, "size": 750,
                          "bonus": "true", "query": ""}, timeout=30)
        if r.status_code != 200:
            print("[ah] status", r.status_code, r.text[:300])
            break
        data = r.json()
        producten = data.get("products", [])
        if pagina == 0:
            with open(os.path.join(DEBUG, "ah-api.json"), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=1)
        for p in producten:
            if not p.get("isBonus"):
                continue
            imgs = sorted(p.get("images") or [], key=lambda i: i.get("width", 0))
            img = next((i["url"] for i in imgs if i.get("width", 0) >= 200), imgs[-1]["url"] if imgs else "")
            actie = p.get("bonusMechanism") or ""
            labels = p.get("discountLabels") or []
            if not actie and labels:
                actie = labels[0].get("defaultDescription", "")
            uit[p.get("webshopId")] = {
                "titel": p.get("title", ""),
                "merk": p.get("brand", ""),
                "eenheid": p.get("salesUnitSize", ""),
                "actie": actie,
                "prijs_nu": p.get("currentPrice"),
                "prijs_was": p.get("priceBeforeBonus"),
                "img": img,
                "url": f"https://www.ah.nl/producten/product/wi{p.get('webshopId')}",
                "geldig": _ah_geldig(p),
                "cat_hint": p.get("mainCategory", ""),
            }
        totaal = data.get("page", {}).get("totalPages", 1)
        if pagina + 1 >= totaal:
            break
        time.sleep(0.5)
    if not uit:
        print("[ah] API leverde niets op, val terug op de website")
        return _generiek("ah", ["https://www.ah.nl/bonus"])
    return list(uit.values())


def _ah_geldig(p):
    a, b = p.get("bonusStartDate"), p.get("bonusEndDate")
    if a and b:
        return f"{a[8:10]}-{a[5:7]} t/m {b[8:10]}-{b[5:7]}"
    return ""


# ------------------------------------------------- generieke kaart-parser
ACTIE_RX = re.compile(
    r"(\d+\s*\+\s*\d+(\s*gratis)?|\d+\s*(e|de)\s+(halve prijs|gratis|voor[^\n]*)|"
    r"-?\s*\d{1,2}\s*%[^\n]{0,20}|\d+\s*(voor|für)\s*€?\s*[\d.,-]+|"
    r"\d\.?\s*(artikel|stück)[^\n]{0,25}|tot wel[^\n]{0,20}|bis zu[^\n]{0,20}|"
    r"\d+[.,]?\d*\s*(euro)?\s*korting)", re.I)
GELDIG_RX = re.compile(r"((geldig|t/m|tm|vanaf|van|gültig|ab|bis)\s[^\n]{3,40}\d)", re.I)
PRIJS_RX = re.compile(r"(?<![\d%])(\d{1,3})\s*[.,]\s*(\d{2})(?!\d)|(?<![\d%])(\d{1,3})[.,]-")
RUIS = re.compile(r"^(bekijk|in winkelmand|toevoegen|bestel|meer info|details|nu |nu$|per |aanbieding|actie|online|alleen|in den warenkorb|zum angebot|€|\d)", re.I)


def _prijzen(tekst):
    gevonden = []
    for m in PRIJS_RX.finditer(tekst):
        if m.group(1):
            gevonden.append(float(f"{m.group(1)}.{m.group(2)}"))
        else:
            gevonden.append(float(m.group(3)))
    return gevonden


def kaart_naar_aanbieding(k):
    tekst = k.get("tekst", "")
    regels = [r.strip() for r in tekst.split("\n") if r.strip()]
    if not regels:
        return None
    actie_m = ACTIE_RX.search(tekst)
    actie = actie_m.group(0).strip() if actie_m else ""
    geldig_m = GELDIG_RX.search(tekst)
    # titel: langste regel zonder prijs/actie/ruis, anders alt-tekst
    kandidaten = [r for r in regels if len(r) > 3 and not PRIJS_RX.search(r)
                  and not ACTIE_RX.fullmatch(r) and not RUIS.match(r) and "%" not in r]
    titel = max(kandidaten, key=len) if kandidaten else (k.get("alt") or "")
    if k.get("alt") and len(k["alt"]) > len(titel) and len(k["alt"]) < 120:
        titel = k["alt"]
    prijzen = [p for p in _prijzen(tekst) if 0.05 <= p < 500]
    nu = was = None
    if len(prijzen) >= 2:
        was, nu = max(prijzen[:3]), min(prijzen[:3])
        if was == nu:
            was = None
    elif prijzen:
        nu = prijzen[0]
    if not titel or (not actie and not was):
        return None
    return {"titel": titel[:140], "actie": actie, "prijs_nu": nu, "prijs_was": was,
            "img": k.get("img", ""), "url": k.get("href", ""),
            "geldig": geldig_m.group(0) if geldig_m else "", "ruw": tekst[:300]}


def _generiek(winkel, urls, selector=None, klik=None):
    url, kaarten, _ = haal(winkel, urls, selector=selector, klik_teksten=klik)
    print(f"[{winkel}] {url}: {len(kaarten)} kaarten gevonden")
    uit, gezien = [], set()
    for k in kaarten:
        a = kaart_naar_aanbieding(k)
        if a and (a["titel"], a["actie"]) not in gezien:
            gezien.add((a["titel"], a["actie"]))
            uit.append(a)
    return uit


# ------------------------------------------------------------- per winkel
def jumbo():
    return _generiek("jumbo", ["https://www.jumbo.com/aanbiedingen/nu",
                               "https://www.jumbo.com/aanbiedingen"])


def lidl():
    url, kaarten, _ = haal("lidl", ["https://www.lidl.nl/c/aanbiedingen/a10008785",
                                    "https://www.lidl.nl/aanbiedingen",
                                    "https://www.lidl.nl/"])
    uit = []
    for k in kaarten:
        grid = k.get("attrs", {}).get("data-grid-data")
        if grid:
            try:
                g = json.loads(grid)
                pr = g.get("price", {}) or {}
                actie = (pr.get("discount", {}) or {}).get("discountText", "") or ""
                uit.append({"titel": g.get("fullTitle") or g.get("title", ""),
                            "actie": actie, "prijs_nu": pr.get("price"),
                            "prijs_was": pr.get("oldPrice"),
                            "img": g.get("image", ""), "url": "https://www.lidl.nl" + g.get("canonicalPath", ""),
                            "geldig": (g.get("stockAvailability", {}) or {}).get("badgeInfo", {}).get("badges", [{}])[0].get("text", "") if isinstance(g.get("stockAvailability"), dict) else ""})
                continue
            except Exception:
                pass
        a = kaart_naar_aanbieding(k)
        if a:
            uit.append(a)
    return uit


def aldi():
    return _generiek("aldi", ["https://www.aldi.nl/aanbiedingen.html",
                              "https://www.aldi.nl/aanbiedingen"])


def plus():
    return _generiek("plus", ["https://www.plus.nl/aanbiedingen"])


def aldi_sued():
    return _generiek("aldi_sued_de", ["https://www.aldi-sued.de/de/angebote.html",
                                      "https://www.aldi-sued.de/angebote"])


def kaufland():
    return _generiek("kaufland_de", ["https://filiale.kaufland.de/angebote/uebersicht.html",
                                     "https://www.kaufland.de/angebote/"])


WINKELS = {
    "ah": ("Albert Heijn", "NL", ah),
    "jumbo": ("Jumbo", "NL", jumbo),
    "lidl": ("Lidl", "NL", lidl),
    "aldi": ("Aldi", "NL", aldi),
    "plus": ("PLUS", "NL", plus),
    "aldi_sued": ("Aldi Süd", "DE", aldi_sued),
    "kaufland": ("Kaufland", "DE", kaufland),
}
