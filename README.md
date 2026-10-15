# ShipPilot

**Code generation is solved. The nine stages after it are not.**

ShipPilot automates the post-code DevSecOps lifecycle — plan, create, verify,
package, secure, release, configure, monitor, govern — with one autonomy dial
that decides how much control you hand over.

```
Agents propose. The verifier decides what counts. The gate decides what ships.
```

Built for **Life After Code** (the GitLab Transcend Hackathon). Python standard
library only — no SDKs, no API keys, no network calls. It runs the same in CI,
on a laptop, and inside an air-gapped sandbox.

---

## The dial

| Level | What the human approves | What it means in the pipeline |
|---|---|---|
| `assisted` | every action | stops before every single write |
| `supervised` | the outcome | clears its own gates, stops once at the end |
| `hands-off` | nothing | states intent, walks away, ships if the verifier clears it |

One dial, one set of checks. The inspectors never change — only who is in the
loop. That is what makes autonomy auditable rather than a matter of taste.

A blocker is not negotiable at any level. `hands-off` will happily fix nineteen
things on its own and still refuse to ship on the twentieth.

## Quick start

```bash
python eval.py                                    # 245 assertions, offline
python -m shippilot audit --root .                # inspect, write nothing
python -m shippilot audit --root . --stage secure # one stage
python -m shippilot ship  --root . --autonomy supervised
python -m shippilot mcp                           # MCP server, stdio
python app.py                                     # web console (needs gradio)
```

`audit` exits `2` when blockers remain, `1` when a human decision is pending,
`0` when the ship is clean. That makes it a CI gate rather than a report.

## What it actually finds

Nine inspectors, each deterministic, each carrying the file and line it came
from. Nothing is inferred; a finding without evidence is not emitted.

| Stage | Sample rules |
|---|---|
| plan | `PLAN_NO_SPEC`, `PLAN_THIN_ACCEPTANCE`, `PLAN_NO_ROLLBACK` |
| create | `CREATE_NO_MR_TEMPLATE`, `CREATE_TEMPLATE_MISSING_SECTION`, `CREATE_UNDOCUMENTED_CODE` |
| verify | `VERIFY_NO_TESTS`, `VERIFY_NO_COVERAGE_GATE`, `VERIFY_NO_CI` |
| package | `PACKAGE_UNPINNED_DEPS`, `PACKAGE_NO_SBOM`, `PACKAGE_NO_IMAGE` |
| secure | `SECURE_HARDCODED_SECRET`, `SECURE_DANGEROUS_CALL`, `SECURE_NO_POLICY` |
| release | `RELEASE_NO_CHANGELOG`, `RELEASE_NO_VERSION`, `RELEASE_BAD_VERSION` |
| configure | `CONFIGURE_ENV_DRIFT`, `CONFIGURE_NO_IAC` |
| monitor | `MONITOR_NO_HEALTHCHECK`, `MONITOR_NO_SLO`, `MONITOR_NO_TELEMETRY` |
| govern | `GOVERN_NO_LICENSE`, `GOVERN_NO_CODEOWNERS`, `GOVERN_NO_AUDIT_TRAIL` |

## Prove-then-act

Every fix is applied by a deterministic fixer, then **the inspector that flagged
it is re-run**. A fix counts as done only when the check stops flagging it. The
receipt records `applied` and `verified` as separate numbers on purpose — a run
that applied twenty fixes and verified nineteen tells you about the twentieth.

Some findings have no automatic fix. `eval()` inside application code is not
something a pipeline should rewrite on its own, so ShipPilot writes a **risk
acceptance waiver** to `.shippilot/waivers.json` naming the file, the rule and
the reason, and moves on. Waiving one rule never waives another.

## GitLab Duo Agent Platform

ShipPilot is wired into the platform three ways, all committed to the repo:

- **MCP client** — `.gitlab/duo/mcp.json` registers the stdio server; Duo calls
  the seven tools directly (`audit_repo`, `plan_lifecycle`, `apply_fix`,
  `ship_repo`, `carbon_report`, `render_receipt`, `list_lifecycle`).
- **Flows** — `.gitlab/duo/flows/post_code_{assisted,supervised,hands_off}.yml`,
  one per autonomy level, with `tool_overrides` pinning tool parameters so the
  model cannot drift from the contract.
- **Agent config** — `.gitlab/duo/agent-config.yml`. The image is
  `python:3.12-slim` and the setup script is a print statement, because there is
  nothing to install.

The repository's own `.gitlab-ci.yml` has nine stages plus a `shippilot-ship`
job, so the pipeline history the judges look at *is* the automation running.

## Carbon

Every run measures wall-clock seconds per stage and converts them with the SCI
formula `(E × I) + M`, then prices two concrete optimisations: skipping stages
that came back clean, and running the dirty stages in parallel. Defaults are
published public figures and every coefficient is overridable. See
[SUSTAINABILITY.md](SUSTAINABILITY.md).

## Receipts

`.shippilot/audit/` gets a JSON receipt per run and a self-contained HTML page:
nine stage tiles, the decision, before/after risk score, every action with its
verification state, and the carbon numbers. No CDN, no fonts, no tracking — it
opens from an artifact folder three weeks later.

## Dogfooding

ShipPilot audits itself (`shippilot-self-audit` in CI). `.shippilotignore`
exempts exactly one path: the deliberately broken fixture the demo and tests run
against. Everything else is fair game.

## Layout

```
shippilot/
  model.py         finding/receipt shapes, deterministic file walk
  stages.py        nine inspectors
  remedy.py        twenty deterministic fixers + risk waivers
  autonomy.py      the dial: assisted / supervised / hands-off
  orchestrator.py  PERCEIVE -> PLAN -> GATE -> ACT -> OBSERVE -> VERIFY -> RECEIPT
  carbon.py        SCI accounting
  mcp_server.py    MCP stdio (spec 2025-11-25), seven tools
  cli.py  receipt.py
app.py             Gradio console, also exposes /gradio_api/mcp/
examples/demo_repo a small repository with eighteen planted defects
eval.py            245 assertions
.gitlab/duo/       agent-config.yml, mcp.json, three flows
```

## Tests

```
python eval.py
```

245 assertions, no network, no fixtures to download. Includes a real MCP
subprocess session, real CLI subprocesses, a lying-fixture check (a clean
repository must not trigger any of the nineteen rules), HTML injection escaping,
and a rogue-input check for missing repositories.

## Definition of done

A change to ShipPilot is shippable when:

- [ ] `python eval.py` passes with zero failures
- [ ] any new rule has both a positive case and a negative case in `eval.py`
- [ ] any new fixer is proven by re-running the inspector that flagged it
- [ ] a clean repository still triggers none of the nineteen rules

## Rollback

Every release is a tag. Reverting a release is `git revert` plus a redeploy of
the previous tag — receipts are append-only files, so no migration is ever
required to roll back. A waiver in `.shippilot/waivers.json` can be removed on
its own without touching code.

## Licence

MIT.
