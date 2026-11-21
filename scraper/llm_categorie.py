"""Categorie-indeling via een taalmodel (GitHub Models, gratis met GITHUB_TOKEN).

Werkt met een cache op titel, zodat alleen nieuwe producten worden ingedeeld.
Lukt de aanroep niet, dan blijft de trefwoord-indeling staan."""
import json
import os
import re
import time

import requests

from categorie import NAMEN

ENDPOINT = "https://models.github.ai/inference/chat/completions"
MODEL = "openai/gpt-4o-mini"
CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "categorie-cache.json")
BATCH = 80

PROMPT = """Deel supermarktproducten in. Kies voor elk product precies één categorie uit deze lijst:
{namen}

Regels:
- Kijk naar wat het product IS, niet naar een smaak of ingrediënt. "Kip noodles" is een pakje noodles (Voorraad), "Paprikachips" is Snoep & snacks, "Kipsalade" is Maaltijden & salades.
- Vleeswaren (ham, salami, worst voor op brood) horen bij Vlees & vis.
- Kant-en-klaarmaaltijden, verse salades, soepen in bakjes: Maaltijden & salades.
- Vleesvervangers en plantaardige producten: Vegetarisch.
- Producten zonder eetbare inhoud (batterijen, kleding, gereedschap, elektronica, speelgoed, decoratie): Non-food.
- Titels kunnen Nederlands of Duits zijn.

Antwoord alleen met JSON: een object met het nummer van het product als sleutel en de categorie als waarde.

Producten:
{lijst}"""


def _laad():
    try:
        with open(CACHE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _bewaar(cache):
    with open(CACHE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, separators=(",", ":"))


def sleutel(a):
    return f"{a.get('merk', '')} {a['titel']}".strip().lower()


def deel_in(items):
    """Zet a['categorie'] voor alle items; nieuwe titels gaan in batches naar het model."""
    token = os.environ.get("GITHUB_TOKEN")
    cache = _laad()
    nieuw = list(dict.fromkeys(sleutel(a) for a in items if sleutel(a) not in cache))
    print(f"[categorie] {len(nieuw)} nieuwe titels, {len(cache)} in cache")
    if token and nieuw:
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json",
                   "Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
        for i in range(0, len(nieuw), BATCH):
            deel = nieuw[i:i + BATCH]
            lijst = "\n".join(f"{n}. {t}" for n, t in enumerate(deel))
            body = {"model": MODEL, "temperature": 0,
                    "messages": [{"role": "user", "content": PROMPT.format(namen=", ".join(NAMEN), lijst=lijst)}]}
            try:
                r = requests.post(ENDPOINT, headers=headers, json=body, timeout=90)
                if r.status_code == 429:
                    print("[categorie] limiet bereikt, rest volgende run")
                    break
                if r.status_code != 200 or not r.text.strip().startswith("{"):
                    print(f"[categorie] status {r.status_code}: {r.text[:300]!r}")
                    if r.status_code in (401, 403, 404):
                        break
                    continue
                inhoud = r.json()["choices"][0]["message"]["content"]
                m = re.search(r"\{.*\}", inhoud, re.S)
                antwoord = json.loads(m.group(0)) if m else {}
                for n, cat in antwoord.items():
                    if n.isdigit() and int(n) < len(deel) and cat in NAMEN:
                        cache[deel[int(n)]] = cat
            except Exception as e:
                print(f"[categorie] batch {i // BATCH} faalde: {str(e)[:200]}")
                if "401" in str(e) or "403" in str(e):
                    break
            time.sleep(4)
        _bewaar(cache)
    for a in items:
        cat = cache.get(sleutel(a))
        if cat:
            a["categorie"] = cat
            if cat == "Non-food" and a["winkel"] == "kaufland":
                a["nonfood"] = True
