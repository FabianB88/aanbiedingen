"""Categorieën voor non-food en Black Friday (andere indeling dan boodschappen)."""
import re

NF_CATEGORIEEN = [
    ("Tv & audio", r"\btv\b|televisie|fernseher|soundbar|speaker|lautsprecher|koptelefoon|kopfhörer|headphone|earbuds|in-ear|oordopjes|beamer|projector|hifi|radio|versterker"),
    ("Computers & telefoons", r"laptop|notebook|computer|\bpc\b|monitor|tablet|ipad|iphone|smartphone|telefoon|handy|galaxy|pixel|macbook|ssd|router|printer|drucker|toetsenbord|tastatur|muis\b|maus\b|smartwatch|powerbank|usb|lader|ladegerät|kabel|webcam|e-reader|kindle"),
    ("Spelcomputers & games", r"playstation|ps5|ps4|xbox|nintendo|switch|game\b|games\b|controller|gaming"),
    ("Keukenapparaten", r"airfryer|heißluft|heteluchtfriteuse|koffiemachine|kaffeemaschine|kaffeevollautomat|espresso|senseo|nespresso|blender|smoothie|mixer|stabmixer|keukenmachine|küchenmaschine|waterkoker|wasserkocher|magnetron|mikrowelle|broodrooster|toaster|grill|tosti|frituur|fritteuse|slowcooker|multicooker|thermomix|vacuüm|sous.vide|waffel"),
    ("Huishoudapparaten", r"stofzuiger|staubsauger|robotstofzuiger|saugroboter|wasmachine|waschmaschine|droger|trockner|vaatwasser|geschirrspüler|strijkijzer|bügel|stoomreiniger|dampf|luchtontvochtiger|luftentfeuchter|luchtreiniger|ventilator|kachel|heizlüfter|koelkast|kühlschrank|vriezer|gefrier|mop|wischer"),
    ("Gereedschap & tuin", r"parkside|boormachine|bohr|schroef|schraub|accu|akku|zaag|säge|slijp|schleif|gereedschap|werkzeug|hogedrukreiniger|hochdruck|tuin|garten|grasmaaier|rasenmäher|heggen|hecken|ladder|leiter|werkbank|compressor|kompressor|lasapparaat|multimeter|tochtstrip|bouwlamp|my project"),
    ("Speelgoed", r"lego|playmobil|barbie|speelgoed|spielzeug|spielset|puzzel|puzzle|knuffel|plüsch|pop\b|puppe|hot wheels|nerf|vtech|paw patrol|bouwset|bauset|rennbahn|carrera|spel\b|kartenspiel|uno\b|bastelset|mikroskop|drone|quadrocopter"),
    ("Kleding & schoenen", r"jas\b|jacke|jacket|trui|pullover|hoodie|shirt|broek|hose|jeans|jurk|kleid|sokken|socken|schoen|schuh|sneaker|laars|stiefel|pantoffel|pyjama|badjas|bademantel|ondergoed|boxershort|bh\b|legging|vest|muts|mütze|handschoen|sjaal|thermo|fleece|rucksack|rugzak|tas\b|tasche|trolley|koffer"),
    ("Verzorging & gezondheid", r"scheerapparaat|rasierer|trimmer|haardroger|haartrockner|föhn|stijltang|krultang|epilator|epilierer|tandenborstel|zahnbürste|sonicare|oral-b|weegschaal|waage|bloeddruk|massage|parfum|parfüm|make-up|haarschneider|bodygroomer|ladyshave"),
    ("Sport & vrije tijd", r"fiets|fahrrad|e-bike|step|scooter|fitness|hometrainer|loopband|halter|yoga|tent|kamperen|camping|ski|snowboard|schaats|sport|wandel"),
    ("Auto", r"auto\b|kfz|ruitenwisser|scheibenwischer|ijskrabber|eiskratzer|starthilfe|kofferraum|autostoel|sitzerhöhung|frostschutz|enteiser|dashcam|garage"),
    ("Wonen & kerst", r"kerst|weihnacht|kerstboom|christbaum|verlichting|lamp|leuchte|led|kaars|kerze|kussen|kissen|deken|decke|dekbed|bettwäsche|matras|matratze|handdoek|handtuch|gordijn|vorhang|vloerkleed|teppich|decoratie|deko|servies|geschirr|bestek|besteck|pan\b|pfanne|topf|kookpan|glazen|tafelkleed|klok|uhr|spiegel|meubel|möbel|kast|regal|stoel|stuhl|tafel|tisch|bank\b|sofa|badmat|badematte|isolierflasche|thermosfles|opslag|aufbewahrung"),
]
_RX = [(n, re.compile(p, re.I)) for n, p in NF_CATEGORIEEN]
NAMEN = [n for n, _ in NF_CATEGORIEEN] + ["Overig"]


def nf_categorie(titel, hint=""):
    tekst = f"{titel} {hint}".lower()
    for naam, rx in _RX:
        if rx.search(tekst):
            return naam
    return "Overig"
