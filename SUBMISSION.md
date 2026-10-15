# Devpost submission — Life After Code (GitLab Transcend Hackathon)

Deadline: **Oct 28, 2026 @ 2:00am GMT+13** (Oct 27, ~21:00 Beijing).
Path: **A — Start Fresh**. Autonomy level: **hands-off** (also demonstrated at
assisted and supervised).

Copy each block below into the matching form field.

---

## Project name

ShipPilot

## Tagline

Nine DevSecOps stages, one autonomy dial.

## Description

### What it does

ShipPilot automates the nine stages that happen after the code is written:
plan, create, verify, package, secure, release, configure, monitor, govern.

You point it at a repository. It runs nine deterministic inspectors, collects
findings — each one carrying the file and line it came from — and then applies
the fix for each rule it knows how to fix. After every write it **re-runs the
inspector that flagged the finding**. A fix counts as done only when the check
stops flagging it.

The interesting part is the dial. One parameter, three levels:

- **assisted** — stops before every single write, human approves each action
- **supervised** — clears its own gates across all nine stages, human approves
  the outcome once
- **hands-off** — human states intent and walks away; it audits, fixes,
  re-verifies, and reports

The checks are identical at all three levels. Only who is in the loop changes,
which is what makes the autonomy auditable instead of a matter of taste. And a
blocker is not negotiable: hands-off will fix nineteen things on its own and
still refuse to ship on the twentieth.

### The problem it solves

"Did the agent actually fix it?" has no answer in most agent pipelines, because
the agent grades its own homework. That is why autonomy stops at demos: the more
you hand over, the less you know.

ShipPilot separates three roles that are usually collapsed into one. The agent
**proposes**. The verifier — the same deterministic inspector that raised the
finding — **decides what counts**. The gate **decides what ships**, by
arithmetic on residual findings, not by model confidence.

The receipt reports `applied` and `verified` as separate numbers. A run reading
"20 applied, 19 verified" is a run that worked: the twentieth is the one a human
needs to look at, and hiding it would be the bug.

### How it uses GitLab to automate the post-code lifecycle

Three integrations, all committed to the repository:

1. **MCP client** — `.gitlab/duo/mcp.json` registers ShipPilot's stdio MCP
   server with the Duo Agent Platform. Duo calls seven tools directly:
   `audit_repo`, `plan_lifecycle`, `apply_fix`, `ship_repo`, `carbon_report`,
   `render_receipt`, `list_lifecycle`. (spec 2025-11-25, zero dependencies)
2. **Flows** — `.gitlab/duo/flows/post_code_{assisted,supervised,hands_off}.yml`,
   one flow per autonomy level, each with `tool_overrides` pinning tool
   parameters so the model cannot drift from the contract.
3. **Agent config** — `.gitlab/duo/agent-config.yml`. The image is
   `python:3.12-slim` and the setup script is a print statement, because there
   is nothing to install.

The project's own `.gitlab-ci.yml` has nine stages plus `shippilot-ship-assisted`
and `shippilot-ship-hands-off` jobs, so the visible pipeline history *is* the
automation running. `shippilot-self-audit` runs ShipPilot on its own repository
on every push.

### Lifecycle stages covered

All nine: plan, create, verify, package, secure, release, configure, monitor,
govern. Each stage has its own inspector, its own rules, and at least one
deterministic fixer. Coverage is printed per run and rendered as nine tiles in
the receipt.

### Autonomy level

**Hands-off** — primary submission. A human sets intent and walks away. The
pipeline audits, fixes, re-verifies, and gates the ship decision without asking.
Assisted and supervised are also implemented and tested; the dial is one
parameter (`--autonomy`).

## Things we deliberately did not automate

- `eval()` and `shell=True` are not auto-rewritten — that is how pipelines break
  production quietly. ShipPilot writes a risk acceptance waiver naming file,
  rule and reason, and reports the item as unresolved.
- Unknown dependencies are not pinned to invented versions. `KNOWN_PINS` holds
  real versions for ~20 packages; anything else stays unpinned and stays in the
  report.
- Findings with no deterministic fix (`fix: null`) are surfaced as
  `needs_a_human` in `plan_lifecycle` and never silently disappear.

## Environmentally Impactful — opt in, YES

See [SUSTAINABILITY.md](SUSTAINABILITY.md). Summary: every run times each stage
and converts with the SCI formula `(E × I) + M`, then prices two concrete
optimisations — skipping stages that came back clean, and running the dirty
stages in parallel. Coefficients are published public figures and all four are
overridable. Percentages are computed from unrounded grams, so a cheap stage
cannot round to zero and claim a saving nobody achieved. Structurally: zero
dependencies means no install step, no network transfer and no container layer
rebuild per pipeline run; the nine stages walk the tree once in a single process
rather than nine containers each re-resolving dependencies.

## Technologies used

Python 3 standard library only (`argparse`, `json`, `os`, `re`, `hashlib`,
`time`, `subprocess`). No SDKs, no API keys, no network calls. The optional web
console uses Gradio. MCP over stdio, spec 2025-11-25, implemented by hand.
GitLab Duo Agent Platform (flows + MCP client + agent-config). GitLab CI/CD.
CycloneDX-shaped SBOM output.

## Submission checklist

- [ ] Public GitLab project, MIT LICENSE visible at the top of the repo page
- [ ] Visible CI/CD pipeline history showing all nine stages
- [ ] Demo video under 3 minutes, public on YouTube — see `DEMO_SCRIPT.md`
- [ ] This description pasted into the submission form
- [ ] Path A selected; autonomy level = hands-off
- [ ] "Most Environmentally Impactful" opt-in ticked on the form
- [ ] Optional: Google Cloud deployment link for the 0.2 bonus

## Prize categories this targets

| Category | Amount | Why |
|---|---|---|
| Path A — Best Hands-off Agent | $5,000 | primary submission level |
| Most Stages Covered | $5,000 | all nine, each with inspector + fixer + verification |
| Most Environmentally Impactful | $5,000 | measured SCI + structural wins, opted in |
| Most Creative | $4,000 | autonomy as one auditable parameter, not three code paths |
| Path A — Best Supervised / Assisted | $4,000 each | same machinery, demonstrated in the video |
