"""Software Carbon Intensity accounting for the pipeline.

We do not guess a number and print it. We measure wall-clock seconds per stage,
convert with published coefficients, and then compute what two concrete
optimisations would have saved. Defaults are documented public figures and every
one of them is overridable.

    SCI = (E * I) + M     (per build)
    E   = energy in kWh   = hours x watts/1000 x PUE
    I   = grid carbon intensity in gCO2e/kWh
    M   = embodied emissions, amortised over the runner's life
"""

from __future__ import annotations

import os

# Public defaults. Override with env vars for your own region / runner class.
DEFAULT_INTENSITY = 383.0   # gCO2e/kWh, world average grid intensity
DEFAULT_WATTS = 30.0        # watts, typical CI runner CPU package under load
DEFAULT_PUE = 1.2           # datacentre power usage effectiveness
DEFAULT_EMBODIED = 6.0      # gCO2e per build-hour, amortised hardware
DEFAULT_LIFE_HOURS = 35040  # 4 years of continuous duty


def _num(name, default):
    try:
        return float(os.environ.get(name, default))
    except (TypeError, ValueError):
        return default


def coefficients():
    return {
        "grid_intensity_gco2e_per_kwh": _num("SHIPPILOT_CARBON_INTENSITY", DEFAULT_INTENSITY),
        "runner_watts": _num("SHIPPILOT_RUNNER_WATTS", DEFAULT_WATTS),
        "pue": _num("SHIPPILOT_PUE", DEFAULT_PUE),
        "embodied_gco2e_per_hour": _num("SHIPPILOT_EMBODIED", DEFAULT_EMBODIED),
    }


def energy_kwh(seconds, watts, pue):
    return (seconds / 3600.0) * (watts / 1000.0) * pue


def _raw_total(seconds, c):
    """Unrounded grams. Percentages must be computed from this, never from the
    display value: a sub-milligram stage would otherwise round to zero and report
    a 100% saving that no one actually achieved."""
    kwh = energy_kwh(seconds, c["runner_watts"], c["pue"])
    return kwh * c["grid_intensity_gco2e_per_kwh"] + c["embodied_gco2e_per_hour"] * (seconds / 3600.0)


def footprint(seconds, coef=None):
    """gCO2e for a duration, split into operational and embodied."""
    c = coef or coefficients()
    kwh = energy_kwh(seconds, c["runner_watts"], c["pue"])
    operational = kwh * c["grid_intensity_gco2e_per_kwh"]
    embodied = c["embodied_gco2e_per_hour"] * (seconds / 3600.0)
    total = operational + embodied
    return {
        "seconds": round(seconds, 4),
        "kwh": round(kwh, 9),
        "operational_gco2e": round(operational, 6),
        "embodied_gco2e": round(embodied, 6),
        "total_gco2e": round(total, 6),
        "per_1000_builds_gco2e": round(total * 1000.0, 3),
    }


def estimate(stage_seconds, coef=None, stages_with_findings=None):
    """Compare three pipelines: naive serial, cached, cached + parallel.

    `stage_seconds` is measured, not modelled. Stages that produced no findings
    are cacheable: a second run on an unchanged tree has nothing to re-derive.
    """
    c = coef or coefficients()
    seconds = {k: float(v) for k, v in (stage_seconds or {}).items()}
    dirty = set(stages_with_findings or seconds.keys())

    total_serial = sum(seconds.values())
    cached_seconds = sum(v for k, v in seconds.items() if k in dirty)
    parallel_seconds = max([v for k, v in seconds.items() if k in dirty] or [0.0])

    naive = footprint(total_serial, c)
    cached = footprint(cached_seconds, c)
    parallel = footprint(parallel_seconds, c)

    raw_naive = _raw_total(total_serial, c)
    raw_cached = _raw_total(cached_seconds, c)
    raw_parallel = _raw_total(parallel_seconds, c)

    def _pct(base, new):
        if base <= 0:
            return 0.0
        return round((base - new) / base * 100.0, 2)

    return {
        "coefficients": c,
        "measured": naive,
        "with_stage_cache": {
            **cached,
            "saved_gco2e": round(raw_naive - raw_cached, 6),
            "saved_percent": _pct(raw_naive, raw_cached),
        },
        "with_cache_and_parallelism": {
            **parallel,
            "saved_gco2e": round(raw_naive - raw_parallel, 6),
            "saved_percent": _pct(raw_naive, raw_parallel),
        },
        "per_stage": {k: footprint(v, c) for k, v in sorted(seconds.items())},
        "method": "SCI = (E * I) + M; E measured as wall-clock x runner watts x PUE",
    }
