# Getting ShipPilot onto GitLab

The hackathon requires the submission to live in a **public GitLab project with
visible CI/CD pipeline history**. GitHub is pushed and ready; this is the part
only you can do, because it needs a GitLab account.

**Deadline: Oct 28, 2026 @ 2:00am GMT+13** (Oct 27, ~21:00 Beijing).

---

## 1. Create the account

- Sign up at <https://gitlab.com> (free).
- **Start a GitLab Ultimate trial** (30 days, no charge). Two reasons:
  - shared CI runners on gitlab.com require verification for free accounts, and
    the trial removes that friction entirely;
  - the Duo Agent Platform features the submission depends on are Ultimate.

## 2. Import the repository

- **New project → Import project → Repository by URL**
- Source: `https://github.com/Zhiyilang/shippilot`
- Name: `shippilot`, visibility: **Public**
- Do **not** enable "mirror" — the repo should be a real GitLab project, not a
  mirror, because the pipeline history has to be generated there.

The MIT `LICENSE` file lands at the top of the repo page, which is a stated
requirement.

## 3. Turn on the pipeline

- **Settings → CI/CD → Runners**: confirm shared runners are available.
- **Build → Pipelines → Run pipeline** on `main`, or just push a commit.

Nine jobs run, one per stage, plus `shippilot-ship-assisted`,
`shippilot-ship-hands-off` and `shippilot-self-audit`. That history is the
evidence the judges look for — leave the project public and do not delete
pipelines.

If a runner is unavailable, `Build → Pipelines → New pipeline` will say so and
the page will offer to register your own runner. The trial avoids this.

## 4. Turn on Duo Agent Platform

- **Settings → General → GitLab Duo**: enable Agent Platform / flows.
- The repo ships `.gitlab/duo/agent-config.yml`, `.gitlab/duo/mcp.json` and three
  flows under `.gitlab/duo/flows/`. GitLab reads `agent-config.yml` from the
  default branch only.
- `mcp.json` may need Code Owners approval the first time it is used.

## 5. Then

- Record the demo video — see `DEMO_SCRIPT.md` (2:45, scripted shot by shot).
- Submit on Devpost — every field is pre-written in `SUBMISSION.md`.
- Tick: Path A, autonomy = hands-off, and the **Most Environmentally Impactful**
  opt-in.

---

## What I need from you

| Step | Who | Status |
|---|---|---|
| Code, tests, docs, MCP, flows, CI config | done | 245/245 assertions green |
| GitHub repo `Zhiyilang/shippilot` | done | public |
| GitLab account + import + run pipeline | **you** | ~20 min |
| Demo video | **you** | ~30 min, script ready |
| Devpost submit (I can drive the browser once you're logged in) | together | 10 min |
