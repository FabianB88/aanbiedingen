# Aanbiedingen

Alle supermarktaanbiedingen uit de buurt van Groesbeek op één pagina, gesorteerd op korting.

- **Winkels:** Albert Heijn, Jumbo, Lidl, Aldi, PLUS (NL), Aldi Süd en Kaufland (DE)
- **Ophalen:** GitHub Action (`.github/workflows/scrape.yml`), elke ochtend en extra rond de folderwissel. Handmatig: Actions → *Aanbiedingen ophalen* → *Run workflow*.
- **Pagina:** `index.html` op GitHub Pages, leest `data/aanbiedingen.json`.
- **Volgen en lijstjes:** opgeslagen in je browser (localStorage), geen account nodig.
- **Korting:** elke actie wordt omgerekend naar één percentage (1+1 = 50%, 2e halve prijs = 25%, enz.), zie `scraper/korting.py`.
- **Debug:** ruwe pagina-dumps per winkel staan in `debug/` om scrapers bij te stellen.
