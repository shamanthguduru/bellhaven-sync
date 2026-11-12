# Bellhaven CRM sync

Keeps CRM parent/facility data in line with the Bellhaven Senior Living website.

## How it works
1. `src/scraper.py` scrapes every Bellhaven location (listing pages plus detail pages, including pages linked but not listed).
2. `src/crm.py` pulls all accounts through the API (paginated).
3. `src/matcher.py` matches each location to a CRM account and builds proposals:
   - Tier 1: street + zip. Tier 2: street + city + state. Tier 3: exact name in the same town. Tier 4: similar name in the same town, only among accounts with no parent or an acquired parent (Bellhaven, Harborview, Cedar Trail). Never matches across towns.
   - Proposal kinds: `fix`, `reparent`, `create`, `duplicate`, `chow_new_account`, `chow_link`, `not_on_website`, `possible_match`.
4. `src/store.py` keeps proposals in SQLite (`data/proposals.db`). A proposal's key is a hash of its operations, and decided proposals keep their status, so re-runs never re-propose them.
5. `src/app.py` is the review app. Each proposal shows website and CRM evidence plus the exact write. Nothing is written until Approve.

## SOP: billing history
If an account must move to a different parent and has both `lifetime_revenue` > 0 and `outstanding_ar` > 0, its parent is never changed. The pipeline creates a new account under the correct parent and sets `chow_current_account` on the old one. Otherwise the account is re-parented directly. Accounts with billing history are never marked as duplicates.

## Demo data
`drift.py` simulates stale CRM records (wrong zip, wrong name, wrong parent) so the review flow can be demonstrated on an already-clean CRM.

## Run
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add your CRM token
python -m src.run_pipeline
flask --app src.app run --port 5001
```

## Schedule
`.github/workflows/daily.yml` runs the pipeline daily. It only generates proposals.