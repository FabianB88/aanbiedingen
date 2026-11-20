"""Eenvoudige categorie-indeling op trefwoorden (NL + DE)."""
import re

CATEGORIEEN = [
    ("Brood & bakkerij", r"brood|brot|brötchen|broodje|bolletje|croissant|bollen|stokbrood|baguette|beschuit|crackers|ontbijtkoek|krentenbol|taart|kuchen|gebak|cake|muffin|donut|wrap|tortilla|pita|toast"),
    ("Bier & wijn", r"merlot|chardonnay|sauvignon|cabernet|shiraz|rosé|riesling|glühwein|bier|pils|wijn|wein|prosecco|cava|champagne|whisky|wodka|vodka|rum|gin|likeur|likör|radler|heineken|grolsch|amstel|hertog jan|jupiler|bavaria|warsteiner|krombacher|bitburger"),
    ("Dranken", r"cola|frisdrank|sap|saft|limonade|water|wasser|thee|tee|koffie|kaffee|senseo|nespresso|dolce gusto|ice tea|energy|red bull|smoothie|siroop|chocomel|fristi|spa |sprite|fanta|pepsi|7up|tonic"),
    ("Groente & fruit", r"appel|apfel|peer|birne|banaan|banane|sinaasappel|orange|mandarijn|druif|traube|aardbei|erdbeer|bes|beeren|mango|ananas|meloen|melone|kiwi|citroen|zitrone|avocado|tomaat|tomate|komkommer|gurke|paprika|ui|zwiebel|wortel|möhre|karotte|broccoli|bloemkool|blumenkohl|sla|salat|spinazie|spinat|champignon|pilz|courgette|zucchini|aardappel|kartoffel|spruit|rosenkohl|pompoen|kürbis|sellerie|selderij|kaki|lauch|peren|mandarine|clementine|sinaasappels|bataat|zoete aardappel|ui |uien|knoflook|groente|gemüse|fruit|obst|prei|lauch|kool|kohl|bonen|asperge|spargel"),
    ("Vlees & vis", r"vlees|fleisch|kip|hähnchen|huhn|kipfilet|gehakt|hack|rund|rind|varken|schwein|schnitzel|worst|wurst|braadworst|bratwurst|ham|schinken|spek|speck|bacon|biefstuk|steak|filet|burger|shoarma|döner|zalm|lachs|vis|fisch|garnaal|garnele|kabeljau|pute|gyros|gulasch|geschnetzelt|hackfleisch|kotelett|beenham|kipgyros|hähnchen|tonijn|thunfisch|kibbeling|lekkerbek|salami|kipburger|slavink|rookworst|frikandel|kroket"),
    ("Zuivel & eieren", r"melk|milch|yoghurt|joghurt|kwark|quark|vla|pudding|kaas|käse|boter|butter|room|sahne|eieren|eier|margarine|skyr|schnittkäse|frischkäse|mozzarella|burrata|babybel|feta|parmigiano|parmezaan|brie|camembert|gouda|zuivel|creme fraiche|crème"),
    ("Diepvries", r"diepvries|tiefkühl|ijs|eis |magnum|ben & jerry|pizza|friet|pommes|frites|kroketten|loempia|bitterbal"),
    ("Snoep & snacks", r"chips|snoep|süßigkeit|chocola|schokolade|koek|keks|biscuit|drop|lakritz|noten|nüsse|pinda|erdnuss|haselnuss|mandeln|walnuss|cashew|popcorn|reep|riegel|haribo|m&m|snickers|twix|lay's|doritos|pringles|tony|milka|verkade|tuc|liga|snack|bonbon"),
    ("Voorraad", r"olijfolie|olijf|pasta|spaghetti|macaroni|nudel|rijst|reis|saus|soße|sauce|soep|suppe|olie|öl|azijn|essig|meel|mehl|suiker|zucker|pindakaas|jam|konfitüre|hagelslag|nutella|honing|honig|kruiden|gewürz|bouillon|conserven|dose|ketchup|mayonaise|mayonnaise|mosterd|senf|muesli|müsli|cornflakes|havermout|cruesli|ontbijtgranen|noedels|curry|wereldkeuken|calvé|conimex|knorr|maggi|unox|grand italia|bertolli"),
    ("Huishouden", r"wasmiddel|waschmittel|vaatwas|spülmaschine|afwas|spülmittel|toiletpapier|toilettenpapier|keukenrol|küchenrolle|schoonmaak|reiniger|vuilniszak|müllbeutel|wasverzachter|weichspüler|ariel|persil|dreft|robijn|omo|finish|sun |glorix|wc-|batterij|batterie|kaars|kerze|aluminiumfolie|vershoudfolie|tissues|zakdoek"),
    ("Verzorging", r"shampoo|douche|dusche|zeep|seife|deo|deodorant|tandpasta|zahnpasta|tandenborstel|zahnbürste|scheer|rasier|luier|windel|maandverband|crème|creme|lotion|nivea|dove|axe|gillette|pampers|andrélon|elvital|zonnebrand|sonnencreme|make-up|parfum|lippen|haarverf|wattenschijf"),
    ("Dier", r"kattenvoer|katzenfutter|hondenvoer|hundefutter|whiskas|felix|sheba|pedigree|kattenbak|katzenstreu|dieren"),
]

def _rx(patroon):
    # lange woorden mogen ook midden in een samenstelling staan (koffiebroodjes),
    # korte alleen aan het begin van een woord (ui, sap, ijs)
    delen = patroon.split("|")
    lang = [d for d in delen if len(d.strip()) >= 5]
    kort = [d for d in delen if len(d.strip()) < 5]
    stukken = []
    if lang:
        stukken.append("(" + "|".join(lang) + ")")
    if kort:
        stukken.append(r"(?<![a-zäöüß])(" + "|".join(kort) + ")")
    return re.compile("|".join(stukken), re.I)


_COMPILED = [(naam, _rx(patroon)) for naam, patroon in CATEGORIEEN]


def categorie(titel, hint=""):
    tekst = f"{titel} {hint or ''}".lower()
    for naam, rx in _COMPILED:
        if rx.search(tekst):
            return naam
    return "Overig"
