"""Geo-specific warmup URLs and search queries per country profile."""

from __future__ import annotations

# Universal dev sites (same persona: indie Android dev)
DEV_SITES = [
    "https://developer.android.com",
    "https://pub.dev",
    "https://stackoverflow.com",
    "https://github.com",
]

EN_SEARCH_QUERIES = [
    "flutter state management 2024",
    "android app publishing guide",
    "google play console requirements",
    "kotlin coroutines tutorial",
    "firebase android setup",
]

GEO_PACKS: dict[str, dict] = {
    "FR": {
        "google": "https://www.google.fr",
        "sites": [
            "https://www.lemonde.fr",
            "https://www.franceinfo.fr",
            "https://www.lefigaro.fr",
            "https://www.amazon.fr",
            "https://fr.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "météo paris demain",
            "flutter développement android",
            "publier application google play",
            "recette crêpes facile",
            "actualités france",
            "kotlin tutoriel français",
        ],
        "consent": ["Tout accepter", "Accepter tout", "J'accepte", "Accept all"],
        "image_queries": ["tour eiffel paris", "chat mignon", "paysage provence", "voiture sport"],
        "maps_queries": ["café paris", "restaurant lyon", "boulangerie marseille"],
    },
    "US": {
        "google": "https://www.google.com",
        "sites": [
            "https://www.nytimes.com",
            "https://www.reddit.com",
            "https://www.amazon.com",
            "https://en.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": EN_SEARCH_QUERIES
        + [
            "weather new york today",
            "best android emulator linux",
        ],
        "consent": ["Accept all", "I agree", "Accept"],
        "image_queries": ["new york skyline", "cute dog", "coffee aesthetic", "sunset beach"],
        "maps_queries": ["coffee shop brooklyn", "restaurant manhattan", "bookstore seattle"],
    },
    "GB": {
        "google": "https://www.google.co.uk",
        "sites": [
            "https://www.bbc.co.uk",
            "https://www.theguardian.com",
            "https://www.amazon.co.uk",
            "https://en.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "weather london today",
            "flutter android tutorial",
            "publish app google play uk",
            "kotlin android guide",
        ],
        "consent": ["Accept all", "I agree", "Accept"],
        "image_queries": ["london skyline", "british pub", "tea and scones", "countryside uk"],
        "maps_queries": ["coffee shop london", "pub manchester", "cafe edinburgh", "restaurant bristol"],
    },
    "DE": {
        "google": "https://www.google.de",
        "sites": [
            "https://www.spiegel.de",
            "https://www.heise.de",
            "https://www.amazon.de",
            "https://de.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "wetter berlin morgen",
            "flutter android entwicklung",
            "app google play veröffentlichen",
            "kotlin tutorial deutsch",
        ],
        "consent": ["Alle akzeptieren", "Akzeptieren", "Accept all"],
        "image_queries": ["berlin skyline", "schloss neuschwanstein", "brot backen", "auto sport"],
        "maps_queries": ["café berlin", "restaurant münchen", "bäckerei hamburg", "bistro köln"],
    },
    "PL": {
        "google": "https://www.google.pl",
        "sites": [
            "https://www.onet.pl",
            "https://www.wp.pl",
            "https://www.amazon.pl",
            "https://pl.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "pogoda warszawa jutro",
            "publikacja aplikacji android",
            "flutter dokumentacja po polsku",
            "kotlin android poradnik",
        ],
        "consent": ["Zaakceptuj wszystko", "Akceptuję", "Accept all"],
        "image_queries": ["warszawa panorama", "góry tatry", "kot w oknie", "jedzenie polskie"],
        "maps_queries": ["kawiarnia warszawa", "restauracja kraków", "piekarnia gdańsk"],
    },
    "IT": {
        "google": "https://www.google.it",
        "sites": [
            "https://www.repubblica.it",
            "https://www.corriere.it",
            "https://www.amazon.it",
            "https://it.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "meteo roma domani",
            "flutter sviluppo android",
            "pubblicare app google play",
        ],
        "consent": ["Accetta tutto", "Accetto", "Accept all"],
        "image_queries": ["colosseo roma", "costiera amalfitana", "pizza napoletana", "auto rossa"],
        "maps_queries": ["caffè roma", "ristorante milano", "pizzeria napoli", "bar torino"],
    },
    "NL": {
        "google": "https://www.google.nl",
        "sites": [
            "https://www.nu.nl",
            "https://www.amazon.nl",
            "https://nl.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "weer amsterdam morgen",
            "flutter android tutorial",
            "app publiceren google play",
        ],
        "consent": ["Alles accepteren", "Accept all"],
        "image_queries": ["amsterdam grachten", "tulpen veld", "fiets nederland", "stroopwafel"],
        "maps_queries": ["café amsterdam", "restaurant rotterdam", "bakkerij utrecht", "koffiebar den haag"],
    },
    "ES": {
        "google": "https://www.google.es",
        "sites": [
            "https://elpais.com",
            "https://www.amazon.es",
            "https://es.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "tiempo madrid mañana",
            "flutter desarrollo android",
            "publicar app google play",
        ],
        "consent": ["Aceptar todo", "Accept all"],
        "image_queries": ["sagrada familia", "playa barcelona", "paella valenciana", "flamenco"],
        "maps_queries": ["café madrid", "restaurante barcelona", "panadería sevilla"],
    },
    "BR": {
        "google": "https://www.google.com.br",
        "sites": [
            "https://www.uol.com.br",
            "https://www.amazon.com.br",
            "https://pt.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "tempo são paulo amanhã",
            "flutter desenvolvimento android",
            "publicar app google play",
        ],
        "consent": ["Aceitar tudo", "Accept all"],
        "image_queries": ["rio de janeiro praia", "são paulo skyline", "café brasil", "natureza"],
        "maps_queries": ["café são paulo", "restaurante rio de janeiro", "padaria curitiba"],
    },
    "NO": {
        "google": "https://www.google.no",
        "sites": [
            "https://www.nrk.no",
            "https://www.amazon.com",
            "https://no.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "vær oslo i morgen",
            "flutter android utvikling",
            "publisere app google play",
        ],
        "consent": ["Godta alle", "Accept all"],
        "image_queries": ["oslo fjord", "norsk natur", "kaffe oslo", "nordlys"],
        "maps_queries": ["kafé oslo", "restaurant bergen", "bakeri trondheim"],
    },
    "UA": {
        "google": "https://www.google.com.ua",
        "sites": [
            "https://www.pravda.com.ua",
            "https://uk.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "погода київ завтра",
            "flutter android розробка",
            "опублікувати додаток google play",
        ],
        "consent": ["Прийняти все", "Accept all"],
        "image_queries": ["київ панорама", "карпати гори", "українська їжа", "котик"],
        "maps_queries": ["кафе київ", "ресторан львів", "пекарня одеса"],
    },
    "NZ": {
        "google": "https://www.google.co.nz",
        "sites": [
            "https://www.stuff.co.nz",
            "https://www.nzherald.co.nz",
            "https://www.trademe.co.nz",
            "https://en.wikipedia.org",
            "https://www.youtube.com",
            *DEV_SITES,
        ],
        "queries": [
            "weather auckland tomorrow",
            "flutter android development",
            "publish app google play",
        ],
        "consent": ["Accept all", "I agree"],
        "image_queries": ["auckland skyline", "milford sound", "sheep farm nz", "flat white coffee"],
        "maps_queries": ["cafe auckland", "restaurant wellington", "bakery christchurch", "coffee shop queenstown"],
    },
}


def pack_for_country(country_code: str) -> dict:
    return GEO_PACKS.get(country_code.upper(), GEO_PACKS["US"])


def pick_queries(country_code: str, lang_mode: str) -> list[str]:
    """lang_mode: geo | en | mixed"""
    pack = pack_for_country(country_code)
    local = pack["queries"]
    if lang_mode == "en":
        return list(EN_SEARCH_QUERIES)
    if lang_mode == "mixed":
        import random
        pool = list(local)
        pool.extend(random.sample(EN_SEARCH_QUERIES, min(2, len(EN_SEARCH_QUERIES))))
        return pool
    return list(local)


def pick_sites(country_code: str, max_sites: int) -> list[str]:
    import random
    from bravelgo.warmup_sites import extended_sites_for_country

    pool = extended_sites_for_country(country_code)
    random.shuffle(pool)
    return pool[:max_sites] if max_sites > 0 else pool


def site_pool_size(country_code: str) -> int:
    from bravelgo.warmup_sites import extended_sites_for_country

    return len(extended_sites_for_country(country_code))


def google_url(country_code: str) -> str:
    return pack_for_country(country_code)["google"]


def consent_labels(country_code: str) -> list[str]:
    pack = pack_for_country(country_code)
    return pack.get("consent", ["Accept all", "I agree"])


def pick_image_query(country_code: str) -> str:
    import random
    pack = pack_for_country(country_code)
    pool = pack.get("image_queries") or pack["queries"][:4] or ["landscape photo"]
    return random.choice(pool)


def pick_maps_query(country_code: str) -> str:
    import random
    pack = pack_for_country(country_code)
    pool = pack.get("maps_queries") or ["coffee shop", "restaurant", "bakery"]
    return random.choice(pool)


def maps_search_url(country_code: str, query: str) -> str:
    from urllib.parse import quote_plus

    host = google_url(country_code).replace("https://", "").split("/")[0]
    return f"https://{host}/maps/search/{quote_plus(query)}"
