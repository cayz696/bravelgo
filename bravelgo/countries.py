"""Country profiles — proxy country drives locale/TZ/language."""

COUNTRY_PROFILES = {
    "FR": {
        "name": "France",
        "timezone": "Europe/Paris",
        "locale": "fr_FR.UTF-8",
        "language": "fr-FR",
        "lang_full": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "fr",
        "ff_locale": "fr-FR",
    },
    "US": {
        "name": "United States",
        "timezone": "America/New_York",
        "locale": "en_US.UTF-8",
        "language": "en-US",
        "lang_full": "en-US,en;q=0.9",
        "keyboard": "us",
        "ff_locale": "en-US",
    },
    "GB": {
        "name": "United Kingdom",
        "timezone": "Europe/London",
        "locale": "en_GB.UTF-8",
        "language": "en-GB",
        "lang_full": "en-GB,en;q=0.9,en-US;q=0.8",
        "keyboard": "gb",
        "ff_locale": "en-GB",
    },
    "PL": {
        "name": "Poland",
        "timezone": "Europe/Warsaw",
        "locale": "pl_PL.UTF-8",
        "language": "pl-PL",
        "lang_full": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "pl",
        "ff_locale": "pl-PL",
    },
    "DE": {
        "name": "Germany",
        "timezone": "Europe/Berlin",
        "locale": "de_DE.UTF-8",
        "language": "de-DE",
        "lang_full": "de-DE,de;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "de",
        "ff_locale": "de-DE",
    },
    "IT": {
        "name": "Italy",
        "timezone": "Europe/Rome",
        "locale": "it_IT.UTF-8",
        "language": "it-IT",
        "lang_full": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "it",
        "ff_locale": "it-IT",
    },
    "NL": {
        "name": "Netherlands",
        "timezone": "Europe/Amsterdam",
        "locale": "nl_NL.UTF-8",
        "language": "nl-NL",
        "lang_full": "nl-NL,nl;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "nl",
        "ff_locale": "nl-NL",
    },
    "ES": {
        "name": "Spain",
        "timezone": "Europe/Madrid",
        "locale": "es_ES.UTF-8",
        "language": "es-ES",
        "lang_full": "es-ES,es;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "es",
        "ff_locale": "es-ES",
    },
    "BR": {
        "name": "Brazil",
        "timezone": "America/Sao_Paulo",
        "locale": "pt_BR.UTF-8",
        "language": "pt-BR",
        "lang_full": "pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "br",
        "ff_locale": "pt-BR",
    },
    "NO": {
        "name": "Norway",
        "timezone": "Europe/Oslo",
        "locale": "nb_NO.UTF-8",
        "language": "nb-NO",
        "lang_full": "nb-NO,nb;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "no",
        "ff_locale": "nb-NO",
    },
    "UA": {
        "name": "Ukraine",
        "timezone": "Europe/Kyiv",
        "locale": "uk_UA.UTF-8",
        "language": "uk-UA",
        "lang_full": "uk-UA,uk;q=0.9,en-US;q=0.8,en;q=0.7",
        "keyboard": "ua",
        "ff_locale": "uk-UA",
    },
    "NZ": {
        "name": "New Zealand",
        "timezone": "Pacific/Auckland",
        "locale": "en_NZ.UTF-8",
        "language": "en-NZ",
        "lang_full": "en-NZ,en;q=0.9,en-US;q=0.8",
        "keyboard": "us",
        "ff_locale": "en-NZ",
    },
}

HOST_PREFIX = ("DESKTOP", "LAPTOP", "PC", "WORK", "DEV")
CORES = (2, 4, 4, 4, 8, 8)


def country_profile(country_code: str, timezone_override: str | None = None) -> dict:
    cc = country_code.upper()
    if cc in COUNTRY_PROFILES:
        cp = dict(COUNTRY_PROFILES[cc])
    else:
        cp = {
            "name": cc,
            "timezone": timezone_override or "UTC",
            "locale": "en_US.UTF-8",
            "language": "en-US",
            "lang_full": "en-US,en;q=0.9",
            "keyboard": "us",
            "ff_locale": "en-US",
        }
    if timezone_override:
        cp["timezone"] = timezone_override
    return cp


def generate_fingerprint(country_code: str, timezone_override: str | None = None) -> dict:
    import os
    import random
    import time

    cp = country_profile(country_code, timezone_override)
    random.seed(os.urandom(16))
    suffix = "".join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=5))
    hostname = f"{random.choice(HOST_PREFIX)}-{suffix}"
    random.seed()
    return {
        "country_code": country_code.upper(),
        "country_name": cp["name"],
        "timezone": cp["timezone"],
        "locale": cp["locale"],
        "language": cp["language"],
        "lang_full": cp["lang_full"],
        "keyboard": cp["keyboard"],
        "ff_locale": cp["ff_locale"],
        "cpu_cores": random.choice(CORES),
        "hostname": hostname,
        "generated_at": time.strftime("%Y-%m-%d %H:%M"),
    }


def fingerprint_summary(fp: dict) -> str:
    return (
        f"Country : {fp.get('country_name', '?')} ({fp.get('country_code', '?')})\n"
        f"TZ      : {fp.get('timezone', '?')}\n"
        f"Locale  : {fp.get('locale', '?')}\n"
        f"Lang    : {fp.get('language', '?')}\n"
        f"Host    : {fp.get('hostname', '?')}\n"
        f"Created : {fp.get('generated_at', '?')}"
    )
