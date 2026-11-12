from collections import Counter
from src import crm, scraper, matcher, store


def main():
    accounts = crm.get_all_accounts()
    locations = scraper.scrape_all()
    if len(locations) < 10:   # a site outage must not look like "everything left Bellhaven"
        raise SystemExit(f"Scraper returned only {len(locations)} locations; aborting")
    props = matcher.build_proposals(accounts, locations)
    new = store.sync(props)
    print(f"accounts={len(accounts)} locations={len(locations)} proposals={len(props)} new={new}")
    print(dict(Counter(p["kind"] for p in props)))
    for p in props:
        print(f'[{p["confidence"]:6}] {p["kind"]:16} {p["title"]}')


if __name__ == "__main__":
    main()