# Demo script — 2 min 45 s

Record at 1080p, terminal font large enough to read, no background music.
Show the terminal, not slides.

---

**0:00 — Hook (15 s)**

> "Code generation is solved. I wrote this repository in about ninety seconds.
> Now: is it shippable? There are nine stages after the code, and nobody has
> looked at any of them."

Show `examples/demo_repo` — three files, one of them with an AWS key sitting in
plain text.

**0:15 — The audit (25 s)**

```bash
python -m shippilot audit --root examples/demo_repo
```

Scroll the output once. Eighteen findings, blocker at the top.

> "Eighteen findings across all nine stages. Note each one has a file and a
> line. Nothing here is a guess — if it can't point at evidence, it doesn't get
> emitted."

**0:40 — The dial (45 s)** ← *the memory hook*

```bash
python -m shippilot ship --root examples/demo_repo --autonomy assisted --deny-all
```

> "Assisted, and I'm answering no to everything. Nothing applied, decision
> NO_GO."

```bash
python -m shippilot ship --root examples/demo_repo --autonomy hands-off
```

> "Same checks, no human in the loop. Twenty actions applied, nineteen verified,
> risk score 100 to 32, coverage nine out of nine. And it still reports the one
> it couldn't confirm."

Point at `unresolved` line.

> "That number is the point. Applied and verified are separate on purpose."

**1:25 — Proof, not claim (30 s)**

Open `.shippilot/audit/receipt.html`.

> "Nine tiles, one per stage. Green means the check that flagged it stopped
> flagging it. Everything here is written to disk as JSON too, append-only —
> that's the audit trail."

Show `git status` — twenty files created or changed, all deterministic.

**1:55 — GitLab Duo (30 s)**

Show `.gitlab/duo/mcp.json`, then the three flow files.

> "Seven MCP tools over stdio, so GitLab Duo drives the same machinery from a
> flow. One flow per autonomy level. `tool_overrides` pins the parameters, so
> the model can't drift."

Show the project's own `.gitlab-ci.yml` — nine stages.

> "And this repo's pipeline history *is* the automation running."

**2:25 — Carbon + close (20 s)**

> "It times every stage and prices the SCI. Skipping clean stages and running
> the dirty ones in parallel — here's what that saves."

> "Agents propose. The verifier decides what counts. The gate decides what
> ships. ShipPilot."

---

## YouTube metadata

**Title:** ShipPilot — nine DevSecOps stages, one autonomy dial (GitLab
Transcend)

**Tags:** `gitlab`, `devsecops`, `ai agents`, `mcp`, `cicd`, `devops`,
`transcend`, `shippilot`

**Description:** ShipPilot automates the post-code DevSecOps lifecycle across
nine stages with a single autonomy dial: assisted, supervised, hands-off. The
same deterministic inspectors run at every level — only who is in the loop
changes. Every fix is re-verified by the check that flagged it, so "applied" and
"verified" are separate numbers. Exposed as seven MCP tools over stdio and wired
into GitLab Duo Agent Platform flows. Python standard library only, zero
dependencies. Repo: https://github.com/Zhiyilang/shippilot

**Check before upload:** under 3:00 · publicly visible · no third-party
trademarks in frame · no music.
