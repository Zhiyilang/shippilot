"""ShipPilot console.

Two tabs: run the whole lifecycle under an autonomy level, or inspect a single
stage. Both are exposed as MCP tools through Gradio's built-in MCP server, which
is how GitLab Duo drives the same machinery from a flow.
"""

from __future__ import annotations

import json
import os

import gradio as gr

from shippilot import autonomy as autonomy_mod, orchestrator, receipt as receipt_mod
from shippilot.model import STAGES, risk_score

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = os.path.join(HERE, "examples", "demo_repo")
CSS = ".decision{padding:10px 14px;border-radius:8px;font-weight:700;color:#fff;display:inline-block}"


def _grid(rec):
    cells = []
    for s in STAGES:
        info = rec["stages"].get(s, {})
        before = info.get("findings_before", 0)
        after = info.get("findings_after", 0)
        state = "clean" if after == 0 and before == 0 else ("fixed" if after == 0 else "%d open" % after)
        cells.append("| %s | %d | %d | %s |" % (s, before, after, state))
    return "| stage | before | after | state |\n|---|---|---|---|\n" + "\n".join(cells)


def run_lifecycle(root: str, autonomy: str) -> str:
    """Run all nine post-code stages under an autonomy level and gate the ship."""
    root = (root or "").strip() or DEFAULT_ROOT
    if not os.path.isdir(root):
        return "**%s is not a directory.**" % root
    level = autonomy_mod.normalize(autonomy or "supervised")
    rec = orchestrator.run(root, level=level, write_receipt=True)
    lines = [
        "## %s" % rec["decision"],
        "",
        "%s" % rec["decision_reason"],
        "",
        "- autonomy: **%s** (%s)" % (rec["autonomy"], rec["autonomy_description"]),
        "- coverage: **%d/9** stages, clean after: %s"
        % (rec["coverage"]["count"], ", ".join(rec["coverage"]["clean_after"]) or "none"),
        "- risk score: **%d -> %d**" % (rec["risk_score_before"], rec["risk_score_after"]),
        "- actions: %d applied, %d verified" % (rec["applied"], rec["verified"]),
        "- carbon: %.4f gCO2e measured, -%s%% with cache + parallelism"
        % ((rec["carbon"]["measured"]["total_gco2e"]),
           rec["carbon"]["with_cache_and_parallelism"]["saved_percent"]),
    ]
    if rec["unresolved"]:
        lines.append("- unresolved: %s" % ", ".join(rec["unresolved"]))
    lines += ["", _grid(rec), "", "```json", json.dumps({
        "decision": rec["decision"], "applied": rec["applied"],
        "verified": rec["verified"], "receipt": rec.get("receipt_path"),
    }, indent=2), "```"]
    return "\n".join(lines)


def inspect_stage(root: str, stage: str) -> str:
    """Inspect one lifecycle stage and list what it found. Writes nothing."""
    root = (root or "").strip() or DEFAULT_ROOT
    if not os.path.isdir(root):
        return "**%s is not a directory.**" % root
    wanted = [stage] if stage in STAGES else None
    findings, _ = orchestrator.audit(root, only=wanted)
    if not findings:
        return "No findings in %s." % (stage or "any stage")
    rows = ["| severity | rule | stage | location |", "|---|---|---|---|"]
    for f in sorted(findings, key=lambda x: {"blocker": 0, "high": 1, "medium": 2, "low": 3}.get(x["severity"], 9)):
        rows.append("| %s | %s | %s | `%s:%s` |"
                    % (f["severity"], f["rule"], f["stage"], f.get("path") or "-", f.get("line") or "-"))
    rows += ["", "risk score: **%d/100**" % risk_score(findings)]
    return "\n".join(rows)


def build():
    with gr.Blocks(title="ShipPilot") as demo:
        gr.Markdown("# ShipPilot\n*Code generation is solved. Nine stages are not.*\n\n"
                    "**Agents propose. The verifier decides what counts. The gate decides what ships.**")
        with gr.Tabs():
            with gr.Tab("Ship console"):
                root = gr.Textbox(label="Repository path", value=DEFAULT_ROOT)
                level = gr.Radio(label="Autonomy", choices=list(autonomy_mod.AUTONOMY), value="supervised")
                gr.Markdown("assisted = approve every action &middot; supervised = approve the outcome "
                            "&middot; hands-off = walk away, blockers still stop it")
                out = gr.Markdown(label="Decision")
                gr.Button("Run lifecycle", variant="primary").click(run_lifecycle, [root, level], out)
            with gr.Tab("Stage inspector"):
                root2 = gr.Textbox(label="Repository path", value=DEFAULT_ROOT)
                stage = gr.Dropdown(label="Stage", choices=list(STAGES), value="secure")
                out2 = gr.Markdown(label="Findings")
                gr.Button("Inspect", variant="secondary").click(inspect_stage, [root2, stage], out2)
        gr.Markdown("---\nZero dependencies. MCP stdio (`python -m shippilot mcp`), CLI, or this app.")
    return demo


if __name__ == "__main__":
    demo = build()
    demo.launch(
        css=CSS,
        mcp_server=True,
        server_name="0.0.0.0",
        server_port=int(os.environ.get("PORT", "7860")),
        show_api=False,
    )
