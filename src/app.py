import json
from flask import Flask, redirect, render_template_string, request, url_for
from src import crm, store

app = Flask(__name__)

PAGE = """
<!doctype html><title>Bellhaven review</title>
<style>
 body{font-family:system-ui;max-width:980px;margin:24px auto;padding:0 16px;color:#222}
 .card{border:1px solid #ddd;border-radius:6px;padding:14px 16px;margin:14px 0}
 .badge{font-size:12px;padding:2px 8px;border-radius:10px;background:#eee;margin-right:6px}
 .low{background:#fde2e2}.medium{background:#fff1cc}.high{background:#dff3e3}
 table{border-collapse:collapse;font-size:13px;width:100%;margin:8px 0}
 td,th{border:1px solid #e5e5e5;padding:4px 6px;text-align:left}
 pre{background:#f6f6f6;padding:8px;font-size:12px;overflow:auto}
 button{padding:6px 14px;margin-right:8px;cursor:pointer}
 .err{color:#b00020}
</style>
<h2>Proposals <small>{{ counts }}</small></h2>
{% if error %}<p class="err">{{ error }}</p>{% endif %}
{% for p in proposals %}
<div class="card">
 <span class="badge {{ p.confidence }}">{{ p.confidence }}</span><span class="badge">{{ p.kind }}</span>
 <b>{{ p.title }}</b>
 <ul>{% for r in p.evidence.reasons %}<li>{{ r }}</li>{% endfor %}</ul>
 {% if p.evidence.website %}<b>Website</b>
 <table><tr><th>Name</th><th>Street</th><th>City</th><th>State</th><th>Zip</th><th>Care</th></tr>
 <tr><td>{{ p.evidence.website.name }}</td><td>{{ p.evidence.website.street }}</td><td>{{ p.evidence.website.city }}</td>
 <td>{{ p.evidence.website.state }}</td><td>{{ p.evidence.website.zip }}</td><td>{{ p.evidence.website.care_offerings|join(', ') }}</td></tr></table>{% endif %}
 <b>CRM</b>
 <table><tr><th>Id</th><th>Name</th><th>Street</th><th>City</th><th>Zip</th><th>Parent</th><th>Status</th><th>Revenue</th><th>AR</th></tr>
 {% for a in p.evidence.crm %}<tr><td>{{ a.id[-6:] }}</td><td>{{ a.name }}</td><td>{{ a.street }}</td><td>{{ a.city }}, {{ a.state }}</td>
 <td>{{ a.zip }}</td><td>{{ a.parent }}</td><td>{{ a.status }}</td><td>{{ a.revenue }}</td><td>{{ a.ar }}</td></tr>{% endfor %}</table>
 <b>Will write</b><pre>{{ p.ops_pretty }}</pre>
 <form method="post" action="{{ url_for('decide', key=p.key) }}">
  <button name="action" value="approve">Approve</button>
  <button name="action" value="reject">Reject</button>
 </form>
</div>
{% else %}<p>No pending proposals.</p>{% endfor %}
"""


@app.route("/")
def index():
    props = store.pending()
    for p in props:
        p["evidence"] = json.loads(p["evidence"])
        p["ops_pretty"] = json.dumps(json.loads(p["ops"]), indent=2)
    return render_template_string(PAGE, proposals=props, counts=store.counts(),
                                  error=request.args.get("error"))


def execute(ops):
    new_id, done = None, []
    for op in ops:
        fields = json.loads(json.dumps(op["fields"]).replace("$new", new_id or "$new"))
        if op["op"] == "create":
            resp = crm.create_account(fields)
            body = resp.get("data", resp)
            new_id = body.get("account_id") or body.get("id")
            if not new_id:
                raise RuntimeError(f"Could not read new account id from: {resp}")
            done.append(f"created {new_id}")
        else:
            crm.update_account(op["account_id"], fields)
            done.append(f"patched {op['account_id']}")
    return "; ".join(done)


@app.route("/decide/<key>", methods=["POST"])
def decide(key):
    p = store.get(key)
    if not p or p["status"] != "pending":
        return redirect(url_for("index"))
    if request.form["action"] == "reject":
        store.decide(key, "rejected")
        return redirect(url_for("index"))
    try:
        result = execute(json.loads(p["ops"]))
        store.decide(key, "approved", result)
        return redirect(url_for("index"))
    except Exception as e:
        return redirect(url_for("index", error=f"{p['title']}: {e}"))