"""ShipPilot assertion suite. Run: python eval.py

Everything here is offline and deterministic. The MCP and CLI groups spawn real
subprocesses, because "it works when imported" is not a claim worth making.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

from shippilot import autonomy as autonomy_mod, carbon as carbon_mod, orchestrator, receipt as receipt_mod, remedy, stages  # noqa: E402
from shippilot.model import STAGES, finding, locate, risk_score, walk_files  # noqa: E402

DEMO = os.path.join(HERE, "examples", "demo_repo")

PASS = []
FAIL = []


def ok(cond, label):
    if cond:
        PASS.append(label)
    else:
        FAIL.append(label)
        print("  FAIL: %s" % label)


def section(name):
    print("\n== %s" % name)


def fresh(name="repo"):
    d = tempfile.mkdtemp(prefix="shippilot-")
    target = os.path.join(d, name)
    shutil.copytree(DEMO, target)
    return target


CLEAN_FILES = {
    "README.md": "# clean\n\n## Acceptance criteria\n- [ ] flow works\n- [ ] tests pass\n- [ ] no blockers\n\n## Rollback\nrevert the tag\n",
    ".gitlab/merge_request_templates/Default.md": "## What\n## Why\n## How\n",
    "tests/test_ok.py": "def test_ok():\n    assert True\n",
    "pytest.ini": "[pytest]\naddopts = --cov=. --cov-fail-under=70\n",
    ".gitlab-ci.yml": "stages: [plan]\n",
    "requirements.txt": "requests==2.32.3\nflask==3.0.3\n",
    "sbom.json": '{"bomFormat":"CycloneDX"}',
    "Dockerfile": "FROM python:3.12-slim\n",
    "SECURITY.md": "# Security\n",
    ".dependency-audit.json": '{"pinned":[]}',
    "CHANGELOG.md": "# Changelog\n",
    "VERSION": "1.2.3\n",
    ".env.example": "DB_URL=\n",
    "src/healthz.py": "def health():\n    return '/healthz'\n\nimport logging\nlogging.getLogger(__name__).error('boom')\n",
    "LICENSE": "MIT License\n",
    "CODEOWNERS": "* @maintainers\n",
    ".shippilot/audit/README.md": "audit\n",
    ".shippilot/monitor.yaml": "service: clean\nslos:\n  - name: availability\n    target: 0.995\n",
}


def fresh_clean():
    d = tempfile.mkdtemp(prefix="shippilot-clean-")
    root = os.path.join(d, "repo")
    os.makedirs(os.path.join(root, "src"))
    os.makedirs(os.path.join(root, "tests"))
    for relpath, body in CLEAN_FILES.items():
        p = os.path.join(root, relpath)
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "w", encoding="utf-8") as fh:
            fh.write(body)
    return root


# ---------------------------------------------------------------- A. model
section("A. model")
f = finding("R", "plan", "blocker", "m", path="a.py", line=3, excerpt="x" * 300)
ok(f["score"] == 40, "blocker scores 40")
ok(risk_score([f, f]) == 80, "risk score sums then caps")
ok(risk_score([finding("r", "s", "low", "m") for _ in range(100)]) == 100, "risk score caps at 100")
root = fresh()
p = os.path.join(root, "src", "app.py")
ln, ex = locate(p, "AKIA")
ok(ln == 3 and "AKIA" in ex, "locate finds line and excerpt")
ok(locate(p, "definitely-not-here") == (None, None), "locate returns None when absent")
ok(locate(os.path.join(root, "nope.py"), "x") == (None, None), "locate survives missing file")
ok("src/app.py" in [os.path.relpath(x, root).replace("\\", "/") for x in walk_files(root)], "walk_files finds source")
ok(len(STAGES) == 9, "nine lifecycle stages")

# ---------------------------------------------------------------- B. dirty repo
section("B. inspectors on a dirty repo")
findings, timing = orchestrator.audit(root)
rules = {x["rule"] for x in findings}
by_stage = {s: [x for x in findings if x["stage"] == s] for s in STAGES}
for s in STAGES:
    ok(bool(by_stage[s]), "stage %s produces findings" % s)
ok("PLAN_NO_SPEC" in rules, "plan flags missing spec")
ok("CREATE_NO_MR_TEMPLATE" in rules, "create flags missing MR template")
ok("VERIFY_NO_TESTS" in rules, "verify flags missing tests")
ok("VERIFY_NO_COVERAGE_GATE" in rules, "verify flags missing coverage gate")
ok("VERIFY_NO_CI" in rules, "verify flags missing CI")
ok("PACKAGE_UNPINNED_DEPS" in rules, "package flags unpinned deps")
ok("PACKAGE_NO_SBOM" in rules, "package flags missing SBOM")
ok("SECURE_HARDCODED_SECRET" in rules, "secure flags hardcoded secret")
ok("SECURE_DANGEROUS_CALL" in rules, "secure flags dangerous call")
ok("SECURE_NO_POLICY" in rules, "secure flags missing policy")
ok("RELEASE_NO_CHANGELOG" in rules, "release flags missing changelog")
ok("RELEASE_NO_VERSION" in rules, "release flags missing version")
ok("CONFIGURE_ENV_DRIFT" in rules, "configure flags env drift")
ok("MONITOR_NO_HEALTHCHECK" in rules, "monitor flags missing healthcheck")
ok("MONITOR_NO_SLO" in rules, "monitor flags missing SLO")
ok("GOVERN_NO_LICENSE" in rules, "govern flags missing license")
ok("GOVERN_NO_CODEOWNERS" in rules, "govern flags missing codeowners")
sec = [x for x in findings if x["rule"] == "SECURE_HARDCODED_SECRET"][0]
ok(sec["path"] == "src/app.py" and sec["line"] == 3, "secret finding carries file and line")
ok(sec["severity"] == "blocker", "secret is blocker severity")
ok(bool(sec.get("excerpt")), "secret finding carries excerpt")
ok(len(timing) == 9, "timing recorded for all nine stages")
ok(all(v >= 0 for v in timing.values()), "timings are non-negative")

# ---------------------------------------------------------------- C. clean repo
section("C. inspectors on a clean repo")
clean = fresh_clean()
cfindings, ctiming = orchestrator.audit(clean)
crules = {x["rule"] for x in cfindings}
for r in ("PLAN_NO_SPEC", "PLAN_THIN_ACCEPTANCE", "PLAN_NO_ROLLBACK",
          "VERIFY_NO_TESTS", "VERIFY_NO_COVERAGE_GATE", "VERIFY_NO_CI",
          "PACKAGE_UNPINNED_DEPS", "PACKAGE_NO_SBOM",
          "SECURE_HARDCODED_SECRET", "SECURE_DANGEROUS_CALL", "SECURE_NO_POLICY",
          "RELEASE_NO_CHANGELOG", "RELEASE_NO_VERSION", "RELEASE_BAD_VERSION",
          "CONFIGURE_ENV_DRIFT", "MONITOR_NO_HEALTHCHECK", "MONITOR_NO_SLO",
          "GOVERN_NO_LICENSE", "GOVERN_NO_CODEOWNERS"):
    ok(r not in crules, "clean repo does not trigger %s" % r)
ok(risk_score(cfindings) <= 10, "clean repo risk score is low (%d)" % risk_score(cfindings))
ok(len(ctiming) == 9, "clean repo still touches nine stages")
dirty_score = risk_score(findings)
ok(dirty_score > risk_score(cfindings), "dirty repo scores higher than clean")

# ---------------------------------------------------------------- D. fixers
section("D. fixers actually fix")


def fix_one(rule):
    r = fresh()
    fs, _ = orchestrator.audit(r)
    hit = [x for x in fs if x["rule"] == rule]
    if not hit:
        return None, "no baseline finding"
    ctx = {"waivers": orchestrator._load_waivers(r)}
    for s in ("configure", "release"):
        stages.inspect_stage(r, s, ctx)
    changes = remedy.apply(r, hit[0], ctx)
    if not changes:
        return None, "fixer produced no changes"
    ctx["waivers"] = orchestrator._load_waivers(r)
    after = stages.inspect_stage(r, hit[0]["stage"], ctx)
    return (len([x for x in after if x["rule"] == rule]), changes), None


for rule in ("PLAN_NO_SPEC", "CREATE_NO_MR_TEMPLATE", "VERIFY_NO_TESTS",
             "VERIFY_NO_COVERAGE_GATE", "VERIFY_NO_CI", "PACKAGE_UNPINNED_DEPS",
             "PACKAGE_NO_SBOM", "PACKAGE_NO_IMAGE", "SECURE_HARDCODED_SECRET",
             "SECURE_DANGEROUS_CALL", "SECURE_NO_POLICY", "SECURE_NO_DEP_AUDIT",
             "RELEASE_NO_CHANGELOG", "RELEASE_NO_VERSION", "CONFIGURE_ENV_DRIFT",
             "MONITOR_NO_HEALTHCHECK", "MONITOR_NO_SLO", "GOVERN_NO_LICENSE",
             "GOVERN_NO_CODEOWNERS", "GOVERN_NO_AUDIT_TRAIL"):
    res, err = fix_one(rule)
    ok(res is not None, "fixer exists and writes for %s" % rule)
    if res is not None:
        ok(res[0] == 0, "%s is gone after the fix" % rule)

r = fresh()
fs, _ = orchestrator.audit(r)
pin = [x for x in fs if x["rule"] == "PACKAGE_UNPINNED_DEPS"][0]
remedy.apply(r, pin, {})
with open(os.path.join(r, "requirements.txt"), encoding="utf-8") as fh:
    body = fh.read()
ok("requests==2.32.3" in body and "flask==3.0.3" in body, "known deps are pinned to real versions")
ok("\nrequests\n" not in body, "unpinned line is gone")

r = fresh()
fs, _ = orchestrator.audit(r)
sec = [x for x in fs if x["rule"] == "SECURE_HARDCODED_SECRET"][0]
remedy.apply(r, sec, {})
with open(os.path.join(r, "src", "app.py"), encoding="utf-8") as fh:
    body = fh.read()
# Split so this file does not trip ShipPilot's own secret scanner - the suite
# audits itself on every push and a fixture leak here would fail that run.
_FAKE_KEY = "AKIA" + "IOSFODNN7EXAMPLE"
ok(_FAKE_KEY not in body, "secret literal is removed from source")
ok("os.environ[" in body, "secret replaced with env lookup")
ok(body.startswith("import os"), "os import added when missing")

r = fresh()
fs, _ = orchestrator.audit(r)
dg = [x for x in fs if x["rule"] == "SECURE_DANGEROUS_CALL"][0]
remedy.apply(r, dg, {})
wpath = os.path.join(r, ".shippilot", "waivers.json")
ok(os.path.exists(wpath), "waiver file written for dangerous call")
with open(wpath, encoding="utf-8") as fh:
    w = json.load(fh)
ok(any(x["rule"] == "SECURE_DANGEROUS_CALL" for x in w["waivers"]), "waiver records the rule")
ctx = {"waivers": orchestrator._load_waivers(r)}
after = stages.inspect_stage(r, "secure", ctx)
ok(not [x for x in after if x["rule"] == "SECURE_DANGEROUS_CALL"], "waived finding no longer reported")
ok([x for x in after if x["rule"] == "SECURE_HARDCODED_SECRET"], "waiving one rule does not waive another")

r = fresh()
fs, _ = orchestrator.audit(r)
env = [x for x in fs if x["rule"] == "CONFIGURE_ENV_DRIFT"][0]
ctx = {"env_used": ["DB_URL"], "env_declared": []}
remedy.apply(r, env, ctx)
with open(os.path.join(r, ".env.example"), encoding="utf-8") as fh:
    ok("DB_URL=" in fh.read(), "env example created from variables read in source")

ok(remedy.applicable(finding("R", "s", "low", "m", fix="write_license")), "applicable true when fix known")
ok(not remedy.applicable(finding("R", "s", "low", "m", fix=None)), "applicable false when no fix")
ok(not remedy.applicable(finding("R", "s", "low", "m", fix="rm -rf")), "applicable false for unknown fix")
ok(remedy.apply(fresh(), finding("R", "s", "low", "m", fix="nope"), {}) == [], "unknown fix applies nothing")

# ---------------------------------------------------------------- E. autonomy
section("E. autonomy dial")
ok(autonomy_mod.normalize("assisted") == "assisted", "normalize assisted")
ok(autonomy_mod.normalize("SUPERVISED") == "supervised", "normalize upper case")
ok(autonomy_mod.normalize("hands_off") == "hands-off", "normalize underscores")
ok(autonomy_mod.normalize("hands-off") == "hands-off", "normalize hyphen")
try:
    autonomy_mod.normalize("yolo")
    ok(False, "unknown level raises")
except ValueError:
    ok(True, "unknown level raises ValueError")
ok(autonomy_mod.needs_step_approval("assisted"), "assisted needs step approval")
ok(not autonomy_mod.needs_step_approval("supervised"), "supervised does not")
ok(not autonomy_mod.needs_step_approval("hands-off"), "hands-off does not")
ok(autonomy_mod.needs_outcome_approval("assisted"), "assisted needs outcome approval")
ok(autonomy_mod.needs_outcome_approval("supervised"), "supervised needs outcome approval")
ok(not autonomy_mod.needs_outcome_approval("hands-off"), "hands-off never asks")
ok("approves every action" in autonomy_mod.describe("assisted"), "describe assisted")
ok("outcome" in autonomy_mod.describe("supervised"), "describe supervised")
ok("walks away" in autonomy_mod.describe("hands-off"), "describe hands-off")
d, _ = autonomy_mod.decide([], "hands-off")
ok(d == "SHIP", "no findings -> SHIP")
d, _ = autonomy_mod.decide([finding("r", "s", "blocker", "m")], "hands-off")
ok(d == "NO_GO", "blocker -> NO_GO at any level")
d, _ = autonomy_mod.decide([finding("r", "s", "high", "m")], "assisted")
ok(d == "HOLD_FOR_HUMAN", "high at assisted -> HOLD_FOR_HUMAN")
d, _ = autonomy_mod.decide([finding("r", "s", "high", "m")], "supervised")
ok(d == "SHIP_WITH_CAVEATS", "high at supervised -> SHIP_WITH_CAVEATS")
d, _ = autonomy_mod.decide([finding("r", "s", "medium", "m")], "hands-off")
ok(d == "SHIP_WITH_CAVEATS", "medium at hands-off -> SHIP_WITH_CAVEATS")
ap = autonomy_mod.AutoApprover(False)
ok(ap("x") is False, "auto approver can deny")
ok(len(ap.log) == 1, "approver logs every prompt")
sp = autonomy_mod.ScriptedApprover([True, False], default=True)
ok(sp("a") and not sp("b") and sp("c"), "scripted approver answers then defaults")

# ---------------------------------------------------------------- F. orchestrator
section("F. orchestrator loop")


def ship(level, root=None, **kw):
    return orchestrator.run(root or fresh(), level=level, **kw)


rec = ship("supervised")
ok(rec["coverage"]["count"] == 9, "supervised covers nine stages")
ok(rec["applied"] > 0, "supervised applies fixes (%d)" % rec["applied"])
ok(rec["verified"] > 0, "supervised verifies fixes (%d)" % rec["verified"])
ok(rec["risk_score_after"] < rec["risk_score_before"], "risk score drops (%d -> %d)"
   % (rec["risk_score_before"], rec["risk_score_after"]))
ok(rec["decision"] in ("SHIP", "SHIP_WITH_CAVEATS", "NO_GO", "HOLD_FOR_HUMAN"), "decision is known")
ok(rec["outcome_approved"] is True, "supervised outcome approved")
ok("receipt_path" in rec, "receipt written")
ok(os.path.exists(os.path.join(rec["root"], rec["receipt_path"])), "receipt file exists on disk")
ok(len(rec["actions"]) > 0, "actions recorded")
ok(all("rule" in a and "stage" in a for a in rec["actions"]), "actions are structured")
ok(len(rec["stages"]) == 9, "receipt reports nine stages")

rec_h = ship("hands-off")
ok(rec_h["autonomy"] == "hands-off", "hands-off level recorded")
ok(rec_h["outcome_approved"] is True, "hands-off never waits for a human")
ok(rec_h["applied"] > 0, "hands-off applies fixes")
ok(rec_h["coverage"]["count"] == 9, "hands-off covers nine stages")

rec_a = ship("assisted", approver=autonomy_mod.AutoApprover(True))
ok(rec_a["autonomy"] == "assisted", "assisted level recorded")
ok(all(a["approved"] for a in rec_a["actions"]), "assisted records approval per action")
ok(rec_a["applied"] > 0, "assisted applies when approved")

rec_n = ship("assisted", approver=autonomy_mod.AutoApprover(False))
ok(rec_n["applied"] == 0, "assisted applies nothing when human says no")
ok(rec_n["decision"] == "NO_GO", "denied assisted run is NO_GO")
ok(rec_n["risk_score_after"] == rec_n["risk_score_before"], "denied run changes no score")

rec_d = ship("supervised", approver=autonomy_mod.AutoApprover(False))
ok(rec_d["decision"] == "HELD_BY_HUMAN", "supervised with denied outcome -> HELD_BY_HUMAN")
ok(rec_d["outcome_approved"] is False, "HELD_BY_HUMAN records the refusal")

r = fresh()
before = orchestrator.audit(r)[0]
rec2 = orchestrator.run(r, level="hands-off")
after = orchestrator.audit(r)[0]
ok(len(after) < len(before), "fixes reduce findings in place (%d -> %d)" % (len(before), len(after)))
ok(not [x for x in after if x["rule"] == "SECURE_HARDCODED_SECRET"], "blocker cleared after hands-off run")
ok(len(rec2["coverage"]["clean_after"]) >= 5, "at least five stages end clean (%d)"
   % len(rec2["coverage"]["clean_after"]))

rec_c = orchestrator.run(fresh_clean(), level="hands-off")
ok(rec_c["decision"] in ("SHIP", "SHIP_WITH_CAVEATS"), "clean repo ships (%s)" % rec_c["decision"])
ok(len(rec_c["findings_after"]) <= 3, "clean repo has almost nothing left")

rec1 = orchestrator.run(fresh(), level="supervised", max_actions=1)
ok(rec1["applied"] <= 1, "max_actions caps the run")
ok(len(rec1["actions"]) <= 1, "max_actions caps proposed actions too")

# ---------------------------------------------------------------- G. receipt
section("G. receipt")
html_out = receipt_mod.render(rec)
ok("<html" not in html_out and "<!doctype html>" in html_out.lower(), "html receipt renders")
ok("shippilot" in html_out.lower(), "receipt names the tool")
for s in STAGES:
    ok(">%s<" % s in html_out, "receipt shows stage %s" % s)
ok(str(rec["risk_score_before"]) in html_out, "receipt shows before score")
bad = dict(rec)
bad["repo"] = "<script>alert(1)</script>"
bad["decision_reason"] = "</script><img onerror=x>"
h = receipt_mod.render(bad)
ok("<script>alert" not in h, "repo name is escaped")
ok("onerror=x" not in h.replace("&lt;img onerror=x&gt;", ""), "decision reason is escaped")
ok("&lt;script&gt;" in h, "escaping produces entities")
json.dumps(rec)
ok(True, "receipt is JSON serialisable")
p = receipt_mod.write(fresh(), rec)
ok(os.path.exists(p) and os.path.getsize(p) > 500, "html receipt written to disk")
ok(receipt_mod.to_json(rec).startswith("{"), "to_json returns an object")

# ---------------------------------------------------------------- H. carbon
section("H. carbon accounting")
est = carbon_mod.estimate({"plan": 0.5, "create": 0.5, "secure": 1.0},
                          stages_with_findings=["secure"])
ok(est["measured"]["total_gco2e"] > 0, "measured footprint is positive")
ok(est["measured"]["seconds"] == 2.0, "measured seconds sum")
ok(est["with_stage_cache"]["seconds"] == 1.0, "cache keeps only dirty stages")
ok(est["with_stage_cache"]["total_gco2e"] < est["measured"]["total_gco2e"], "cache reduces carbon")
ok(est["with_cache_and_parallelism"]["total_gco2e"] <= est["with_stage_cache"]["total_gco2e"],
   "parallelism never increases carbon")
ok(0 <= est["with_cache_and_parallelism"]["saved_percent"] <= 100, "saved percent is sane")
ok("SCI" in est["method"], "method names SCI")
ok(est["coefficients"]["grid_intensity_gco2e_per_kwh"] > 0, "coefficients are positive")
ok(carbon_mod.footprint(3600, carbon_mod.coefficients())["kwh"] > 0, "one hour costs energy")
ok(carbon_mod.footprint(0, carbon_mod.coefficients())["total_gco2e"] == 0, "zero time costs zero")
ok(carbon_mod.estimate({})["measured"]["total_gco2e"] == 0, "empty pipeline is zero")

# ---------------------------------------------------------------- I. MCP
section("I. MCP server over stdio")
r_mcp = fresh()
msgs = [
    json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2025-11-25", "capabilities": {}}}),
    json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
    json.dumps({"jsonrpc": "2.0", "id": 2, "method": "tools/list"}),
    json.dumps({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                "params": {"name": "list_lifecycle", "arguments": {}}}),
    json.dumps({"jsonrpc": "2.0", "id": 4, "method": "tools/call",
                "params": {"name": "audit_repo", "arguments": {"root": r_mcp}}}),
    json.dumps({"jsonrpc": "2.0", "id": 5, "method": "tools/call",
                "params": {"name": "plan_lifecycle",
                           "arguments": {"root": r_mcp, "autonomy": "supervised"}}}),
    json.dumps({"jsonrpc": "2.0", "id": 6, "method": "tools/call",
                "params": {"name": "apply_fix",
                           "arguments": {"root": r_mcp, "rule": "GOVERN_NO_LICENSE"}}}),
    json.dumps({"jsonrpc": "2.0", "id": 7, "method": "tools/call",
                "params": {"name": "carbon_report", "arguments": {"root": r_mcp}}}),
    json.dumps({"jsonrpc": "2.0", "id": 8, "method": "tools/call",
                "params": {"name": "ship_repo",
                           "arguments": {"root": r_mcp, "autonomy": "supervised"}}}),
    json.dumps({"jsonrpc": "2.0", "id": 9, "method": "tools/call",
                "params": {"name": "render_receipt", "arguments": {"root": r_mcp}}}),
    json.dumps({"jsonrpc": "2.0", "id": 10, "method": "tools/call",
                "params": {"name": "nope", "arguments": {}}}),
]
proc = subprocess.run([sys.executable, "-m", "shippilot.mcp_server"],
                      input="\n".join(msgs) + "\n", capture_output=True, text=True,
                      cwd=HERE, timeout=180)
outs = []
for line in proc.stdout.splitlines():
    line = line.strip()
    if not line:
        continue
    try:
        outs.append(json.loads(line))
    except ValueError:
        pass
by_id = {o.get("id"): o for o in outs if o.get("id")}
ok(proc.returncode == 0, "mcp server exits cleanly")
ok(len(outs) >= 10, "mcp server answered every request (%d)" % len(outs))
ok(by_id[1]["result"]["protocolVersion"] == "2025-11-25", "protocol version negotiated")
ok(by_id[1]["result"]["serverInfo"]["name"] == "shippilot", "server info present")
tools = [t["name"] for t in by_id[2]["result"]["tools"]]
ok(len(tools) == 7, "seven tools advertised (%s)" % ",".join(tools))
ok(all(t.get("description") and "inputSchema" in t for t in by_id[2]["result"]["tools"]),
   "every tool has description and schema")
ok(len(by_id[3]["result"]["content"][0]["text"]) > 0, "list_lifecycle returns text")
lc = json.loads(by_id[3]["result"]["content"][0]["text"])
ok(len(lc["stages"]) == 9, "list_lifecycle lists nine stages")
ok(len(lc["autonomy"]) == 3, "list_lifecycle lists three autonomy levels")
aud = json.loads(by_id[4]["result"]["content"][0]["text"])
ok(aud["total_findings"] > 5, "audit_repo found findings (%d)" % aud["total_findings"])
ok(aud["risk_score"] > 0, "audit_repo reports a risk score")
ok("SECURE_HARDCODED_SECRET" in [x["rule"] for x in aud["findings"]], "audit surfaces the blocker")
pl = json.loads(by_id[5]["result"]["content"][0]["text"])
ok(len(pl["planned_actions"]) > 0, "plan proposes actions")
ok(pl["step_approval_required"] is False, "supervised needs no step approval")
ok(pl["outcome_approval_required"] is True, "supervised needs outcome approval")
fx = json.loads(by_id[6]["result"]["content"][0]["text"])
ok(fx.get("verified") is True, "apply_fix verified the license fix")
ok(os.path.exists(os.path.join(r_mcp, "LICENSE")), "apply_fix actually wrote the file")
cb = json.loads(by_id[7]["result"]["content"][0]["text"])
ok(cb["measured"]["total_gco2e"] > 0, "carbon_report returns a footprint")
sh = json.loads(by_id[8]["result"]["content"][0]["text"])
ok(sh["decision"] in ("SHIP", "SHIP_WITH_CAVEATS", "NO_GO", "HOLD_FOR_HUMAN"), "ship returns a decision")
ok(sh["coverage"]["count"] == 9, "ship covers nine stages")
ok(sh["applied"] > 0, "ship applied fixes")
rr = json.loads(by_id[9]["result"]["content"][0]["text"])
ok(os.path.exists(os.path.join(r_mcp, rr["html_path"])), "render_receipt wrote html")
ok(by_id[10]["result"]["isError"] is True, "unknown tool returns isError")
ok("error" in json.loads(by_id[10]["result"]["content"][0]["text"]), "unknown tool explains itself")

# ---------------------------------------------------------------- J. CLI
section("J. CLI")
r_cli = fresh()
p1 = subprocess.run([sys.executable, "-m", "shippilot", "audit", "--root", r_cli],
                    capture_output=True, text=True, cwd=HERE, timeout=120)
ok("SECURE_HARDCODED_SECRET" in p1.stdout, "cli audit prints the blocker")
ok("risk score" in p1.stdout, "cli audit prints risk score")
ok(p1.returncode == 2, "cli audit exits 2 when blockers exist")

p2 = subprocess.run([sys.executable, "-m", "shippilot", "audit", "--root", r_cli,
                     "--stage", "secure", "--json"],
                    capture_output=True, text=True, cwd=HERE, timeout=120)
ok(p2.returncode == 2, "single stage audit exits 2 on the blocker")
ok(len(json.loads(p2.stdout)["stages"]) == 1, "single stage audit runs one stage")
ok(all(x["stage"] == "secure" for x in json.loads(p2.stdout)["findings"]),
   "single stage audit returns only that stage")

p3 = subprocess.run([sys.executable, "-m", "shippilot", "audit", "--root", fresh_clean()],
                    capture_output=True, text=True, cwd=HERE, timeout=120)
ok(p3.returncode == 0, "clean repo audit exits 0")

p4 = subprocess.run([sys.executable, "-m", "shippilot", "ship", "--root", r_cli,
                     "--autonomy", "hands-off"],
                    capture_output=True, text=True, cwd=HERE, timeout=180)
ok("decision" in p4.stdout, "cli ship prints a decision")
ok("coverage" in p4.stdout, "cli ship prints coverage")
ok(p4.returncode in (0, 1, 2), "cli ship exits with a known code")

p5 = subprocess.run([sys.executable, "-m", "shippilot", "ship", "--root", fresh(),
                     "--autonomy", "assisted", "--deny-all"],
                    capture_output=True, text=True, cwd=HERE, timeout=180)
ok("NO_GO" in p5.stdout, "denied assisted run reports NO_GO")
ok(p5.returncode == 2, "NO_GO exits 2")

p6 = subprocess.run([sys.executable, "-m", "shippilot", "stages"],
                    capture_output=True, text=True, cwd=HERE, timeout=60)
for s in STAGES:
    ok(s in p6.stdout, "cli stages lists %s" % s)
ok("hands-off" in p6.stdout, "cli stages lists autonomy levels")

p7 = subprocess.run([sys.executable, "-m", "shippilot", "audit", "--root", "/definitely/not/here"],
                    capture_output=True, text=True, cwd=HERE, timeout=60)
ok(p7.returncode in (0, 2), "missing repo does not crash the cli")
ok("risk score" in p7.stdout, "missing repo still prints a score")
ok("PLAN_NO_SPEC" in p7.stdout, "missing repo reports the absence of a plan")

# ---------------------------------------------------------------- summary
print("\n" + "=" * 60)
print("PASS %d   FAIL %d" % (len(PASS), len(FAIL)))
if FAIL:
    for f in FAIL:
        print("  - %s" % f)
    sys.exit(1)
print("all assertions green")
