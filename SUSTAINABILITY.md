# Sustainability: Software Carbon Intensity of the pipeline

Opt-in submission for the **Most Environmentally Impactful** prize.

## What is measured

Every ShipPilot run times each of the nine stages with `perf_counter()` and
converts the result with the Software Carbon Intensity specification:

```
SCI = (E × I) + M
  E  energy (kWh)   = hours × runner watts ÷ 1000 × PUE
  I  grid carbon intensity (gCO2e/kWh)
  M  embodied emissions, amortised over the runner's service life
```

Stages are timed individually, so `carbon_report` shows which stage costs what
rather than a single blended number.

## Coefficients

| Coefficient | Default | Source | Override |
|---|---|---|---|
| Grid carbon intensity | 383 gCO2e/kWh | world average electricity | `SHIPPILOT_CARBON_INTENSITY` |
| Runner power | 30 W | typical CI runner package under load | `SHIPPILOT_RUNNER_WATTS` |
| PUE | 1.2 | typical cloud datacentre | `SHIPPILOT_PUE` |
| Embodied | 6 gCO2e/build-hour | hardware amortised over ~4 years | `SHIPPILOT_EMBODIED` |

Every one is overridable, because a runner in Quebec and a runner on coal are
not the same pipeline. Defaults are documented rather than tuned to look good.

## The two optimisations, priced

1. **Stage cache.** A stage that returned no findings has nothing to re-derive
   on an unchanged tree. Skipping clean stages costs nothing and removes their
   whole energy line.
2. **Parallelism.** The nine inspectors read files independently. Wall clock
   drops from the sum of stage times to the slowest stage.

Both are reported side by side with the measured baseline, in grams and as a
percentage, and both are computed from unrounded values.

## Why the design is the sustainable part

The measurement is a small win. The structural wins are:

- **No dependencies.** No install step, so no network transfer, no package
  resolution, no container layer rebuild on every pipeline run. The flow image
  is `python:3.12-slim` and the setup script is a print statement.
- **Cacheable by construction.** Because each stage is a pure function of the
  working tree, "did anything change?" is a cheap question. Most CI carbon is
  spent re-deriving things that did not move.
- **Nine stages, one pass.** One process walks the tree once. The alternative —
  nine separate scanners, each a container, each re-resolving dependencies —
  is the industry default and it is roughly an order of magnitude more energy
  for the same answer.
- **Right-sized output.** The receipt is a static HTML file with no fonts, no
  CDN and no analytics. Reviewing a run costs a file open, not a page load.

## Honest limits

- ShipPilot measures its own compute. It does not measure the energy of the
  builds it gates; that requires runner-level telemetry it does not have.
- The embodied figure is an amortised estimate, not a per-machine inventory.
- A single audit of a small repository costs a fraction of a milligram of CO2e.
  The numbers become meaningful per 1,000 builds, which is why the receipt also
  reports `per_1000_builds_gco2e`.
