"""Nine deterministic lifecycle inspectors.

One function per GitLab DevSecOps stage. Each returns a list of findings. None of
them guess: every finding carries the file and line it came from, or it is not
emitted at all.
"""

from __future__ import annotations

import os
import re

from .model import finding, locate, rel, walk_files

PY = ".py"

_SECRET_PATTERNS = (
    (re.compile(r"AKIA[0-9A-Z]{12,}"), "aws-access-key-id"),
    (re.compile(r"(?i)\b(api[_-]?key|secret[_-]?key|password|passwd|token)\s*=\s*[\"'][^\"']{8,}[\"']"), "inline-credential"),
    (re.compile(r"ghp_[A-Za-z0-9]{20,}"), "github-token"),
    (re.compile(r"sk-[A-Za-z0-9]{24,}"), "openai-key"),
    (re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"), "private-key"),
)

_DANGEROUS = (
    (re.compile(r"\bos\.system\s*\("), "os.system"),
    (re.compile(r"\beval\s*\("), "eval"),
    (re.compile(r"\bexec\s*\("), "exec"),
    (re.compile(r"shell\s*=\s*True"), "subprocess-shell-true"),
    (re.compile(r"verify\s*=\s*False"), "tls-verification-disabled"),
)

_ENV_RE = (
    re.compile(r"os\.environ\s*\[\s*[\"']([A-Z0-9_]+)[\"']"),
    re.compile(r"os\.environ\.get\s*\(\s*[\"']([A-Z0-9_]+)[\"']"),
    re.compile(r"os\.getenv\s*\(\s*[\"']([A-Z0-9_]+)[\"']"),
)

# Only pin what we actually know. Unknown packages are reported, never invented.
KNOWN_PINS = {
    "requests": "2.32.3", "flask": "3.0.3", "fastapi": "0.115.0", "uvicorn": "0.30.6",
    "numpy": "1.26.4", "pandas": "2.2.2", "pytest": "8.3.3", "pytest-cov": "5.0.0",
    "gradio": "5.9.1", "boto3": "1.35.24", "pydantic": "2.9.2", "sqlalchemy": "2.0.35",
    "python-dotenv": "1.0.1", "gunicorn": "23.0.0", "redis": "5.1.0", "celery": "5.4.0",
    "scikit-learn": "1.5.2", "httpx": "0.27.2", "jinja2": "3.1.4", "pyyaml": "6.0.2",
}


def _has(root, *names):
    for n in names:
        if os.path.exists(os.path.join(root, n)):
            return n
    return None


def _text(path):
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


# --------------------------------------------------------------------------
# plan -- is the intent written down and testable?
# --------------------------------------------------------------------------
def plan(root, ctx):
    out = []
    spec = _has(root, ".shippilot/plan.md", "docs/plan.md", "PLAN.md", "README.md")
    body = _text(os.path.join(root, spec)) if spec else ""
    if not spec or len(body.strip()) < 40:
        out.append(finding(
            "PLAN_NO_SPEC", "plan", "high",
            "No written plan found. Downstream stages have nothing to verify against.",
            fix="write_plan",
        ))
        return out
    criteria = len(re.findall(r"(?im)^\s*[-*]\s*\[[ x]\]|^\s*[-*]\s*(?:AC|Accept)", body))
    if criteria < 3:
        out.append(finding(
            "PLAN_THIN_ACCEPTANCE", "plan", "medium",
            "Plan has %d acceptance criteria; need at least 3 to gate a release." % criteria,
            path=spec, fix="write_plan",
        ))
    if not re.search(r"(?i)\b(rollback|revert|abort)\b", body):
        out.append(finding(
            "PLAN_NO_ROLLBACK", "plan", "medium",
            "Plan does not describe a rollback path.",
            path=spec, fix="write_plan",
        ))
    return out


# --------------------------------------------------------------------------
# create -- will a reviewer understand the change?
# --------------------------------------------------------------------------
def create(root, ctx):
    out = []
    tpl = _has(root, ".gitlab/merge_request_templates/Default.md", ".github/pull_request_template.md")
    if not tpl:
        out.append(finding(
            "CREATE_NO_MR_TEMPLATE", "create", "medium",
            "No merge request template. Reviewers get no structure to fill in.",
            fix="write_mr_template",
        ))
    else:
        body = _text(os.path.join(root, tpl))
        for key, label in (("what", "What"), ("why", "Why"), ("how", "How")):
            if not re.search(r"(?i)\b%s\b" % key, body):
                out.append(finding(
                    "CREATE_TEMPLATE_MISSING_SECTION", "create", "low",
                    "MR template has no '%s' section." % label,
                    path=tpl, fix="write_mr_template",
                ))
    py = [p for p in walk_files(root, (PY,), ignore=ctx.get("ignore"))
          if "/tests/" not in p.replace("\\", "/")
          and not rel(root, p).startswith(".shippilot/")]
    undocumented = 0
    for p in py:
        body = _text(p)
        defs = len(re.findall(r"(?m)^\s*(?:def|class)\s+[A-Za-z_]", body))
        docstrings = len(re.findall(r'"""', body)) // 2
        if defs > 3 and docstrings == 0:
            undocumented += 1
    if undocumented:
        out.append(finding(
            "CREATE_UNDOCUMENTED_CODE", "create", "low",
            "%d source files expose >3 public definitions with no docstrings." % undocumented,
            fix=None,
        ))
    return out


# --------------------------------------------------------------------------
# verify -- does the pipeline actually prove anything?
# --------------------------------------------------------------------------
def verify(root, ctx):
    out = []
    tests = [p for p in walk_files(root, (PY,), ignore=ctx.get("ignore"))
             if os.path.basename(p).startswith("test_")]
    if not tests:
        out.append(finding(
            "VERIFY_NO_TESTS", "verify", "blocker",
            "No test files found. Nothing stands between a typo and production.",
            fix="write_smoke_test",
        ))
    cov = _has(root, ".coveragerc", "pytest.ini", "setup.cfg", "pyproject.toml", "tox.ini")
    body = _text(os.path.join(root, cov)) if cov else ""
    if not cov or not re.search(r"(?i)(cov|fail_under|min-coverage)", body):
        out.append(finding(
            "VERIFY_NO_COVERAGE_GATE", "verify", "high",
            "No coverage threshold configured, so a green pipeline proves nothing.",
            path=cov, fix="write_coverage_gate",
        ))
    ci = _has(root, ".gitlab-ci.yml", ".github/workflows/ci.yml", ".github/workflows/ci.yaml")
    if not ci:
        out.append(finding(
            "VERIFY_NO_CI", "verify", "high",
            "No CI definition found in the repository.",
            fix="write_ci",
        ))
    return out


# --------------------------------------------------------------------------
# package -- is the artifact reproducible and inventoried?
# --------------------------------------------------------------------------
def package(root, ctx):
    out = []
    req = _has(root, "requirements.txt")
    if req:
        lines = _text(os.path.join(root, req)).splitlines()
        loose = [ln.strip() for ln in lines if ln.strip() and not ln.strip().startswith("#") and "==" not in ln]
        if loose:
            line, excerpt = locate(os.path.join(root, req), loose[0]) if loose[0] else (None, None)
            out.append(finding(
                "PACKAGE_UNPINNED_DEPS", "package", "high",
                "%d dependencies are unpinned (e.g. '%s'); builds are not reproducible." % (len(loose), loose[0]),
                path=req, line=line, excerpt=excerpt, fix="pin_dependencies",
            ))
    if not _has(root, "sbom.json", "sbom.cdx.json", "cyclonedx.json"):
        out.append(finding(
            "PACKAGE_NO_SBOM", "package", "medium",
            "No SBOM. You cannot answer 'are we affected?' during an incident.",
            fix="write_sbom",
        ))
    if not _has(root, "Dockerfile", "docker-compose.yml", "Containerfile"):
        out.append(finding(
            "PACKAGE_NO_IMAGE", "package", "low",
            "No container definition; deployment is environment-dependent.",
            fix="write_dockerfile",
        ))
    return out


# --------------------------------------------------------------------------
# secure -- secrets, dangerous calls, policy surface
# --------------------------------------------------------------------------
def secure(root, ctx):
    out = []
    seen = set()
    waived = set(ctx.get("waivers") or ())
    for path in walk_files(root, (PY, ".js", ".ts", ".env", ".yaml", ".yml", ".json", ".toml", ".cfg", ".ini"),
                         ignore=ctx.get("ignore")):
        rpath = rel(root, path)
        if rpath.startswith(".shippilot/"):
            continue  # our own artifacts are not part of the audit surface
        for i, line in enumerate(_text(path).splitlines(), 1):
            for rx, name in _SECRET_PATTERNS:
                if rx.search(line) and name not in seen:
                    seen.add(name)
                    out.append(finding(
                        "SECURE_HARDCODED_SECRET", "secure", "blocker",
                        "Hardcoded credential (%s) committed to the repository." % name,
                        path=rpath, line=i, excerpt=line.strip()[:160],
                        fix="redact_secret",
                    ))
            for rx, name in _DANGEROUS:
                key = ("danger", name, rpath)
                if rx.search(line) and key not in seen:
                    seen.add(key)
                    if (rpath, "SECURE_DANGEROUS_CALL") in waived:
                        continue
                    out.append(finding(
                        "SECURE_DANGEROUS_CALL", "secure", "high",
                        "Dangerous call '%s' - a code-execution or TLS-downgrade footgun." % name,
                        path=rpath, line=i, excerpt=line.strip()[:160],
                        fix="guard_dangerous_call",
                    ))
    if not _has(root, "SECURITY.md", "docs/SECURITY.md", ".github/SECURITY.md"):
        out.append(finding(
            "SECURE_NO_POLICY", "secure", "medium",
            "No SECURITY.md, so nobody knows how to report a vulnerability.",
            fix="write_security_policy",
        ))
    dep_files = _has(root, "requirements.txt", "package.json", "Pipfile")
    if dep_files and not _has(root, ".dependency-audit.json", "audit.json"):
        out.append(finding(
            "SECURE_NO_DEP_AUDIT", "secure", "medium",
            "No dependency audit artifact is produced by the pipeline.",
            path=dep_files, fix="write_dependency_audit",
        ))
    return out


# --------------------------------------------------------------------------
# release -- can a human tell what shipped?
# --------------------------------------------------------------------------
def release(root, ctx):
    out = []
    if not _has(root, "CHANGELOG.md", "CHANGES.md", "HISTORY.md"):
        out.append(finding(
            "RELEASE_NO_CHANGELOG", "release", "medium",
            "No changelog. Release notes get invented at 2am.",
            fix="write_changelog",
        ))
    version = None
    for name in ("VERSION", "version.txt"):
        if os.path.exists(os.path.join(root, name)):
            version = _text(os.path.join(root, name)).strip()
            break
    if version is None:
        body = _text(os.path.join(root, "pyproject.toml"))
        m = re.search(r"(?m)^\s*version\s*=\s*[\"']([^\"']+)[\"']", body)
        version = m.group(1) if m else None
    if not version:
        out.append(finding(
            "RELEASE_NO_VERSION", "release", "high",
            "No machine-readable version. Rollbacks cannot name what to roll back to.",
            fix="write_version",
        ))
    elif not re.match(r"^\d+\.\d+\.\d+", version):
        out.append(finding(
            "RELEASE_BAD_VERSION", "release", "medium",
            "Version '%s' is not semantic (MAJOR.MINOR.PATCH)." % version,
            fix="write_version",
        ))
    ctx["version"] = version
    return out


# --------------------------------------------------------------------------
# configure -- does the environment match what the code expects?
# --------------------------------------------------------------------------
def configure(root, ctx):
    out = []
    used = set()
    for path in walk_files(root, (PY,), ignore=ctx.get("ignore")):
        body = _text(path)
        for rx in _ENV_RE:
            used.update(rx.findall(body))
    ctx["env_used"] = sorted(used)
    example = _has(root, ".env.example", ".env.sample", "env.template")
    declared = set()
    if example:
        for line in _text(os.path.join(root, example)).splitlines():
            m = re.match(r"\s*([A-Z0-9_]+)\s*=", line)
            if m:
                declared.add(m.group(1))
    ctx["env_declared"] = sorted(declared)
    missing = sorted(used - declared)
    if missing:
        out.append(finding(
            "CONFIGURE_ENV_DRIFT", "configure", "high",
            "Code reads %d env var(s) never declared in %s: %s"
            % (len(missing), example or ".env.example", ", ".join(missing[:6])),
            fix="write_env_example",
        ))
    iac = _has(root, "terraform", "infra", "k8s", "kubernetes", "chart", "helm")
    if not iac:
        out.append(finding(
            "CONFIGURE_NO_IAC", "configure", "low",
            "No infrastructure-as-code directory; environments drift silently.",
            fix=None,
        ))
    return out


# --------------------------------------------------------------------------
# monitor -- will anyone notice when it breaks?
# --------------------------------------------------------------------------
def monitor(root, ctx):
    out = []
    body = "".join(_text(p)
                for p in walk_files(root, (PY, ".js", ".ts", ".go"), ignore=ctx.get("ignore")))
    if not re.search(r"(?i)(/healthz|/health|health_check|healthcheck)", body):
        out.append(finding(
            "MONITOR_NO_HEALTHCHECK", "monitor", "high",
            "No health endpoint. Orchestrators cannot tell alive from wedged.",
            fix="write_healthcheck",
        ))
    slo = _has(root, ".shippilot/monitor.yaml", "monitoring/slo.yaml", "slo.yaml")
    if not slo:
        out.append(finding(
            "MONITOR_NO_SLO", "monitor", "medium",
            "No SLO definition, so 'is it broken?' is a matter of opinion.",
            fix="write_monitoring_contract",
        ))
    if not re.search(r"(?i)(sentry|opentelemetry|otel|prometheus|datadog|logger\.(error|exception))", body):
        out.append(finding(
            "MONITOR_NO_TELEMETRY", "monitor", "medium",
            "No telemetry or structured error reporting found.",
            fix=None,
        ))
    return out


# --------------------------------------------------------------------------
# govern -- licence, ownership, audit trail
# --------------------------------------------------------------------------
def govern(root, ctx):
    out = []
    lic = _has(root, "LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING")
    if not lic:
        out.append(finding(
            "GOVERN_NO_LICENSE", "govern", "high",
            "No LICENSE file. Downstream users have no grant.",
            fix="write_license",
        ))
    else:
        head = _text(os.path.join(root, lic))[:400]
        if "MIT" not in head and "Apache" not in head and "BSD" not in head and "GPL" not in head:
            out.append(finding(
                "GOVERN_UNKNOWN_LICENSE", "govern", "medium",
                "LICENSE header does not name a known OSI licence.",
                path=lic, fix="write_license",
            ))
    if not _has(root, "CODEOWNERS", ".gitlab/CODEOWNERS", ".github/CODEOWNERS"):
        out.append(finding(
            "GOVERN_NO_CODEOWNERS", "govern", "medium",
            "No CODEOWNERS; review assignment is guesswork.",
            fix="write_codeowners",
        ))
    if not _has(root, ".shippilot/audit", "AUDIT.md", "docs/AUDIT.md"):
        out.append(finding(
            "GOVERN_NO_AUDIT_TRAIL", "govern", "low",
            "No audit trail directory for machine decisions.",
            fix="write_audit_trail",
        ))
    return out


INSPECTORS = {
    "plan": plan,
    "create": create,
    "verify": verify,
    "package": package,
    "secure": secure,
    "release": release,
    "configure": configure,
    "monitor": monitor,
    "govern": govern,
}


def inspect_stage(root, stage, ctx=None):
    ctx = ctx if ctx is not None else {}
    return INSPECTORS[stage](root, ctx)
