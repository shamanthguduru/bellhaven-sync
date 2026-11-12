import hashlib, json, re
from rapidfuzz import fuzz
from src.crm import BELLHAVEN_PARENT_ID as BH

MAP = {"northwest": "nw", "northeast": "ne", "southwest": "sw", "southeast": "se",
       "north": "n", "south": "s", "east": "e", "west": "w", "street": "st", "avenue": "ave",
       "road": "rd", "drive": "dr", "lane": "ln", "boulevard": "blvd", "court": "ct",
       "place": "pl", "pk": "pike", "highway": "hwy"}
CARE = {"assisted living": "Assisted Living", "memory support": "Memory Care",
        "memory care": "Memory Care", "skilled nursing": "Skilled Nursing",
        "short-term rehabilitation & nursing": "Skilled Nursing",
        "independent living": "Independent Living"}


def norm_street(s):
    s = re.sub(r"[^a-z0-9 ]", " ", (s or "").lower())
    return " ".join(MAP.get(w, w) for w in s.split())


def zip5(z):
    return re.sub(r"\D", "", z or "")[:5]


def norm_name(s):
    s = (s or "").lower().replace("&", " and ").replace("health care", "healthcare")
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    m = {"rehabilitation": "rehab", "centre": "center"}
    return " ".join(m.get(w, w) for w in s.split() if w not in ("the", "at", "of"))


def core_name(s):
    return " ".join(w for w in norm_name(s).split() if w != "bellhaven")


def billed_both(a):
    return (a["lifetime_revenue"] or 0) > 0 and (a["outstanding_ar"] or 0) > 0


def summ(a):
    return {"id": a["account_id"], "name": a["name"], "street": a["billing_street"],
            "city": a["billing_city"], "state": a["billing_state"], "zip": a["billing_zip"],
            "parent": a["parent_name"] or "-", "status": a["status"],
            "revenue": a["lifetime_revenue"], "ar": a["outstanding_ar"]}


def make_key(kind, ops):
    return hashlib.sha1(json.dumps([kind, ops], sort_keys=True).encode()).hexdigest()[:16]


def P(kind, title, conf, ops, evidence):
    return {"key": make_key(kind, ops), "kind": kind, "title": title,
            "confidence": conf, "ops": ops, "evidence": evidence}


def ev(l, accts, reasons):
    keys = ("name", "street", "city", "state", "zip", "care_offerings", "phone", "url")
    return {"website": {k: l.get(k) for k in keys} if l else None,
            "crm": [summ(a) for a in accts], "reasons": reasons}


def care_type(l):
    for c in l.get("care_offerings", []):
        if c.lower() in CARE:
            return CARE[c.lower()]
    return ""


def new_fields(l, care=None):
    return {"name": l["name"], "parent_id": BH, "billing_street": l["street"],
            "billing_city": l["city"], "billing_state": l["state"], "billing_zip": l["zip"],
            "care_type": care or care_type(l), "phone": l.get("phone", ""), "status": "Active"}


def tier12(l, pool):
    k = norm_street(l["street"])
    t1 = [a for a in pool if norm_street(a["billing_street"]) == k
          and zip5(a["billing_zip"]) == l["zip"]]
    if t1:
        return t1, 1
    t2 = [a for a in pool if norm_street(a["billing_street"]) == k
          and a["billing_city"].lower() == l["city"].lower()
          and a["billing_state"].upper() == l["state"]]
    return (t2, 2) if t2 else ([], 0)


def tier34(l, pool):
    same = [a for a in pool if a["billing_city"].lower() == l["city"].lower()
            and a["billing_state"].upper() == l["state"]]   # never match across towns
    t3 = [a for a in same if norm_name(a["name"]) == norm_name(l["name"])]
    if t3:
        return t3, 3
    cn = core_name(l["name"])
    ACQUIRED = {BH, "001FJZYHR7MLFMNPLL", "001FWSQ30SFW6S7604", ""}  # Bellhaven, Harborview, Cedar Trail, no parent
    t4 = [a for a in same if (a["parent_id"] or "") in ACQUIRED
          and cn and fuzz.partial_ratio(cn, core_name(a["name"])) >= 85]
    return (t4, 4) if t4 else ([], 0)


def changes(a, l):
    ch = {}
    if a["name"] != l["name"]:
        ch["name"] = l["name"]
    if norm_street(a["billing_street"]) != norm_street(l["street"]):
        ch["billing_street"] = l["street"]
    if a["billing_city"].lower() != l["city"].lower():
        ch["billing_city"] = l["city"]
    if a["billing_state"].upper() != l["state"]:
        ch["billing_state"] = l["state"]
    if zip5(a["billing_zip"]) != l["zip"]:
        ch["billing_zip"] = l["zip"]
    if a["status"] != "Active":
        ch["status"] = "Active"
    if a["parent_id"] != BH:
        ch["parent_id"] = BH
    return ch


def loser_op(x, target):
    if billed_both(x):   # SOP: never mark an account with billing history as a duplicate
        return {"op": "patch", "account_id": x["account_id"],
                "fields": {"chow_current_account": target}}
    return {"op": "patch", "account_id": x["account_id"],
            "fields": {"duplicate_of_account": target, "status": "Inactive"}}


def build_proposals(accounts, locations):
    crm = [a for a in accounts if "(Parent Account)" not in a["name"]]
    # already-decided accounts are out of the pool, which keeps re-runs safe
    live = [a for a in crm if not a["chow_current_account"] and not a["duplicate_of_account"]]
    claimed, matches, props = set(), {}, []

    for l in locations:                                  # pass 1: address
        c, t = tier12(l, live)
        if c:
            matches[l["slug"]] = (c, t)
            claimed |= {a["account_id"] for a in c}
    for l in locations:                                  # pass 2: name, same town only
        if l["slug"] in matches:
            continue
        pool = [a for a in live if a["account_id"] not in claimed]
        c, t = tier34(l, pool)
        if c:
            matches[l["slug"]] = (c, t)
            claimed |= {a["account_id"] for a in c}

    for l in locations:
        cands, tier = matches.get(l["slug"], ([], 0))
        if not cands:
            props.append(P("create", f'Create account: {l["name"]}', "medium",
                           [{"op": "create", "fields": new_fields(l)}],
                           ev(l, [], ["No CRM account at this address or with a similar name in this town"])))
            continue
        cands = sorted(cands, key=lambda a: (not ((a["lifetime_revenue"] or 0) + (a["outstanding_ar"] or 0) > 0),
                                             re.sub(r"\D", "", a["phone"] or "") != re.sub(r"\D", "", l.get("phone", "")),
                                             a["parent_id"] != BH,
                                             a["name"].strip().lower() != l["name"].strip().lower(),
                                             a["status"] != "Active", a["account_id"]))
        s, losers = cands[0], cands[1:]
        ch = changes(s, l)
        conf = {1: "high", 2: "medium", 3: "medium", 4: "low"}[tier]
        why = [f"Matched by tier {tier} (1 = street+zip, 2 = street+city+state, 3 = name+city, 4 = similar name in same town)"]
        if len(cands) > 1:
            why.append(f"{len(cands)} CRM accounts share this location; survivor chosen by billing history, then Bellhaven parent, then exact name")

        if "parent_id" in ch and billed_both(s):
            ops = [{"op": "create", "fields": new_fields(l, care=s["care_type"])},
                   {"op": "patch", "account_id": s["account_id"], "fields": {"chow_current_account": "$new"}}]
            ops += [loser_op(x, "$new") for x in losers]
            why.append("SOP: old account has revenue AND AR > 0, so its parent is NOT changed. New account created under Bellhaven; chow_current_account set on the old one")
            props.append(P("chow_new_account", f'{s["name"]}: CHOW to new account', conf, ops, ev(l, cands, why)))
            continue
        if ch:
            kind = "possible_match" if tier == 4 else ("reparent" if "parent_id" in ch else "fix")
            if tier == 4:
                why.append("Low confidence: street differs from the website. Check before approving")
            props.append(P(kind, f'{s["name"]}: update {", ".join(ch)}', conf,
                           [{"op": "patch", "account_id": s["account_id"], "fields": ch}], ev(l, cands, why)))
        for x in losers:
            props.append(P("duplicate" if not billed_both(x) else "chow_link",
                           f'{x["name"]} ({x["account_id"][-6:]}): duplicate of {s["name"]}', conf,
                           [loser_op(x, s["account_id"])], ev(l, [x, s], why)))

    # Bellhaven-parent accounts whose location is not on the website
    for a in live:
        if (a["account_id"] in claimed or a["parent_id"] != BH
                or a["status"] in ("Inactive", "Needs Review")):
            continue
        key = norm_street(a["billing_street"])
        succ = [b for b in live if key and b["account_id"] != a["account_id"]
                and b["account_id"] not in claimed and b["parent_id"] != BH
                and norm_street(b["billing_street"]) == key
                and zip5(b["billing_zip"]) == zip5(a["billing_zip"])]
        if succ and billed_both(a):
            props.append(P("chow_link", f'{a["name"]}: sold, set chow to {succ[0]["name"]}', "medium",
                           [{"op": "patch", "account_id": a["account_id"],
                             "fields": {"chow_current_account": succ[0]["account_id"]}}],
                           ev(None, [a, succ[0]], ["Not on website; another owner's account exists at the same address. SOP: revenue and AR > 0, so the old account is left as is except chow_current_account"])))
        elif succ:
            props.append(P("duplicate", f'{a["name"]}: sold, duplicate of {succ[0]["name"]}', "medium",
                           [{"op": "patch", "account_id": a["account_id"],
                             "fields": {"duplicate_of_account": succ[0]["account_id"], "status": "Inactive"}}],
                           ev(None, [a, succ[0]], ["Not on website; another owner's account exists at the same address; no billing history"])))
        else:
            props.append(P("not_on_website", f'{a["name"]}: not on website, needs review', "medium",
                           [{"op": "patch", "account_id": a["account_id"],
                             "fields": {"status": "Needs Review",
                                        "note": "Not listed on Bellhaven website; confirm ownership change or closure."}}],
                           ev(None, [a], ["Under Bellhaven in the CRM but absent from the website, with no successor account at the address"])))
    return props