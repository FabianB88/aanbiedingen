"""Generieke browser-scraper: opent een aanbiedingenpagina, wegklikt cookies,
scrolt tot alles geladen is, vangt JSON-verkeer op en haalt productkaarten
uit de pagina. Bewaart ruwe dumps in debug/ zodat parsers per winkel
bijgesteld kunnen worden."""
import json
import os
import re
import time

from playwright.sync_api import sync_playwright

DEBUG = os.path.join(os.path.dirname(__file__), "..", "debug")

COOKIE_WEIGEREN = [
    "Weigeren", "Alles weigeren", "Alleen noodzakelijk", "Alleen functionele cookies",
    "Noodzakelijke cookies", "Ablehnen", "Alle ablehnen", "Nur notwendige",
    "Nur erforderliche", "Nicht zustimmen",
]
COOKIE_ACCEPT = [
    "Accepteren", "Alles accepteren", "Akkoord", "Accepteer", "Prima",
    "Alle akzeptieren", "Akzeptieren", "Zustimmen", "Einverstanden", "OK",
]

# JS dat productkaarten zoekt: elementen met een prijs en een afbeelding,
# zo klein mogelijk gehouden.
KAART_JS = r"""
(cfg) => {
  const prijsRx = /(\d+[.,]\d{2}|\d+[.,]-)/;
  const sel = cfg.selector;
  let kaarten = [];
  if (sel) {
    kaarten = Array.from(document.querySelectorAll(sel));
  } else {
    const kandidaten = new Set();
    const alles = document.querySelectorAll('body *');
    for (const el of alles) {
      if (el.children.length > 0) continue;
      const t = (el.textContent || '').trim();
      if (!t || t.length > 20 || !prijsRx.test(t)) continue;
      let p = el;
      for (let i = 0; i < 9 && p; i++) {
        p = p.parentElement;
        if (!p) break;
        const len = (p.innerText || '').length;
        if (len > 700) break;
        if (p.querySelector('img') && len > 12) { kandidaten.add(p); break; }
      }
    }
    // houd per kaart de binnenste container: gooi kandidaten weg die een andere bevatten
    const lijst = Array.from(kandidaten);
    kaarten = lijst.filter(k => !lijst.some(o => o !== k && k.contains(o)));
  }
  return kaarten.slice(0, 3000).map(k => {
    const img = k.querySelector('img');
    const a = k.closest('a') || k.querySelector('a');
    const attrs = {};
    for (const at of k.attributes) if (at.name.startsWith('data-')) attrs[at.name] = at.value.slice(0, 4000);
    return {
      tekst: (k.innerText || '').trim().slice(0, 700),
      img: img ? (img.currentSrc || img.src || img.getAttribute('data-src') || '') : '',
      alt: img ? (img.alt || '') : '',
      href: a ? a.href : '',
      attrs,
    };
  });
}
"""


def _klik_tekst(page, teksten):
    for t in teksten:
        for loc in (page.get_by_role("button", name=t, exact=True),
                    page.get_by_role("button", name=t),
                    page.get_by_text(t, exact=True)):
            try:
                if loc.count() and loc.first.is_visible():
                    loc.first.click(timeout=2000)
                    return t
            except Exception:
                pass
    return None


def cookies_weg(page):
    time.sleep(1.5)
    geklikt = _klik_tekst(page, COOKIE_WEIGEREN) or _klik_tekst(page, COOKIE_ACCEPT)
    time.sleep(1)
    return geklikt


MEER_KNOPPEN = re.compile(r"^(meer laden|laad meer|toon meer|meer tonen|meer aanbiedingen|bekijk meer aanbiedingen|mehr laden|mehr anzeigen|weitere (angebote|artikel|produkte)( anzeigen| laden)?|alle angebote anzeigen)$", re.I)


def klik_meer(page):
    try:
        knoppen = page.get_by_role("button", name=MEER_KNOPPEN)
        for i in range(knoppen.count()):
            b = knoppen.nth(i)
            if b.is_visible():
                b.click(timeout=2000)
                time.sleep(1.2)
                return True
    except Exception:
        pass
    return False


def scroll_tot_einde(page, max_rondes=60):
    vorige = 0
    stil = 0
    for _ in range(max_rondes):
        page.mouse.wheel(0, 2500)
        time.sleep(0.8)
        if klik_meer(page):
            stil = 0
            continue
        h = page.evaluate("document.body.scrollHeight")
        if h == vorige:
            stil += 1
            if stil >= 3:
                break
        else:
            stil = 0
        vorige = h


def kaarten_lezen(page, selector, wachten=True):
    for poging in range(3):
        try:
            if wachten:
                page.wait_for_load_state("load", timeout=15000)
            return page.evaluate(KAART_JS, {"selector": selector})
        except Exception as e:
            print("   lezen mislukt, opnieuw:", str(e)[:120])
            time.sleep(3)
    return []


def haal(winkel, urls, selector=None, klik_teksten=None, wacht=4, tabs=None, traag=False):
    """Opent de eerste werkende URL en geeft (kaarten, json_responses) terug."""
    os.makedirs(DEBUG, exist_ok=True)
    responses = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL" if not winkel.endswith("_de") else "de-DE",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()

        def op_response(r):
            try:
                ct = r.headers.get("content-type", "")
                if "json" in ct and r.request.resource_type in ("xhr", "fetch"):
                    body = r.text()
                    if len(body) > 200 and re.search(r"price|prijs|preis|promotion|offer|bonus", body, re.I):
                        responses.append({"url": r.url, "body": body[:400000]})
            except Exception:
                pass

        page.on("response", op_response)
        gebruikt = None
        for url in urls:
            try:
                resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
                if resp and resp.status < 400:
                    gebruikt = url
                    break
            except Exception as e:
                print(f"[{winkel}] {url} faalde: {e}")
        if not gebruikt:
            browser.close()
            raise RuntimeError("geen enkele URL bereikbaar")
        time.sleep(wacht)
        print(f"[{winkel}] cookies: {cookies_weg(page)}")
        for t in klik_teksten or []:
            _klik_tekst(page, [t])
            time.sleep(1)
        if traag:
            # rustig scrollen zodat alle tegels hun gegevens laden
            for _ in range(80):
                page.mouse.wheel(0, 700)
                time.sleep(0.5)
        scroll_tot_einde(page)
        kaarten = kaarten_lezen(page, selector)
        if tabs:
            # klik elk tabblad (bijv. "vanaf DO 19/11") en voeg de kaarten toe
            gezien = {k["tekst"] for k in kaarten}
            tab_loc = page.get_by_text(re.compile(tabs, re.I))
            n = tab_loc.count()
            print(f"[{winkel}] {n} tabbladen")
            for i in range(min(n, 8)):
                try:
                    tab_loc.nth(i).scroll_into_view_if_needed(timeout=3000)
                    tab_loc.nth(i).click(timeout=3000)
                    time.sleep(2.5)
                    page.mouse.wheel(0, -100000)
                    scroll_tot_einde(page, 40)
                    for k in kaarten_lezen(page, selector):
                        if k["tekst"] not in gezien:
                            gezien.add(k["tekst"])
                            kaarten.append(k)
                except Exception as e:
                    print(f"[{winkel}] tab {i} faalde: {str(e)[:120]}")
        html = page.content()
        page.screenshot(path=os.path.join(DEBUG, f"{winkel}.png"), full_page=False)
        browser.close()

    with open(os.path.join(DEBUG, f"{winkel}.html"), "w", encoding="utf-8") as f:
        f.write(html[:3_000_000])
    with open(os.path.join(DEBUG, f"{winkel}-kaarten.json"), "w", encoding="utf-8") as f:
        json.dump({"url": gebruikt, "aantal": len(kaarten), "kaarten": kaarten[:400]}, f, ensure_ascii=False, indent=1)
    with open(os.path.join(DEBUG, f"{winkel}-xhr.json"), "w", encoding="utf-8") as f:
        json.dump([{"url": r["url"], "body": r["body"][:60000]} for r in responses[:40]], f, ensure_ascii=False, indent=1)
    return gebruikt, kaarten, responses


def haal_details(winkel, urls, wacht=2.0, max_urls=200, budget_s=480):
    """Bezoekt een reeks detailpagina's in één browser en geeft {url: kaarten} terug.
    De eerste drie pagina's worden als dump bewaard."""
    uit = {}
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
        ctx = browser.new_context(
            locale="nl-NL",
            user_agent=("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"),
            viewport={"width": 1366, "height": 900},
        )
        page = ctx.new_page()
        eerste = True
        begin = time.time()
        for i, url in enumerate(urls[:max_urls]):
            if time.time() - begin > budget_s:
                print(f"[{winkel}] tijdsbudget op na {i} pagina's")
                break
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if eerste:
                    time.sleep(2)
                    cookies_weg(page)
                    eerste = False
                time.sleep(wacht)
                page.mouse.wheel(0, 3000)
                time.sleep(0.8)
                kaarten = kaarten_lezen(page, None, wachten=False)
                uit[url] = kaarten
                if i < 3:
                    with open(os.path.join(DEBUG, f"{winkel}-detail{i}.json"), "w", encoding="utf-8") as f:
                        json.dump({"url": url, "kaarten": kaarten[:60]}, f, ensure_ascii=False, indent=1)
            except Exception as e:
                print(f"[{winkel}] detail {url} faalde: {str(e)[:100]}")
        browser.close()
    return uit
