"""Large warmup URL pools — merge with geo packs (55+ per country)."""

from __future__ import annotations

# Trusted generic sites (news, tech, shopping, reference) — no login walls
COMMON_POOL: list[str] = [
    "https://www.wikipedia.org",
    "https://www.youtube.com",
    "https://stackoverflow.com",
    "https://github.com",
    "https://developer.android.com",
    "https://pub.dev",
    "https://medium.com",
    "https://www.reddit.com",
    "https://news.ycombinator.com",
    "https://www.bbc.com",
    "https://www.reuters.com",
    "https://techcrunch.com",
    "https://arstechnica.com",
    "https://www.theverge.com",
    "https://9to5google.com",
    "https://android-developers.googleblog.com",
    "https://kotlinlang.org",
    "https://flutter.dev",
    "https://firebase.google.com",
    "https://docs.flutter.dev",
    "https://developer.mozilla.org",
    "https://www.w3schools.com",
    "https://www.imdb.com",
    "https://www.goodreads.com",
    "https://openweathermap.org",
    "https://www.timeanddate.com",
    "https://www.booking.com",
    "https://www.tripadvisor.com",
    "https://www.etsy.com",
    "https://www.ebay.com",
    "https://www.aliexpress.com",
    "https://unsplash.com",
    "https://www.pinterest.com",
    "https://www.quora.com",
    "https://www.linkedin.com",
    "https://www.indeed.com",
    "https://www.glassdoor.com",
    "https://www.khanacademy.org",
    "https://www.coursera.org",
    "https://www.duolingo.com",
    "https://www.spotify.com",
    "https://soundcloud.com",
    "https://www.archdaily.com",
    "https://www.howtogeek.com",
    "https://lifehacker.com",
    "https://www.digitalocean.com/community",
    "https://dev.to",
    "https://gitlab.com/explore",
    "https://bitbucket.org",
    "https://www.producthunt.com",
    "https://www.gsmarena.com",
    "https://www.androidauthority.com",
    "https://www.xda-developers.com",
]

REGION_EXTRA: dict[str, list[str]] = {
    "FR": [
        "https://www.lemonde.fr", "https://www.lefigaro.fr", "https://www.franceinfo.fr",
        "https://www.francetvinfo.fr", "https://www.liberation.fr", "https://www.leparisien.fr",
        "https://www.20minutes.fr", "https://www.bfmtv.com", "https://www.cnews.fr",
        "https://www.amazon.fr", "https://www.fnac.com", "https://www.leboncoin.fr",
        "https://www.decathlon.fr", "https://www.leroymerlin.fr", "https://www.carrefour.fr",
        "https://www.orange.fr", "https://www.sncf-connect.com", "https://www.vinted.fr",
        "https://fr.wikipedia.org", "https://www.allocine.fr", "https://www.jeuxvideo.com",
    ],
    "NL": [
        "https://www.nu.nl", "https://www.ad.nl", "https://www.telegraaf.nl",
        "https://www.volkskrant.nl", "https://www.nos.nl", "https://www.rtlnieuws.nl",
        "https://www.amazon.nl", "https://www.bol.com", "https://www.coolblue.nl",
        "https://www.marktplaats.nl", "https://www.ah.nl", "https://www.weeronline.nl",
        "https://nl.wikipedia.org", "https://www.ing.nl", "https://www.ns.nl",
        "https://www.rijksoverheid.nl", "https://www.tweedekamer.nl",
    ],
    "DE": [
        "https://www.spiegel.de", "https://www.heise.de", "https://www.zeit.de",
        "https://www.sueddeutsche.de", "https://www.faz.net", "https://www.welt.de",
        "https://www.amazon.de", "https://www.otto.de", "https://www.idealo.de",
        "https://www.mobile.de", "https://de.wikipedia.org", "https://www.tagesschau.de",
    ],
    "GB": [
        "https://www.bbc.co.uk", "https://www.theguardian.com", "https://www.dailymail.co.uk",
        "https://www.independent.co.uk", "https://www.telegraph.co.uk", "https://www.sky.com",
        "https://www.amazon.co.uk", "https://www.argos.co.uk", "https://www.tesco.com",
        "https://en.wikipedia.org", "https://www.gov.uk",
    ],
    "US": [
        "https://www.nytimes.com", "https://www.cnn.com", "https://www.washingtonpost.com",
        "https://www.amazon.com", "https://www.walmart.com", "https://www.target.com",
        "https://www.yelp.com", "https://www.craigslist.org", "https://en.wikipedia.org",
    ],
    "PL": [
        "https://www.onet.pl", "https://www.wp.pl", "https://www.interia.pl",
        "https://www.gazeta.pl", "https://www.amazon.pl", "https://pl.wikipedia.org",
    ],
    "ES": [
        "https://elpais.com", "https://www.elmundo.es", "https://www.amazon.es",
        "https://es.wikipedia.org", "https://www.marca.com",
    ],
    "IT": [
        "https://www.repubblica.it", "https://www.corriere.it", "https://www.amazon.it",
        "https://it.wikipedia.org", "https://www.gazzetta.it",
    ],
    "NZ": [
        "https://www.stuff.co.nz", "https://www.nzherald.co.nz", "https://www.rnz.co.nz",
        "https://www.trademe.co.nz", "https://en.wikipedia.org",
    ],
}


def extended_sites_for_country(country_code: str) -> list[str]:
    """Unique merged pool (geo pack + region + common), typically 55–70 URLs."""
    from bravelgo.warmup_geo import pack_for_country

    pack = pack_for_country(country_code)
    cc = country_code.upper()
    seen: set[str] = set()
    out: list[str] = []
    for url in pack.get("sites", []) + REGION_EXTRA.get(cc, []) + COMMON_POOL:
        u = url.strip().rstrip("/")
        if not u or u in seen:
            continue
        seen.add(u)
        out.append(u)
    return out
