"""Zet een actietekst (+ eventueel prijzen) om naar een kortingspercentage.

Alles komt uit op één getal: het percentage dat je bespaart per stuk,
uitgaande van dat je de actie volledig benut (1+1 = 50%).
"""
import re

PRIJS = r"(\d+)[.,](\d{2})|(\d+)[.,]-"


def prijs(tekst):
    """Eerste bedrag in een tekst als float, of None."""
    if tekst is None:
        return None
    if isinstance(tekst, (int, float)):
        return float(tekst)
    m = re.search(r"(\d+)[.,](\d{2})(?!\d)", str(tekst))
    if m:
        return float(f"{m.group(1)}.{m.group(2)}")
    m = re.search(r"(\d+)[.,]-", str(tekst))
    if m:
        return float(m.group(1))
    return None


def _n(woord):
    woorden = {"twee": 2, "drie": 3, "vier": 4, "vijf": 5, "zes": 6,
               "zwei": 2, "drei": 3, "vier ": 4}
    return int(woord) if woord.isdigit() else woorden.get(woord.lower())


def bereken(actie="", prijs_nu=None, prijs_was=None):
    """Geeft (percentage, 'tot'-vlag) terug. percentage is None als het
    niet te bepalen is."""
    t = (actie or "").lower().replace(" ", " ")
    t = re.sub(r"\s+", " ", t)
    tot = bool(re.search(r"\btot( wel)?\b|\bbis zu\b", t))

    # 1+1 gratis, 2+1 gratis, 3+2 gratis
    m = re.search(r"(\d+)\s*\+\s*(\d+)\s*(gratis|kostenlos|umsonst)?", t)
    if m and (m.group(3) or "gratis" in t or "+" in t and "%" not in t):
        a, b = int(m.group(1)), int(m.group(2))
        if 0 < b <= a * 3:
            return round(100 * b / (a + b)), tot

    # 2e halve prijs / 2e gratis / 2e voor €1
    m = re.search(r"(\d+)\s*(e|de|ste)\s+(halve prijs|gratis|voor)", t)
    if m:
        n = int(m.group(1))
        if "halve" in m.group(3):
            return round(100 * 0.5 / n), tot
        if "gratis" in m.group(3):
            return round(100 / n), tot
    if re.search(r"2\.?\s*(artikel|st(ü|ue)ck)\s*(gratis|geschenkt)", t):
        return 50, tot
    if re.search(r"2\.?\s*(artikel|st(ü|ue)ck)\s*(-?\s*50\s*%|zum halben preis)", t):
        return 25, tot

    # expliciet percentage: "30% korting", "-30%", "25% voordeel"
    m = re.search(r"(\d{1,2})\s*%", t)
    if m:
        p = int(m.group(1))
        if 0 < p < 100:
            return p, tot

    # "2 voor 5,00" / "3 für 4,99"
    m = re.search(r"(\d+|twee|drie|vier|vijf|zwei|drei)\s*(voor|für|fur|stuks voor)\s*€?\s*(\d+[.,]\d{2}|\d+[.,]-|\d+)", t)
    if m and prijs_was:
        n = _n(m.group(1))
        totaal = prijs(m.group(3)) or (float(m.group(3)) if m.group(3).isdigit() else None)
        if n and totaal and prijs_was > 0:
            p = round(100 * (1 - totaal / (n * prijs_was)))
            if 0 < p < 100:
                return p, tot

    # "€1 korting"
    m = re.search(r"(\d+[.,]\d{2}|\d+)\s*(euro)?\s*korting", t)
    if m and prijs_was:
        k = prijs(m.group(1)) or float(m.group(1))
        p = round(100 * k / prijs_was)
        if 0 < p < 100:
            return p, tot

    # oude en nieuwe prijs bekend
    if prijs_nu and prijs_was and prijs_was > prijs_nu > 0:
        return round(100 * (1 - prijs_nu / prijs_was)), tot

    return None, tot


if __name__ == "__main__":
    tests = [
        ("1+1 gratis", None, None, 50),
        ("2+1 gratis", None, None, 33),
        ("2e halve prijs", None, None, 25),
        ("2e gratis", None, None, 50),
        ("25% korting", None, None, 25),
        ("-30%", None, None, 30),
        ("2 voor 5,00", None, 3.29, 24),
        ("", 2.49, 3.29, 24),
        ("tot wel 40% korting", None, None, 40),
        ("1+1 GRATIS", None, None, 50),
        ("3 für 4,99", None, 2.29, 27),
        ("€1 korting", None, 4.00, 25),
        ("Nu voor 1,99", None, None, None),
    ]
    for actie, nu, was, verwacht in tests:
        p, tot = bereken(actie, nu, was)
        status = "ok " if p == verwacht else "FOUT"
        print(status, repr(actie), nu, was, "->", p, "tot" if tot else "")
