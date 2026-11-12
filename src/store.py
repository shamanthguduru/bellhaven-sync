import json
import sqlite3

DB = "data/proposals.db"


def conn():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with conn() as c:
        c.execute("""create table if not exists proposals(
            key text primary key, kind text, title text, confidence text,
            ops text, evidence text, status text default 'pending',
            created_at text, decided_at text, result text)""")


def sync(props):
    """Insert new proposals. Existing keys keep their status, so decided items are never re-proposed."""
    init()
    current = {p["key"] for p in props}
    with conn() as c:
        existing = {r["key"]: r["status"] for r in c.execute("select key, status from proposals")}
        new = 0
        for p in props:
            if p["key"] not in existing:
                c.execute("insert into proposals(key, kind, title, confidence, ops, evidence, created_at) "
                          "values(?,?,?,?,?,?,datetime('now'))",
                          (p["key"], p["kind"], p["title"], p["confidence"],
                           json.dumps(p["ops"]), json.dumps(p["evidence"])))
                new += 1
            elif existing[p["key"]] == "stale":
                c.execute("update proposals set status='pending' where key=?", (p["key"],))
        for k, s in existing.items():
            if s == "pending" and k not in current:
                c.execute("update proposals set status='stale' where key=?", (k,))
    return new


def pending():
    order = "case confidence when 'low' then 0 when 'medium' then 1 else 2 end"
    with conn() as c:
        return [dict(r) for r in c.execute(
            f"select * from proposals where status='pending' order by {order}, kind, title")]


def get(key):
    with conn() as c:
        r = c.execute("select * from proposals where key=?", (key,)).fetchone()
        return dict(r) if r else None


def decide(key, status, result=""):
    with conn() as c:
        c.execute("update proposals set status=?, decided_at=datetime('now'), result=? where key=?",
                  (status, result, key))


def counts():
    with conn() as c:
        return {r["status"]: r["n"] for r in
                c.execute("select status, count(*) n from proposals group by status")}