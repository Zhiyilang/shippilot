"""Core data shapes for ShipPilot.

Everything the orchestrator emits is a plain dict built from the helpers here so
the receipts stay JSON-safe and diffable in CI logs.
"""

from __future__ import annotations

import hashlib
import os

# The nine GitLab DevSecOps lifecycle stages, in pipeline order.
STAGES = (
    "plan",
    "create",
    "verify",
    "package",
    "secure",
    "release",
    "configure",
    "monitor",
    "govern",
)

# Autonomy levels. The dial is the heart of the hackathon brief.
ASSISTED = "assisted"      # human approves every single action
SUPERVISED = "supervised"  # human approves the outcome, agent clears the gates
HANDS_OFF = "hands-off"    # human sets intent and walks away

AUTONOMY = (ASSISTED, SUPERVISED, HANDS_OFF)

_SCORES = {"blocker": 40, "high": 20, "medium": 8, "low": 2}


def finding(rule, stage, severity, message, path=None, line=None, excerpt=None, fix=None):
    """One deterministic observation, always carrying where it came from."""
    return {
        "rule": rule,
        "stage": stage,
        "severity": severity,
        "message": message,
        "path": path,
        "line": line,
        "excerpt": excerpt,
        "fix": fix,
        "score": _SCORES.get(severity, 1),
    }


def risk_score(findings):
    """0-100 debt score. Blockers dominate; the number is monotonic in findings."""
    raw = sum(f.get("score", 1) for f in findings)
    return int(min(100, raw))


def locate(path, needle):
    """Return (line_no, excerpt) for the first line containing needle, or (None, None)."""
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            lines = fh.read().splitlines()
    except OSError:
        return None, None
    for i, line in enumerate(lines, 1):
        if needle in line:
            return i, line.strip()[:160]
    return None, None


def sha256_file(path):
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()[:12]
    except OSError:
        return None


def walk_files(root, exts=None, skip_dirs=None, ignore=None):
    """Deterministic, sorted file walk. Sorted so receipts are byte-stable.

    `ignore` is a list of path prefixes from .shippilotignore - a repository can
    exempt its own fixture data without weakening the check everywhere else.
    """
    skip = set(skip_dirs or (".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build"))
    prefixes = [p.strip("/") for p in (ignore or ()) if p]
    out = []
    for dirpath, dirnames, filenames in os.walk(root):
        rdir = rel(root, dirpath)
        if rdir != "." and any(rdir == p or rdir.startswith(p + "/") for p in prefixes):
            dirnames[:] = []
            continue
        dirnames[:] = sorted(d for d in dirnames if d not in skip)
        for name in sorted(filenames):
            if exts and not name.endswith(tuple(exts)):
                continue
            full = os.path.join(dirpath, name)
            rp = rel(root, full)
            if any(rp == p or rp.startswith(p + "/") for p in prefixes):
                continue
            out.append(full)
    return sorted(out)


def load_ignore(root):
    path = os.path.join(root, ".shippilotignore")
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def rel(root, path):
    try:
        return os.path.relpath(path, root).replace("\\", "/")
    except ValueError:
        return path
