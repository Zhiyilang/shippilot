"""Self-contained HTML receipt. No CDN, no fonts, no tracking - it has to open
from a CI artifact folder three weeks later on a machine with no network.
"""

from __future__ import annotations

import html
import json

from .model import STAGES

_COLORS = {"blocker": "#b3261e", "high": "#c9522b", "medium": "#a8791a", "low": "#4a6572"}
_DECISION = {"SHIP": "#1e7d43", "SHIP_WITH_CAVEATS": "#a8791a",
             "HOLD_FOR_HUMAN": "#4a6572", "HELD_BY_HUMAN": "#4a6572", "NO_GO": "#b3261e"}


def e(v):
    return html.escape("" if v is None else str(v), quote=True)


def _stage_grid(receipt):
    cells = []
    for s in STAGES:
        info = receipt["stages"].get(s, {})
        before = info.get("findings_before", 0)
        after = info.get("findings_after", 0)
        if not info.get("ran"):
            bg, label = "#eceff1", "skipped"
        elif after == 0 and before == 0:
            bg, label = "#d7f0dd", "clean"
        elif after == 0:
            bg, label = "#d7f0dd", "fixed %d" % before
        else:
            bg, label = "#fbe3e1", "%d open" % after
        cells.append(
            '<div class="stage" style="background:%s">'
            '<div class="stage-name">%s</div>'
            '<div class="stage-state">%s</div>'
            '<div class="stage-meta">%ss</div></div>' % (bg, e(s), e(label), e(info.get("seconds", 0)))
        )
    return '<div class="grid">%s</div>' % "".join(cells)


def _rows(receipt):
    out = []
    for a in receipt.get("actions", []):
        state = "verified" if a["verified"] else ("rejected" if not a["approved"] else "unresolved")
        badge = {"verified": "#1e7d43", "rejected": "#4a6572", "unresolved": "#b3261e"}[state]
        changes = ", ".join(e(c.get("path")) for c in a.get("changes", [])) or "-"
        err = '<div class="err">%s</div>' % e(a["error"]) if a.get("error") else ""
        out.append(
            "<tr><td><b>%s</b></td><td>%s</td><td>%s</td>"
            '<td><span class="badge" style="background:%s">%s</span></td>'
            "<td>%s</td><td>%s%s</td></tr>"
            % (e(a["rule"]), e(a["stage"]), e(a["severity"]), badge, state, e(a.get("fix")), changes, err)
        )
    if not out:
        out.append('<tr><td colspan="6">No actions proposed.</td></tr>')
    return "".join(out)


def _findings(receipt, key):
    out = []
    for f in receipt.get(key, []):
        loc = "%s:%s" % (f.get("path") or "-", f.get("line") or "-")
        out.append(
            '<tr><td><span class="dot" style="background:%s"></span>%s</td>'
            "<td>%s</td><td>%s</td><td><code>%s</code></td></tr>"
            % (_COLORS.get(f.get("severity"), "#4a6572"), e(f.get("severity")),
               e(f.get("rule")), e(f.get("stage")), e(loc))
        )
    if not out:
        out.append('<tr><td colspan="4">none</td></tr>')
    return "".join(out)


def _carbon(receipt):
    c = receipt.get("carbon") or {}
    m = c.get("measured") or {}
    a = c.get("with_stage_cache") or {}
    b = c.get("with_cache_and_parallelism") or {}
    return (
        '<table class="kv">'
        "<tr><th>Measured build</th><td>%s gCO2e (%ss)</td></tr>"
        "<tr><th>With stage cache</th><td>%s gCO2e &minus;%s%%</td></tr>"
        "<tr><th>Cache + parallelism</th><td>%s gCO2e &minus;%s%%</td></tr>"
        "<tr><th>Method</th><td>%s</td></tr></table>"
        % (e(m.get("total_gco2e")), e(m.get("seconds")),
           e(a.get("total_gco2e")), e(a.get("saved_percent")),
           e(b.get("total_gco2e")), e(b.get("saved_percent")),
           e(c.get("method")))
    )


def render(receipt):
    decision = receipt.get("decision", "")
    color = _DECISION.get(decision, "#4a6572")
    return """<!doctype html>
<meta charset="utf-8">
<title>ShipPilot receipt - %(repo)s</title>
<style>
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;margin:0;padding:32px;
background:#fafafa;color:#1c1e21;line-height:1.5}
h1{margin:0 0 4px;font-size:22px}
h2{margin:28px 0 10px;font-size:15px;text-transform:uppercase;letter-spacing:.06em;color:#5f6368}
.sub{color:#5f6368;font-size:13px;margin-bottom:18px}
.badge{display:inline-block;color:#fff;padding:2px 10px;border-radius:11px;font-size:12px;font-weight:600}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}
.stage{border-radius:8px;padding:12px 14px;box-shadow:0 1px 2px rgba(0,0,0,.08)}
.stage-name{font-weight:700;font-size:14px}
.stage-state{font-size:13px}
.stage-meta{font-size:11px;color:#5f6368;margin-top:4px}
table{border-collapse:collapse;width:100%%;background:#fff;box-shadow:0 1px 2px rgba(0,0,0,.08);font-size:13px}
th,td{text-align:left;padding:8px 10px;border-bottom:1px solid #eceff1;vertical-align:top}
th{background:#f1f3f4;font-size:12px;text-transform:uppercase;letter-spacing:.04em;width:25%%}
table.kv th{width:30%%}
code{background:#f1f3f4;padding:1px 5px;border-radius:3px;font-size:12px}
.dot{display:inline-block;width:8px;height:8px;border-radius:50%%;margin-right:6px}
.err{color:#b3261e;font-size:12px;margin-top:4px}
.foot{margin-top:28px;color:#5f6368;font-size:12px}
</style>
<h1>ShipPilot &mdash; %(repo)s</h1>
<div class="sub">Autonomy <b>%(autonomy)s</b> &middot; %(autodesc)s</div>
<h2>Decision</h2>
<div><span class="badge" style="background:%(dcolor)s">%(decision)s</span>
&nbsp; %(reason)s</div>
<h2>Lifecycle coverage &mdash; %(covered)s/9 stages</h2>
%(grid)s
<h2>Risk score</h2>
<table class="kv"><tr><th>Before</th><td>%(before)s</td></tr>
<tr><th>After</th><td>%(after)s</td></tr>
<tr><th>Actions applied / verified</th><td>%(applied)s / %(verified)s</td></tr></table>
<h2>Actions</h2>
<table><tr><th>Rule</th><th>Stage</th><th>Severity</th><th>State</th><th>Fix</th><th>Touched</th></tr>
%(rows)s</table>
<h2>Findings after</h2>
<table><tr><th>Severity</th><th>Rule</th><th>Stage</th><th>Location</th></tr>
%(after_rows)s</table>
<h2>Software carbon intensity</h2>
%(carbon)s
<div class="foot">Generated %(ts)s &middot; Agents propose, the verifier decides what counts,
the gate decides what ships.</div>
""" % {
        "repo": e(receipt.get("repo")),
        "autonomy": e(receipt.get("autonomy")),
        "autodesc": e(receipt.get("autonomy_description")),
        "dcolor": color,
        "decision": e(decision),
        "reason": e(receipt.get("decision_reason")),
        "covered": e(receipt.get("coverage", {}).get("count")),
        "grid": _stage_grid(receipt),
        "before": e(receipt.get("risk_score_before")),
        "after": e(receipt.get("risk_score_after")),
        "applied": e(receipt.get("applied")),
        "verified": e(receipt.get("verified")),
        "rows": _rows(receipt),
        "after_rows": _findings(receipt, "findings_after"),
        "carbon": _carbon(receipt),
        "ts": e(receipt.get("generated_at")),
    }


def write(root, receipt, name="receipt.html"):
    import os
    d = os.path.join(root, ".shippilot", "audit")
    os.makedirs(d, exist_ok=True)
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(render(receipt))
    return path


def to_json(receipt):
    return json.dumps(receipt, indent=2)
