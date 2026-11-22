"""Wekelijks: het vaste Aldi-assortiment (ruim 1700 producten) van aldi.nl/producten
in data/assortiment/aldi.json zetten, in hetzelfde formaat als de Checkjebon-data.
Draait elke maandagnacht via de workflow 'Aldi-assortiment', of handmatig."""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

from assortiment import DOEL, per_eenheid
from browser import KAART_JS, cookies_weg, scroll_tot_einde, DEBUG
from winkels import aldi_kaart

START = "https://www.aldi.nl/producten.html"


def links(page, patroon):
    hrefs = page.eval_on_selector_all("a[href]", "els => els.map(e => e.href)")
    return sorted({h.split("#")[0].split("?")[0] for h in hrefs if re.search(patroon, h)})


def main():
    os.makedirs(DOEL, exist_ok=True)
    rijen, gezien = [], set()
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(locale="nl-NL", viewport={"width": 1366, "height": 900},
                                  user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                              "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"))
        page = ctx.new_page()
        page.goto(START, wait_until="domcontentloaded", timeout=45000)
        time.sleep(3)
        cookies_weg(page)
        categorieen = links(page, r"aldi\.nl/producten/[a-z0-9-]+\.html$")
        print(f"[aldi] {len(categorieen)} categorieën")
        subs = []
        for c in categorieen:
            try:
                page.goto(c, wait_until="domcontentloaded", timeout=45000)
                time.sleep(1.5)
                gevonden = links(page, re.escape(c[:-5]) + r"/[a-z0-9-]+\.html$")
                subs += gevonden or [c]        # geen subcategorieën: de categorie zelf
            except Exception as e:
                print(f"[aldi] {c}: {e}")
        subs = list(dict.fromkeys(subs))
        print(f"[aldi] {len(subs)} subcategorieën")
        for i, url in enumerate(subs):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                time.sleep(1.5)
                scroll_tot_einde(page, 15)
                kaarten = page.evaluate(KAART_JS, {"selector": None})
                n = 0
                for k in kaarten:
                    a = aldi_kaart(k)
                    if not a or not a.get("titel") or not a.get("prijs_nu"):
                        continue
                    sleutel = (a["titel"], a.get("eenheid", ""), a["prijs_nu"])
                    if sleutel in gezien:
                        continue
                    gezien.add(sleutel)
                    naam = f"{a['merk']} {a['titel']}".strip() if a.get("merk") else a["titel"]
                    per, eenh = per_eenheid(a["prijs_nu"], a.get("eenheid", ""), naam)
                    rijen.append([naam, a["prijs_nu"], a.get("eenheid", ""), per, eenh, k.get("href") or url])
                    n += 1
                print(f"[aldi] {i+1}/{len(subs)} {url.rsplit('/', 1)[-1]}: {n}")
                if i < 2:
                    with open(os.path.join(DEBUG, f"aldi-assortiment{i}.json"), "w", encoding="utf-8") as f:
                        json.dump(kaarten[:40], f, ensure_ascii=False, indent=1)
            except Exception as e:
                print(f"[aldi] {url}: {e}")
        browser.close()
    if len(rijen) < 200:
        print(f"[aldi] maar {len(rijen)} producten, niets opgeslagen")
        return
    with open(os.path.join(DOEL, "aldi.json"), "w", encoding="utf-8") as f:
        json.dump(rijen, f, ensure_ascii=False, separators=(",", ":"))
    print(f"[aldi] {len(rijen)} producten opgeslagen")


if __name__ == "__main__":
    main()
