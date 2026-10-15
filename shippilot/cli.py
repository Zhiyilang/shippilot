"""Command line entry point.

    python -m shippilot audit  --root .            # inspect, print, write nothing
    python -m shippilot audit  --stage secure .    # one stage
    python -m shippilot ship   --root . --autonomy supervised
    python -m shippilot stages                     # the dial, explained
"""

from __future__ import annotations

import argparse
import json
import os
import sys

from . import autonomy as autonomy_mod
from . import receipt as receipt_mod
from . import orchestrator
from . import __version__
from .model import STAGES, risk_score

_EXIT_OK = 0
_EXIT_HOLD = 1
_EXIT_NOGO = 2


def _print_findings(findings, stream):
    if not findings:
        stream.write("no findings\n")
        return
    for f in sorted(findings, key=lambda x: {"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 9)):
        loc = "%s:%s" % (f.get("path") or "-", f.get("line") or "-")
        stream.write("[%-7s] %-28s %-10s %s\n" % (f["severity"], f["rule"], f["stage"], loc))
        stream.write("            %s\n" % f["message"])
        if f.get("excerpt"):
            stream.write("            > %s\n" % f["excerpt"])


def cmd_audit(args):
    findings, timing = orchestrator.audit(os.path.abspath(args.root), only=args.stage_list())
    if args.json:
        print(json.dumps({
            "findings": findings,
            "risk_score": risk_score(findings),
            "stages": {k: round(v, 4) for k, v in timing.items()},
        }, indent=2))
    else:
        _print_findings(findings, sys.stdout)
        print("\nrisk score: %d/100 across %d stage(s)"
              % (risk_score(findings), len(timing)))
    return _EXIT_OK if not [f for f in findings if f["severity"] == "blocker"] else _EXIT_NOGO


def cmd_ship(args):
    root = os.path.abspath(args.root)
    approver = autonomy_mod.AutoApprover(not args.deny_all)
    rec = orchestrator.run(
        root,
        level=args.autonomy,
        approver=approver,
        only=args.stage_list(),
        max_actions=args.max_actions,
        write_receipt=not args.no_receipt,
    )
    if args.json:
        print(json.dumps(rec, indent=2))
    else:
        print("autonomy   : %s  (%s)" % (rec["autonomy"], rec["autonomy_description"]))
        print("coverage   : %d/9 stages, clean after: %s"
              % (rec["coverage"]["count"], ", ".join(rec["coverage"]["clean_after"]) or "none"))
        print("risk score : %d -> %d" % (rec["risk_score_before"], rec["risk_score_after"]))
        print("actions    : %d proposed, %d applied, %d verified"
              % (len(rec["actions"]), rec["applied"], rec["verified"]))
        if rec["unresolved"]:
            print("unresolved : %s" % ", ".join(rec["unresolved"]))
        print("decision   : %s (%s)" % (rec["decision"], rec["decision_reason"]))
        carbon = rec.get("carbon") or {}
        print("carbon     : %.4f gCO2e measured, -%s%% with cache+parallelism"
              % ((carbon.get("measured") or {}).get("total_gco2e", 0.0),
                 (carbon.get("with_cache_and_parallelism") or {}).get("saved_percent", 0)))
        if rec.get("receipt_path"):
            print("receipt    : %s" % rec["receipt_path"])
    if args.html:
        print("html receipt: %s" % os.path.relpath(receipt_mod.write(root, rec), root))

    if rec["decision"] == "NO_GO":
        return _EXIT_NOGO
    if rec["decision"] in ("HOLD_FOR_HUMAN", "HELD_BY_HUMAN"):
        return _EXIT_HOLD
    return _EXIT_OK


def cmd_stages(args):
    if args.json:
        print(json.dumps({"stages": list(STAGES), "autonomy": list(autonomy_mod.AUTONOMY)}, indent=2))
        return _EXIT_OK
    print("Lifecycle stages (%d):" % len(STAGES))
    for s in STAGES:
        print("  - %s" % s)
    print("\nAutonomy dial:")
    for a in autonomy_mod.AUTONOMY:
        print("  - %-11s %s" % (a, autonomy_mod.describe(a)))
    return _EXIT_OK


def build_parser():
    p = argparse.ArgumentParser(prog="shippilot", description="Automate the nine stages after the code is written.")
    p.add_argument("--version", action="version", version="shippilot %s" % __version__)
    sub = p.add_subparsers(dest="cmd")

    a = sub.add_parser("audit", help="inspect the repository, write nothing")
    a.add_argument("--root", default=".")
    a.add_argument("--stage", action="append", dest="stages", choices=list(STAGES))
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=cmd_audit)

    s = sub.add_parser("ship", help="run the lifecycle loop and gate the ship")
    s.add_argument("--root", default=".")
    s.add_argument("--autonomy", default="supervised", choices=list(autonomy_mod.AUTONOMY))
    s.add_argument("--stage", action="append", dest="stages", choices=list(STAGES))
    s.add_argument("--max-actions", type=int, default=40)
    s.add_argument("--deny-all", action="store_true", help="approver answers no to everything")
    s.add_argument("--no-receipt", action="store_true")
    s.add_argument("--html", action="store_true")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_ship)

    t = sub.add_parser("stages", help="list stages and autonomy levels")
    t.add_argument("--json", action="store_true")
    t.set_defaults(fn=cmd_stages)

    m = sub.add_parser("mcp", help="run the MCP server over stdio")
    m.set_defaults(fn=lambda args: None)
    return p


def _stage_list(args):
    return list(args.stages) if getattr(args, "stages", None) else None


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "cmd", None):
        parser.print_help()
        return _EXIT_OK
    if args.cmd == "mcp":
        from .mcp_server import serve
        serve()
        return _EXIT_OK
    args.stage_list = lambda: _stage_list(args)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
