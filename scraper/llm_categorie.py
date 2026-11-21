"""Vaste categorie-indeling per producttitel.

data/categorie-cache.json bevat titels die met de hand (door Claude) zijn
ingedeeld. Staat een titel erin, dan wint die indeling; anders blijft de
winkelcategorie of de trefwoord-indeling staan. Nieuwe titels kunnen later
worden aangevuld: zie ontbrekend() hieronder."""
import json
import os

CACHE = os.path.join(os.path.dirname(__file__), "..", "data", "categorie-cache.json")
ONTBREKEND = os.path.join(os.path.dirname(__file__), "..", "data", "categorie-ontbrekend.json")


def sleutel(a):
    return f"{a.get('merk', '')} {a['titel']}".strip().lower()


def deel_in(items):
    try:
        with open(CACHE, encoding="utf-8") as f:
            cache = json.load(f)
    except Exception:
        cache = {}
    ontbreekt = set()
    for a in items:
        cat = cache.get(sleutel(a))
        if cat:
            a["categorie"] = cat
            if cat == "Non-food" and a["winkel"] == "kaufland":
                a["nonfood"] = True
        elif not (a["winkel"] == "ah" and a["categorie"] != "Overig"):
            ontbreekt.add(sleutel(a))
    # lijst van nog niet ingedeelde titels, om later aan te vullen
    with open(ONTBREKEND, "w", encoding="utf-8") as f:
        json.dump(sorted(ontbreekt), f, ensure_ascii=False, indent=0)
    print(f"[categorie] {len(cache)} vaste indelingen, {len(ontbreekt)} titels nog zonder")
