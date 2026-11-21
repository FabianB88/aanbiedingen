"""Tweakers-check voor Black Friday-deals.

Zoekt het product op in de Tweakers Pricewatch en haalt de laagste prijs
nu en de laagste prijs van de afgelopen 90 dagen op. Zo zie je of de
deal echt goedkoper is dan elders en dan eerder.

Resultaten worden per titel bewaard in data/tweakers-cache.json en een
week hergebruikt, zodat elke run maar een beperkt aantal nieuwe producten
opzoekt."""
import datetime as dt
import json
import os
import re
import time
from urllib.parse import quote_plus

import requests

from browser import DEBUG

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "tweakers-cache.json")
MAX_NIEUW = 60          # per run
MIN_PRIJS = 25          # alleen zinvol voor wat duurdere producten
GELDIG_DAGEN = 7

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")


def _sessie():
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": "nl-NL,nl;q=0.9"})
    # DPG-cookiemuur: weigeren van niet-noodzakelijke cookies via de consent-cookie
    s.cookies.set("TnetID", "", domain="tweakers.net")
    return s


def _dump(naam, tekst):
    try:
        with open(os.path.join(DEBUG, f"tweakers-{naam}"), "w", encoding="utf-8") as f:
            f.write(tekst[:300000])
    except Exception:
        pass


def zoek(s, titel, dumpen=False):
    """Geeft (product_id, url) van de eerste Pricewatch-treffer, of (None, None)."""
    r = s.get(f"https://tweakers.net/zoeken/?keyword={quote_plus(titel)}", timeout=30)
    if dumpen:
        _dump("zoek.html", f"<!-- status {r.status_code} url {r.url} -->\n" + r.text)
    m = re.search(r'href="(https://tweakers\.net/pricewatch/(\d+)/[^"]+)"', r.text)
    if not m:
        return None, None
    return m.group(2), m.group(1)


def prijzen(s, pid, url, dumpen=False):
    """Laagste prijs nu en laagste prijs in de afgelopen 90 dagen."""
    nu = laagste90 = None
    r = s.get(url, timeout=30)
    if dumpen:
        _dump("product.html", f"<!-- status {r.status_code} -->\n" + r.text)
    m = re.search(r'"lowPrice"\s*:\s*"?(\d+(?:\.\d+)?)', r.text) or \
        re.search(r'itemprop="lowPrice"\s+content="(\d+(?:\.\d+)?)"', r.text)
    if m:
        nu = float(m.group(1))
    try:
        r2 = s.get(f"https://tweakers.net/ajax/price_chart/{pid}/nl/", timeout=30,
                   headers={"X-Requested-With": "XMLHttpRequest"})
        if dumpen:
            _dump("chart.json", f"status {r2.status_code}\n" + r2.text)
        data = r2.json()
        reeksen = (data.get("dataset") or {}).get("source") or data.get("data") or []
        grens = (dt.date.today() - dt.timedelta(days=90)).isoformat()
        waarden = []
        for rij in reeksen:
            if isinstance(rij, list) and len(rij) >= 2 and str(rij[0]) >= grens:
                for v in rij[1:]:
                    if isinstance(v, (int, float)) and v > 0:
                        waarden.append(float(v))
        if waarden:
            laagste90 = min(waarden)
    except Exception as e:
        print(f"[tweakers] grafiek {pid}: {str(e)[:100]}")
    return nu, laagste90


def check(items):
    """Voegt tw_url, tw_laagste en tw_laagste90 toe aan Black Friday-items."""
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    vandaag = dt.date.today()
    kandidaten = [a for a in items if a.get("bf") and (a.get("prijs_nu") or 0) >= MIN_PRIJS]
    kandidaten.sort(key=lambda a: -(a.get("korting") or 0))
    s = _sessie()
    nieuw = 0
    gedumpt = False
    for a in kandidaten:
        sleutel = a["titel"].lower()
        c = cache.get(sleutel)
        vers = c and (vandaag - dt.date.fromisoformat(c["datum"])).days < GELDIG_DAGEN
        if not vers:
            if nieuw >= MAX_NIEUW:
                continue
            nieuw += 1
            try:
                pid, url = zoek(s, a["titel"], dumpen=not gedumpt)
                nu = l90 = None
                if pid:
                    nu, l90 = prijzen(s, pid, url, dumpen=not gedumpt)
                    gedumpt = True
                c = {"datum": vandaag.isoformat(), "url": url, "laagste": nu, "laagste90": l90}
                cache[sleutel] = c
                time.sleep(1.5)
            except Exception as e:
                print(f"[tweakers] {a['titel'][:40]}: {str(e)[:100]}")
                continue
        if c and c.get("url"):
            a["tw_url"] = c["url"]
            a["tw_laagste"] = c.get("laagste")
            a["tw_laagste90"] = c.get("laagste90")
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))
    gevonden = sum(1 for a in items if a.get("tw_url"))
    print(f"[tweakers] {nieuw} opgezocht, {gevonden} deals met Tweakers-gegevens")
