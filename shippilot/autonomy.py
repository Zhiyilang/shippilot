"""The autonomy dial.

Three levels, one dial, identical machinery underneath:

  assisted   - every single action stops for a human yes/no
  supervised - the run clears its own gates, the human approves the outcome
  hands-off  - the human states intent and walks away; only blockers stop it

The point of the dial is that the *checks* never change. What changes is who is
in the loop. That is what makes autonomy auditable instead of vibes.
"""

from __future__ import annotations

from .model import ASSISTED, HANDS_OFF, SUPERVISED, AUTONOMY


class AutoApprover:
    """Non-interactive approver. Used in CI and in tests."""

    def __init__(self, answer=True):
        self.answer = bool(answer)
        self.log = []

    def __call__(self, prompt):
        self.log.append({"prompt": prompt, "approved": self.answer})
        return self.answer


class ScriptedApprover:
    """Answers from a fixed list, then falls back to `default`. Deterministic."""

    def __init__(self, answers=None, default=True):
        self.answers = list(answers or [])
        self.default = default
        self.log = []

    def __call__(self, prompt):
        answer = self.answers.pop(0) if self.answers else self.default
        self.log.append({"prompt": prompt, "approved": bool(answer)})
        return bool(answer)


def normalize(level):
    if not level:
        return SUPERVISED
    low = str(level).strip().lower().replace("_", "-")
    if low in ("handsoff", "hands-off", "hands_off", "auto", "autonomous"):
        return HANDS_OFF
    if low in ("assist", "assisted"):
        return ASSISTED
    if low in ("supervise", "supervised"):
        return SUPERVISED
    raise ValueError("unknown autonomy level: %r (expected one of %s)" % (level, ", ".join(AUTONOMY)))


def needs_step_approval(level):
    """Assisted stops before every write. The other two do not."""
    return normalize(level) == ASSISTED


def needs_outcome_approval(level):
    """Hands-off is the only level that never asks."""
    return normalize(level) != HANDS_OFF


def describe(level):
    return {
        ASSISTED: "Human approves every action before it is applied.",
        SUPERVISED: "Pipeline clears its own gates; human approves the outcome.",
        HANDS_OFF: "Human states intent and walks away; blockers still stop the ship.",
    }[normalize(level)]


def decide(findings, level):
    """Turn residual findings into a ship decision. Pure arithmetic, no judgement."""
    level = normalize(level)
    blockers = [f for f in findings if f["severity"] == "blocker"]
    highs = [f for f in findings if f["severity"] == "high"]
    mediums = [f for f in findings if f["severity"] == "medium"]
    if blockers:
        return "NO_GO", "blockers remain: " + ", ".join(sorted({f["rule"] for f in blockers}))
    if highs or mediums:
        if level == ASSISTED:
            return "HOLD_FOR_HUMAN", "%d high / %d medium findings need a human decision" % (len(highs), len(mediums))
        return "SHIP_WITH_CAVEATS", "%d high / %d medium findings accepted under %s autonomy" % (
            len(highs), len(mediums), level)
    return "SHIP", "no findings above low severity"
