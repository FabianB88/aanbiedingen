"""Per winkel: hoe de aanbiedingen worden opgehaald en omgezet.

Elke functie geeft een lijst dicts terug met minimaal:
  titel, actie, prijs_nu, prijs_was, img, url, geldig
"""
import json
import re
import time

import requests

import os

from browser import haal, haal_details, DEBUG
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
def _regels(k):
    return [r.strip() for r in k.get("tekst", "").replace(" ", " ").split("\n") if r.strip()]


def _uniek(lijst):
    uit, gezien = [], set()
    for a in lijst:
        if a and a.get("titel") and (a["titel"], a.get("actie"), a.get("prijs_nu")) not in gezien:
            gezien.add((a["titel"], a.get("actie"), a.get("prijs_nu")))
            uit.append(a)
    return uit


def _met_parser(winkel, urls, parser, **kw):
    url, kaarten, _ = haal(winkel, urls, **kw)
    print(f"[{winkel}] {url}: {len(kaarten)} kaarten")
    uit = []
    for k in kaarten:
        try:
            uit.append(parser(k))
        except Exception as e:
            print(f"[{winkel}] kaart overgeslagen: {e}")
    return _uniek(uit)


PCT_RX = re.compile(r"(\d{1,2})\s*%")
GELDIG_NL = re.compile(r"((ma|di|wo|do|vr|za|zo)\s+\d+.*t/m.*|\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}|t/m .*)", re.I)


def jumbo_kaart(k):
    r = _regels(k)
    actie = r[0] if r and (ACTIE_RX.search(r[0]) or r[0].lower().startswith("voor") or r[0] == "OP=OP") else ""
    rest = [x for x in r if x != actie]
    geldig = next((x for x in rest if GELDIG_NL.search(x)), "")
    titel = k.get("alt") or next((x for x in rest if x != geldig and not PRIJS_RX.fullmatch(x)), "")
    nu = prijs(actie) if actie.lower().startswith("voor") else None
    if actie == "OP=OP":
        nu = next((prijs(x) for x in rest if PRIJS_RX.fullmatch(x)), None)
    return {"titel": titel, "actie": actie, "prijs_nu": nu, "prijs_was": None,
            "img": k.get("img", ""), "url": k.get("href", ""), "geldig": geldig}


def plus_kaart(k):
    t = k.get("tekst", "").replace(" ", " ")
    t = re.sub(r"(\d+)\.\s*\n\s*(\d{2})", r"\1.\2", t)          # "4.\n99" -> "4.99"
    r = [x.strip() for x in t.split("\n") if x.strip()]
    actie = r[0] if ACTIE_RX.search(r[0]) or "korting" in r[0].lower() or "gratis" in r[0].lower() else ""
    rest = r[1:] if actie else r
    titel = rest[0] if rest else ""
    detail = next((x for x in rest[1:] if x.lower().startswith(("bijv", "per "))), "")
    prijsregels = [x for x in rest[1:] if re.fullmatch(r"[\d.,\s-]+", x)]
    nu = prijs(prijsregels[0]) if prijsregels else None
    was = None
    if len(prijsregels) > 1:
        was = prijs(prijsregels[1].split("-")[0])      # onderkant van de range: voorzichtigste korting
    if detail.lower().startswith("bijv"):
        titel = f"{titel} ({detail[5:].strip()})"
    return {"titel": titel, "actie": actie, "prijs_nu": nu, "prijs_was": was, "eenheid": detail if detail.lower().startswith("per") else "",
            "tot": bool(len(prijsregels) > 1 and "-" in prijsregels[1]),
            "img": k.get("img", ""), "url": k.get("href", ""), "geldig": ""}


def aldi_kaart(k):
    r = [x for x in _regels(k) if not x.lower().startswith("kg =") and not x.lower().startswith("l =")]
    merk = ""
    if len(r) > 2 and r[0].isupper() and not PRIJS_RX.search(r[0]):
        merk, r = r[0].title(), r[1:]
    titel = r[0]
    pct = next((x for x in r if PCT_RX.search(x)), "")
    opop = "OP=OP" if "OP=OP" in r else ""
    prijzen = [prijs(x) for x in r if re.fullmatch(r"\d+[.,]\d{2}", x)]
    nu = prijzen[0] if prijzen else None
    was = prijzen[1] if len(prijzen) > 1 else None
    eenheid = next((x for x in r if re.search(r"\b(g|kg|l|ml|stuks?|tabs|per stuk\.?)$", x, re.I) and x != titel), "")
    return {"titel": titel, "merk": merk, "actie": pct or opop, "prijs_nu": nu, "prijs_was": was, "eenheid": eenheid,
            "img": k.get("img", ""), "url": k.get("href", ""), "geldig": ""}


def aldi_sued_kaart(k):
    t = k.get("tekst", "").replace(" ", " ")
    t = re.sub(r"\([^)]*/[^)]*\)", "", t)                   # grondprijs (x €/1 kg) weg
    r = [x.strip() for x in t.split("\n") if x.strip()]
    titel = k.get("alt") or ""
    merk = next((x for x in r if x.isupper() and len(x) > 2 and x != titel), "")
    pct = next((x for x in r if "spare" in x.lower() or PCT_RX.search(x)), "")
    prijzen = [float(f"{a}.{b}") for a, b in re.findall(r"(\d+),(\d{2})\s*€", t)]
    nu = prijzen[0] if prijzen else None
    was = prijzen[1] if len(prijzen) > 1 else None
    geldig = next((x for x in r if x.lower().startswith(("verfügbar", "gültig", "ab "))), "")
    return {"titel": titel, "merk": merk.title(), "actie": pct.replace("Spare", "").strip(), "prijs_nu": nu,
            "prijs_was": was, "img": k.get("img", ""), "url": k.get("href", ""), "geldig": geldig}


def lidl_kaart(k):
    r = _regels(k)
    geldig_r = next((x for x in r if GELDIG_NL.search(x) or x.lower().startswith("alleen in de winkel")), "")
    geldig = GELDIG_NL.search(geldig_r).group(0) if GELDIG_NL.search(geldig_r) else ""
    lidlplus = any("lidl plus" in x.lower() for x in r)
    pct = next((x for x in r if PCT_RX.fullmatch(x.replace("-", "").strip()) or re.fullmatch(r"-?\d{1,2}\s*%", x)), "")
    prijzen = [prijs(x) for x in r if re.fullmatch(r"\d+[.,]\d{2}", x)]
    # titel: eerste regel(s) tot de eerste prijs, zonder merk als dat in hoofdletters staat
    kop = []
    for x in r:
        if re.fullmatch(r"\d+[.,]\d{2}", x) or x.lower().startswith(("met lidl", "alleen", "per ")):
            break
        kop.append(x)
    merk = kop[0].title() if len(kop) > 1 and kop[0].isupper() else ""
    titel = " ".join(kop[1:] if merk else kop) or k.get("alt", "")
    actie = pct
    if pct and lidlplus:
        actie = f"{pct} met Lidl Plus"
    nu = was = None
    if (pct or lidlplus) and len(prijzen) >= 2:
        was, nu = prijzen[0], prijzen[1]
    elif prijzen:
        nu = prijzen[0]
    tekst = k.get("tekst", "")
    m = ACTIE_RX.search(tekst)
    if not actie and m and "%" not in m.group(0):
        actie = m.group(0)
    return {"titel": titel, "merk": merk, "actie": actie, "prijs_nu": nu, "prijs_was": was,
            "img": k.get("img", ""), "url": k.get("href", ""), "geldig": geldig}


def _jumbo_normaalprijzen(kaarten):
    """De 'Oude prijs' van elk product op een Jumbo-actiepagina."""
    prijzen = []
    for k in kaarten:
        t = k.get("tekst", "").replace("\u00a0", " ")
        m = re.search(r"Oude prijs:\s*€\s*(\d+),(\d{2})", t)
        if m:
            prijzen.append(float(f"{m.group(1)}.{m.group(2)}"))
    return prijzen


def jumbo():
    items = _met_parser("jumbo", ["https://www.jumbo.com/aanbiedingen/nu",
                                  "https://www.jumbo.com/aanbiedingen"], jumbo_kaart)
    # voor acties zonder normale prijs: bezoek de actiepagina
    nodig = [a for a in items if a.get("url") and "/aanbiedingen/" in a["url"]
             and not PCT_RX.search(a.get("actie", ""))]
    urls = list(dict.fromkeys(a["url"] for a in nodig))
    # cache: oude prijzen per actiepagina, geldig zolang de actie loopt
    cache_pad = os.path.join(DEBUG, "..", "data", "jumbo-oudeprijzen.json")
    try:
        with open(cache_pad, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    cache = {u: v for u, v in cache.items() if u in urls}          # verlopen acties weg
    nieuw = [u for u in urls if u not in cache]
    print(f"[jumbo] {len(urls)} acties, {len(nieuw)} nieuwe actiepagina's bezoeken")
    details = haal_details("jumbo", nieuw, max_urls=200)
    for u, kaarten in details.items():
        cache[u] = _jumbo_normaalprijzen(kaarten)     # ook leeg bewaren: niet elke run opnieuw
    with open(cache_pad, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False)
    for a in nodig:
        prijzen = cache.get(a["url"], [])
        if not prijzen:
            continue
        laag, hoog = min(prijzen), max(prijzen)
        a["prijs_was"] = laag                   # voorzichtigste korting
        a["tot"] = hoog > laag * 1.05
        # "2 voor 5,00": prijs_nu is het totaalbedrag; zet om naar per stuk
        m = re.search(r"(\d+)\s*voor\s*([\d.,]+)", a.get("actie", ""))
        if m and int(m.group(1)) > 1:
            a["prijs_nu"] = round(prijs(m.group(2)) / int(m.group(1)), 2)
        if a.get("prijs_nu") and a["prijs_nu"] >= laag:
            a["prijs_was"] = None               # geen echte korting af te leiden
    return items


def lidl_grid(g):
    """Eén product uit Lidl's data-grid-data JSON."""
    titel = re.sub(r"^[-\s]+", "", g.get("fullTitle") or g.get("title") or "")
    normaal = (g.get("price") or {}).get("price")
    lp = (g.get("lidlPlus") or [{}])[0] or {}
    lp_prijs = (lp.get("price") or {}).get("price")
    highlight = lp.get("highlightText") or ""
    disc = (g.get("price") or {}).get("discount") or {}
    actie, nu, was = "", normaal, None
    if lp_prijs and normaal and lp_prijs < normaal:
        nu, was = lp_prijs, normaal
        actie = f"{highlight} met Lidl Plus".strip() if highlight else "met Lidl Plus"
    elif lp_prijs and not normaal:
        nu = lp_prijs
        actie = f"{highlight} met Lidl Plus".strip()
    if disc.get("deletedPrice") and normaal and disc["deletedPrice"] > normaal:
        was, nu = disc["deletedPrice"], normaal
        actie = disc.get("discountText") or actie
    badges = ((g.get("stockAvailability") or {}).get("badgeInfo") or {}).get("badges") or []
    geldig = ""
    for b in badges:
        m = re.search(r"\d{1,2}/\d{1,2}\s*-\s*\d{1,2}/\d{1,2}", b.get("text", ""))
        if m:
            geldig = m.group(0)
    pack = ((g.get("price") or {}).get("packaging") or {}).get("text", "")
    return {"titel": titel, "merk": (g.get("brand") or {}).get("name", ""), "actie": actie,
            "prijs_nu": nu, "prijs_was": was, "eenheid": pack, "img": g.get("image", ""),
            "url": "https://www.lidl.nl" + (g.get("canonicalPath") or ""), "geldig": geldig,
            "cat_hint": g.get("category", "")}


def lidl():
    import html as _html
    url, kaarten, _ = haal("lidl", ["https://www.lidl.nl/c/aanbiedingen/a10008785",
                                    "https://www.lidl.nl/aanbiedingen"], traag=True)
    with open(os.path.join(DEBUG, "lidl.html"), encoding="utf-8") as f:
        h = f.read()
    uit, gezien = [], set()
    for ruw in re.findall(r'data-grid-data="([^"]+)"', h):
        try:
            g = json.loads(_html.unescape(ruw))
        except Exception:
            continue
        if g.get("erpNumber") in gezien:
            continue
        gezien.add(g.get("erpNumber"))
        uit.append(lidl_grid(g))
    print(f"[lidl] {len(uit)} producten uit grid-data, {len(kaarten)} zichtbare kaarten")
    titels = {a["titel"].lower() for a in uit}
    for k in kaarten:                      # aanvullen met kaarten zonder grid-data
        a = lidl_kaart(k)
        if a and a["titel"] and a["titel"].lower() not in titels:
            titels.add(a["titel"].lower())
            uit.append(a)
    return _uniek(uit)


def aldi():
    return _met_parser("aldi", ["https://www.aldi.nl/aanbiedingen.html",
                                "https://www.aldi.nl/aanbiedingen"], aldi_kaart)


def plus():
    return _met_parser("plus", ["https://www.plus.nl/aanbiedingen"], plus_kaart)


def aldi_sued():
    return _met_parser("aldi_sued_de", ["https://www.aldi-sued.de/de/angebote.html",
                                        "https://www.aldi-sued.de/angebote"], aldi_sued_kaart)


KAUFLAND_NONFOOD = re.compile(r"elektro|büro|medien|heim, haus|haushalt|bekleidung|auto|freizeit|spiel|black week|garten|baumarkt|multimedia|technik|möbel|deko", re.I)
KAUFLAND_FOOD = re.compile(r"obst|gemüse|fleisch|geflügel|wurst|fisch|molkerei|tiefkühl|feinkost|konserven|grundnahrung|kaffee|tee|süß|knabber|getränke|spirituosen|drogerie|tiernahrung|käse|bäckerei|frische|bio", re.I)


KAUFLAND_LABEL = re.compile(r"^(knüller|topartikel|aktion|neu|black week.*|deal.*|kaufland card.*|xtra.*|nur mit .*|preisknüller|bio|vegan)$", re.I)


def kaufland_kaart(k):
    r = [x for x in _regels(k) if not x.startswith("(") and not KAUFLAND_LABEL.match(x)]
    merk = r[0].title() if r and r[0].isupper() and len(r) > 1 else ""
    if merk:
        r = r[1:]
    titel = r[0] if r else ""
    eenheid = next((x for x in r if x.lower().startswith("je ")), "")
    pct = next((x for x in r if re.fullmatch(r"-?\d{1,2}\s*%", x)), "")
    prijzen = [prijs(x) for x in r if re.fullmatch(r"\d+[.,]\d{2}", x)]
    nu = prijzen[0] if prijzen else None
    was = prijzen[1] if len(prijzen) > 1 else None
    actie = pct or next((x for x in r if ACTIE_RX.search(x) and x not in (titel, eenheid)), "")
    if nu is None and not actie:
        return None                      # kaart nog niet volledig geladen
    sectie = k.get("sectie", "")
    if KAUFLAND_FOOD.search(sectie):
        nonfood = False
    elif KAUFLAND_NONFOOD.search(sectie):
        nonfood = True
    else:
        nonfood = None                      # beslist run.py op basis van de categorie
    return {"titel": f"{merk} {titel}".strip(), "merk": merk, "actie": actie, "prijs_nu": nu, "prijs_was": was,
            "eenheid": eenheid, "img": k.get("img", ""), "url": "https://filiale.kaufland.de/angebote/uebersicht.html",
            "geldig": "", "nonfood": nonfood, "sectie": sectie}


def kaufland():
    return _met_parser("kaufland_de", ["https://filiale.kaufland.de/angebote/uebersicht.html",
                                       "https://www.kaufland.de/angebote/"], kaufland_kaart)


WINKELS = {
    "ah": ("Albert Heijn", "NL", ah),
    "jumbo": ("Jumbo", "NL", jumbo),
    "lidl": ("Lidl", "NL", lidl),
    "aldi": ("Aldi", "NL", aldi),
    "plus": ("PLUS", "NL", plus),
    "aldi_sued": ("Aldi Süd", "DE", aldi_sued),
    "kaufland": ("Kaufland", "DE", kaufland),
}
