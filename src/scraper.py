import re
import time
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from src.config import SITE_URL

CSZ_RE = re.compile(r"^(?P<city>.+?),\s*(?P<state>[A-Za-z]{2})\s+(?P<zip>\d{5})")


def _soup(url):
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return BeautifulSoup(r.text, "html.parser")


def scrape_listing():
    """Follow the pager and return one stub per card."""
    url, stubs, seen = f"{SITE_URL}/communities", [], set()
    while url:
        soup = _soup(url)
        for card in soup.select(".card"):
            a = card.select_one("h3 a")
            if not a or a["href"] in seen:
                continue
            seen.add(a["href"])
            stubs.append({
                "url": urljoin(SITE_URL, a["href"]),
                "slug": a["href"].rstrip("/").split("/")[-1],
                "name": a.get_text(strip=True),
                "listing_location": (card.select_one(".city").get_text(strip=True)
                                     if card.select_one(".city") else ""),
                "listing_care": [b.get_text(strip=True) for b in card.select(".badge")],
            })
        nxt = next((a for a in soup.select(".pager a") if "Next" in a.get_text()), None)
        url = urljoin(SITE_URL, nxt["href"]) if nxt else None
        time.sleep(0.2)
    return stubs


def scrape_detail(stub):
    soup = _soup(stub["url"])
    rec = dict(stub)
    h1 = soup.select_one("h1")
    rec["name"] = h1.get_text(strip=True) if h1 else stub["name"]

    fields = {}
    for dt in soup.select("dl.detail dt"):
        dd = dt.find_next_sibling("dd")
        if dd is not None:
            fields[dt.get_text(strip=True).lower()] = dd

    street = city = state = zip_ = ""
    if "address" in fields:
        lines = [l for l in fields["address"].get_text("\n", strip=True).split("\n") if l]
        if lines:
            m = CSZ_RE.match(lines[-1])
            if m:
                city, state, zip_ = m["city"], m["state"].upper(), m["zip"]
                street = ", ".join(lines[:-1])
            else:
                street = ", ".join(lines)  # unparseable: keep raw, don't guess

    rec.update({
        "street": street, "city": city, "state": state, "zip": zip_,
        "care_offerings": [b.get_text(strip=True)
                           for b in fields["care offerings"].select(".badge")]
                          if "care offerings" in fields else [],
        "administrator": fields["administrator"].get_text(strip=True) if "administrator" in fields else "",
        "phone": fields["phone"].get_text(strip=True) if "phone" in fields else "",
        # the CSS defines a .notice box; capture any text in it as evidence
        "notice": " | ".join(n.get_text(" ", strip=True) for n in soup.select(".notice")),
    })
    return rec


def scrape_all():
    stubs = {s["slug"]: s for s in scrape_listing()}
    # pages linked from elsewhere but missing from the listing (e.g. Findlay)
    for path in ["/", "/about", "/communities"]:
        soup = _soup(SITE_URL + path)
        for a in soup.select("a[href^='/communities/']"):
            slug = a["href"].rstrip("/").split("/")[-1]
            if slug and slug not in stubs:
                stubs[slug] = {"url": urljoin(SITE_URL, a["href"]), "slug": slug,
                               "name": a.get_text(strip=True), "listing_location": "",
                               "listing_care": [], "found_via": path}
    out = []
    for s in stubs.values():
        out.append(scrape_detail(s))
        time.sleep(0.2)
    return out