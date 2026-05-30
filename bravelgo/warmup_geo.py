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
    pack = pack_for_country(country_code)
    sites = pack["sites"][:]
    random.shuffle(sites)
    return sites[:max_sites]


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
