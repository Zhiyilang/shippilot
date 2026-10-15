# ShipPilot design

## The problem behind the brief

"Life After Code" asks how much of the DevSecOps lifecycle you can hand to an
agent. The tempting answer is to wire an LLM to a shell and let it run. That
answer fails in one specific way: **the agent's output is not evidence.** When a
model says "I fixed the security finding", there is nothing to check that
against, so autonomy becomes a confidence trick — the more you hand over, the
less you know.

ShipPilot inverts it. The lifecycle is modelled as deterministic inspectors
first. An agent's job is to *choose* among known fixes, never to invent one, and
never to grade its own homework.

## Three roles, kept separate

| Role | Can do | Cannot do |
|---|---|---|
| Agent / flow | propose which fix to run, order the work, decide when to stop | write a file, declare success |
| Verifier | re-run the inspector, compare counts | change anything |
| Gate | apply arithmetic to residual findings | override a blocker |

The signature line is the whole architecture:

> Agents propose. The verifier decides what counts. The gate decides what ships.

## The loop

```
PERCEIVE  run nine inspectors, time each one
PLAN      collect findings whose rule has a known fixer, order by severity
GATE      assisted -> ask before every action; supervised/hands-off -> proceed
ACT       one deterministic fixer per finding
OBSERVE   re-run the inspector for that stage
VERIFY    the fix counts only if the rule stopped firing
RECEIPT   JSON + HTML, append-only into .shippilot/audit/
```

`applied` and `verified` are reported as separate numbers. A run showing
"20 applied, 19 verified" is a run that worked — the twentieth is the interesting
one, and hiding it would be the bug.

## Why the dial is a parameter, not three code paths

`autonomy.py` is 90 lines. `needs_step_approval()` and `needs_outcome_approval()`
are the only places the level is consulted. The inspectors, fixers and verifier
never see it.

This matters for the hackathon's judging criterion *"does the code reflect
genuine effort"*: the same 245 assertions pass at all three levels because there
is only one implementation to test. Autonomy is a policy, not a fork.

## Things we deliberately do not automate

- **Rewriting `eval()` / `shell=True`.** Auto-replacing these is how a pipeline
  breaks production quietly. ShipPilot writes a waiver naming file, rule and
  reason instead, and reports it as unresolved.
- **Pinning unknown dependencies.** `KNOWN_PINS` holds real versions for ~20
  packages. Anything else stays unpinned and stays in the report rather than
  getting `==0.0.0` invented for it.
- **Predicting next steps for unfixable findings.** Rules with `fix: null` are
  surfaced as `needs_a_human` in `plan_lifecycle`. They never silently vanish.

## Carbon: measured, then priced

The naive version of "green CI" prints a number nobody can audit. ShipPilot
measures wall-clock seconds per stage, converts with `SCI = (E × I) + M`, and
then computes the delta for two changes a team can actually make: skip stages
that came back clean, and run the dirty ones in parallel.

Percentages are computed from unrounded grams. A sub-milligram stage rounding to
zero would otherwise report a 100% saving nobody achieved — so
`_raw_total()` exists specifically to prevent that.

## Failure modes handled

| Situation | Behaviour |
|---|---|
| Fixer raises | recorded as `error` on the action, run continues |
| Fix applied but rule still fires | `verified: false`, listed in `unresolved` |
| Repository path missing | inspectors return empty, audit still prints a score |
| Approver unavailable | non-interactive default; `assisted` + deny-all yields nothing applied |
| Blocker survives | `NO_GO` at every autonomy level, exit code 2 |
| Malicious repo name in receipt | HTML-escaped; asserted in the suite |

## Zero dependencies, on purpose

The post-code lifecycle is exactly the place where adding an SDK adds a supply
chain finding. ShipPilot has none, so `SECURE_NO_DEP_AUDIT` and `PACKAGE_NO_SBOM`
stay meaningful for the repositories it audits rather than for itself. Gradio is
optional and lives behind `app.py`.
