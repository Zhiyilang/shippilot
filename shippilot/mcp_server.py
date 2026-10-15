"""Zero-dependency MCP server (stdio, spec 2025-11-25).

Seven tools, one per thing a GitLab Duo flow would want to ask for. Nothing here
truncates a string: payloads are trimmed structurally, so the JSON on the wire is
always parseable.
"""

from __future__ import annotations

import json
import os
import sys

from . import autonomy as autonomy_mod
from . import carbon as carbon_mod
from . import orchestrator
from . import receipt as receipt_mod
from . import remedy
from .model import STAGES, risk_score

PROTOCOL = "2025-11-25"
SUPPORTED = ["2025-11-25", "2025-06-18", "2025-03-26"]
SERVER_INFO = {"name": "shippilot", "version": "1.0.0"}


def _ok(result):
    return {"content": [{"type": "text", "text": json.dumps(result, indent=2)}],
            "isError": False}


def _err(message):
    return {"content": [{"type": "text", "text": json.dumps({"error": message})}],
            "isError": True}


def _root(value):
    return os.path.abspath(value or ".")


def _slim(f, keep_excerpt=True):
    out = {k: f.get(k) for k in ("rule", "stage", "severity", "message", "path", "line", "fix")}
    if keep_excerpt and f.get("excerpt"):
        out["excerpt"] = f["excerpt"][:200]
    return out


def tool_list_lifecycle(args):
    return {
        "stages": list(STAGES),
        "autonomy": [{"level": a, "description": autonomy_mod.describe(a)} for a in autonomy_mod.AUTONOMY],
        "signature": "Agents propose. The verifier decides what counts. The gate decides what ships.",
    }


def tool_audit_repo(args):
    root = _root(args.get("root"))
    if not os.path.isdir(root):
        return {"error": "not a directory: %s" % root}
    stage = args.get("stage")
    only = [stage] if stage else None
    findings, timing = orchestrator.audit(root, only=only)
    limit = int(args.get("limit", 40) or 40)
    ordered = sorted(findings, key=lambda f: {"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(f["severity"], 9))
    return {
        "root": root,
        "risk_score": risk_score(findings),
        "total_findings": len(findings),
        "returned": min(limit, len(ordered)),
        "findings": [_slim(f) for f in ordered[:limit]],
        "by_stage": {s: len([f for f in findings if f["stage"] == s]) for s in STAGES if s in timing},
    }


def tool_plan_lifecycle(args):
    root = _root(args.get("root"))
    level = autonomy_mod.normalize(args.get("autonomy", "supervised"))
    findings, _ = orchestrator.audit(root)
    planned = [f for f in findings if remedy.applicable(f)]
    manual = [f for f in findings if not remedy.applicable(f)]
    return {
        "root": root,
        "autonomy": level,
        "autonomy_description": autonomy_mod.describe(level),
        "step_approval_required": autonomy_mod.needs_step_approval(level),
        "outcome_approval_required": autonomy_mod.needs_outcome_approval(level),
        "planned_actions": [{"rule": f["rule"], "stage": f["stage"], "severity": f["severity"],
                             "fix": f["fix"], "path": f.get("path")} for f in planned],
        "needs_a_human": [_slim(f) for f in manual],
        "note": "plan only - nothing has been written",
    }


def tool_apply_fix(args):
    root = _root(args.get("root"))
    rule = args.get("rule")
    if not rule:
        return {"error": "rule is required"}
    findings, _ = orchestrator.audit(root)
    ctx = {"waivers": orchestrator._load_waivers(root)}
    match = None
    for f in findings:
        if f["rule"] == rule and (not args.get("path") or f.get("path") == args.get("path")):
            match = f
            break
    if match is None:
        return {"error": "no open finding for rule %r" % rule}
    if not remedy.applicable(match):
        return {"error": "rule %r has no deterministic fix; a human must decide" % rule,
                "finding": _slim(match)}
    changes = remedy.apply(root, match, ctx)
    after, _ = orchestrator.audit(root, only=[match["stage"]])
    residual = [f for f in after if f["rule"] == rule]
    return {"rule": rule, "stage": match["stage"], "changes": changes,
            "verified": not residual, "residual": [_slim(f) for f in residual]}


def tool_ship_repo(args):
    root = _root(args.get("root"))
    level = autonomy_mod.normalize(args.get("autonomy", "supervised"))
    rec = orchestrator.run(
        root,
        level=level,
        approver=autonomy_mod.AutoApprover(bool(args.get("approve", True))),
        max_actions=int(args.get("max_actions", 40) or 40),
        write_receipt=bool(args.get("write_receipt", True)),
    )
    slim = {
        "repo": rec["repo"], "autonomy": rec["autonomy"],
        "coverage": rec["coverage"], "risk_score_before": rec["risk_score_before"],
        "risk_score_after": rec["risk_score_after"], "applied": rec["applied"],
        "verified": rec["verified"], "unresolved": rec["unresolved"],
        "decision": rec["decision"], "decision_reason": rec["decision_reason"],
        "outcome_approved": rec["outcome_approved"],
        "receipt_path": rec.get("receipt_path"),
        "carbon_gco2e": (rec.get("carbon") or {}).get("measured", {}).get("total_gco2e"),
        "actions": [{"rule": a["rule"], "stage": a["stage"], "fix": a["fix"],
                     "approved": a["approved"], "verified": a["verified"],
                     "touched": [c.get("path") for c in a.get("changes", [])]}
                    for a in rec["actions"]],
        "findings_after": [_slim(f, keep_excerpt=False) for f in rec["findings_after"]],
    }
    return slim


def tool_carbon_report(args):
    root = _root(args.get("root"))
    findings, timing = orchestrator.audit(root)
    est = carbon_mod.estimate(timing, stages_with_findings=sorted({f["stage"] for f in findings}))
    return {
        "root": root,
        "coefficients": est["coefficients"],
        "measured": est["measured"],
        "with_stage_cache": est["with_stage_cache"],
        "with_cache_and_parallelism": est["with_cache_and_parallelism"],
        "method": est["method"],
    }


def tool_render_receipt(args):
    root = _root(args.get("root"))
    level = autonomy_mod.normalize(args.get("autonomy", "supervised"))
    rec = orchestrator.run(root, level=level, write_receipt=False)
    path = receipt_mod.write(root, rec)
    return {"html_path": os.path.relpath(path, root), "bytes": os.path.getsize(path),
            "decision": rec["decision"]}


TOOLS = {
    "list_lifecycle": {
        "description": "List the nine DevSecOps lifecycle stages and the three autonomy levels.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
        "fn": tool_list_lifecycle,
    },
    "audit_repo": {
        "description": "Inspect a repository across the post-code lifecycle. Writes nothing.",
        "inputSchema": {"type": "object", "properties": {
            "root": {"type": "string", "description": "Path to the repository."},
            "stage": {"type": "string", "description": "Optional single stage to inspect.",
                      "enum": list(STAGES)},
            "limit": {"type": "integer", "description": "Max findings to return (default 40)."},
        }, "required": []},
        "fn": tool_audit_repo,
    },
    "plan_lifecycle": {
        "description": "Propose the actions the loop would take, without taking them.",
        "inputSchema": {"type": "object", "properties": {
            "root": {"type": "string"},
            "autonomy": {"type": "string", "enum": list(autonomy_mod.AUTONOMY)},
        }, "required": []},
        "fn": tool_plan_lifecycle,
    },
    "apply_fix": {
        "description": "Apply one deterministic fix and re-run the check that flagged it.",
        "inputSchema": {"type": "object", "properties": {
            "root": {"type": "string"},
            "rule": {"type": "string", "description": "Rule id, e.g. SECURE_HARDCODED_SECRET."},
            "path": {"type": "string", "description": "Optional path to disambiguate."},
        }, "required": ["rule"]},
        "fn": tool_apply_fix,
    },
    "ship_repo": {
        "description": "Run the full loop under an autonomy level and gate the ship decision.",
        "inputSchema": {"type": "object", "properties": {
            "root": {"type": "string"},
            "autonomy": {"type": "string", "enum": list(autonomy_mod.AUTONOMY)},
            "approve": {"type": "boolean", "description": "What the approver answers (default true)."},
            "max_actions": {"type": "integer"},
            "write_receipt": {"type": "boolean"},
        }, "required": ["root"]},
        "fn": tool_ship_repo,
    },
    "carbon_report": {
        "description": "Software Carbon Intensity for the pipeline, plus two optimisation scenarios.",
        "inputSchema": {"type": "object", "properties": {"root": {"type": "string"}}, "required": []},
        "fn": tool_carbon_report,
    },
    "render_receipt": {
        "description": "Run the loop and write a self-contained HTML receipt.",
        "inputSchema": {"type": "object", "properties": {
            "root": {"type": "string"},
            "autonomy": {"type": "string", "enum": list(autonomy_mod.AUTONOMY)},
        }, "required": ["root"]},
        "fn": tool_render_receipt,
    },
}


def _tools_list():
    return [{"name": n, "description": t["description"], "inputSchema": t["inputSchema"]}
            for n, t in TOOLS.items()]


def handle(msg):
    method = msg.get("method")
    mid = msg.get("id")
    if method == "initialize":
        wanted = ((msg.get("params") or {}).get("protocolVersion") or PROTOCOL)
        version = wanted if wanted in SUPPORTED else PROTOCOL
        return {"jsonrpc": "2.0", "id": mid, "result": {
            "protocolVersion": version, "serverInfo": SERVER_INFO,
            "capabilities": {"tools": {}}}}
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": {"tools": _tools_list()}}
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = TOOLS.get(name)
        if tool is None:
            return {"jsonrpc": "2.0", "id": mid, "result": _err("unknown tool: %s" % name)}
        try:
            return {"jsonrpc": "2.0", "id": mid, "result": _ok(tool["fn"](args))}
        except Exception as exc:
            return {"jsonrpc": "2.0", "id": mid, "result": _err("%s: %s" % (type(exc).__name__, exc))}
    if method and method.startswith("notifications/"):
        return None
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": "method not found: %s" % method}}


def serve(stdin=None, stdout=None):
    stdin = stdin or sys.stdin
    stdout = stdout or sys.stdout
    for raw in stdin:
        raw = raw.strip()
        if not raw:
            continue
        try:
            msg = json.loads(raw)
        except ValueError:
            continue
        resp = handle(msg)
        if resp is None:
            continue
        stdout.write(json.dumps(resp) + "\n")
        stdout.flush()


if __name__ == "__main__":
    serve()
