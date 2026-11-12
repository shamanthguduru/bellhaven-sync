import requests
from src.config import CRM_BASE, HEADERS

BELLHAVEN_PARENT_ID = "0015QAPLGS3FVYEEEM"


def get_all_accounts():
    accounts, page = [], 1
    while True:
        r = requests.get(
            f"{CRM_BASE}/accounts",
            headers=HEADERS,
            params={"page": page, "page_size": 50},
            timeout=30,
        )
        r.raise_for_status()
        body = r.json()
        accounts.extend(body["data"])
        if len(accounts) >= body["total"] or not body["data"]:
            break
        page += 1
    return accounts


def update_account(account_id, fields):
    r = requests.patch(
        f"{CRM_BASE}/accounts/{account_id}",
        headers=HEADERS,
        json=fields,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def create_account(fields):
    r = requests.post(
        f"{CRM_BASE}/accounts",
        headers=HEADERS,
        json=fields,
        timeout=30,
    )
    r.raise_for_status()
    return r.json()