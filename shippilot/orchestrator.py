"""The ShipPilot lifecycle loop.

    PERCEIVE -> PLAN -> GATE -> ACT -> OBSERVE -> VERIFY -> RECEIPT

The loop is the same at every autonomy level. Only the gate changes. After each
write we re-run the inspector that produced the finding: a fix counts as done
only when the check that flagged it stops flagging it.
"""

from __future__ import annotations

import json
import os
import time

from . import autonomy as autonomy_mod
from . import carbon as carbon_mod
from . import remedy
from . import stages as stages_mod
from .model import STAGES, load_ignore, rel, risk_score

_SEVERITY_ORDER = {"blocker": 0, "high": 1, "medium": 2, "low": 3}


def _now():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _load_waivers(root):
    path = os.path.join(root, remedy.WAIVERS)
    if not os.path.exists(path):
        return set()
    try:
        with open(path, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return set()
    return {(w.get("path"), w.get("rule")) for w in data.get("waivers", [])}


def audit(root, only=None, ctx=None):
    """Run the inspectors and return findings. Nothing is written."""
    ctx = ctx if ctx is not None else {}
    ctx.setdefault("waivers", _load_waivers(root))
    ctx.setdefault("ignore", load_ignore(root))
    wanted = [s for s in STAGES if not only or s in only]
    findings, timing = [], {}
    for stage in wanted:
        t0 = time.perf_counter()
        got = stages_mod.inspect_stage(root, stage, ctx)
        timing[stage] = time.perf_counter() - t0
        findings.extend(got)
    return findings, timing


def _sort_key(f):
    return (_SEVERITY_ORDER.get(f.get("severity"), 9), f.get("stage", ""), f.get("rule", ""))


def run(root, level="supervised", approver=None, only=None, max_actions=40, write_receipt=True):
    root = os.path.abspath(root)
    level = autonomy_mod.normalize(level)
    approver = approver or autonomy_mod.AutoApprover(True)

    baseline, timing = audit(root, only=only)
    ctx = {"waivers": _load_waivers(root)}
    # configure() populates env_used; release() populates version. Seed them once.
    stages_mod.inspect_stage(root, "configure", ctx)
    stages_mod.inspect_stage(root, "release", ctx)

    score_before = risk_score(baseline)
    actions, attempted = [], set()

    for f in sorted(baseline, key=_sort_key):
        if len(actions) >= max_actions:
            break
        if not remedy.applicable(f):
            continue
        key = (f.get("rule"), f.get("path"), f.get("line"))
        if key in attempted:
            continue
        attempted.add(key)

        prompt = "%s/%s: %s" % (f["stage"], f["rule"], f.get("path") or "repository")
        if autonomy_mod.needs_step_approval(level):
            approved = bool(approver("apply %s -> %s?" % (f.get("fix"), prompt)))
        else:
            approved = True

        record = {
            "rule": f["rule"],
            "stage": f["stage"],
            "severity": f["severity"],
            "path": f.get("path"),
            "line": f.get("line"),
            "fix": f.get("fix"),
            "prompt": prompt,
            "approved": approved,
            "changes": [],
            "verified": False,
            "residual": [],
        }
        if approved:
            try:
                record["changes"] = remedy.apply(root, f, ctx)
            except Exception as exc:  # a failed write must not sink the run
                record["error"] = "%s: %s" % (type(exc).__name__, exc)
            ctx["waivers"] = _load_waivers(root)
            after = stages_mod.inspect_stage(root, f["stage"], ctx)
            residual = [g for g in after if g["rule"] == f["rule"]]
            record["residual"] = residual
            record["verified"] = not residual
        actions.append(record)

    residual, _ = audit(root, only=only)
    score_after = risk_score(residual)
    decision, reason = autonomy_mod.decide(residual, level)

    # A blocker is not negotiable: no autonomy level and no human can wave it through.
    if decision == "NO_GO":
        outcome_approved = False
    elif autonomy_mod.needs_outcome_approval(level):
        outcome_approved = bool(approver(
            "approve outcome? decision=%s (%s)" % (decision, reason)))
        if not outcome_approved:
            decision = "HELD_BY_HUMAN"
    else:
        outcome_approved = True

    stages_with_findings = sorted({f["stage"] for f in residual})
    carbon = carbon_mod.estimate(timing, stages_with_findings=stages_with_findings)

    receipt = {
        "tool": "shippilot",
        "version": "1.0.0",
        "repo": os.path.basename(root),
        "root": root,
        "generated_at": _now(),
        "autonomy": level,
        "autonomy_description": autonomy_mod.describe(level),
        "stages": {
            s: {
                "ran": s in timing,
                "seconds": round(timing.get(s, 0.0), 4),
                "findings_before": len([f for f in baseline if f["stage"] == s]),
                "findings_after": len([f for f in residual if f["stage"] == s]),
            }
            for s in STAGES
        },
        "coverage": {
            "touched": [s for s in STAGES if s in timing],
            "count": len([s for s in STAGES if s in timing]),
            "clean_after": [s for s in STAGES
                            if s in timing and not [f for f in residual if f["stage"] == s]],
        },
        "findings_before": baseline,
        "findings_after": residual,
        "risk_score_before": score_before,
        "risk_score_after": score_after,
        "actions": actions,
        "applied": len([a for a in actions if a["approved"] and a["changes"]]),
        "verified": len([a for a in actions if a["verified"]]),
        "unresolved": [a["rule"] for a in actions if a["approved"] and not a["verified"]],
        "decision": decision,
        "decision_reason": reason,
        "outcome_approved": outcome_approved,
        "carbon": carbon,
    }

    if write_receipt:
        receipt["receipt_path"] = rel(root, save_receipt(root, receipt))
    return receipt


def save_receipt(root, receipt):
    d = os.path.join(root, ".shippilot", "audit")
    os.makedirs(d, exist_ok=True)
    name = "receipt-%s-%s.json" % (
        time.strftime("%Y%m%dT%H%M%SZ", time.gmtime()),
        receipt.get("autonomy", "run"),
    )
    path = os.path.join(d, name)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(receipt, fh, indent=2, sort_keys=False)
    return path
