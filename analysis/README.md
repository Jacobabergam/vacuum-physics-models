# analysis/ — session analysis packages

Standalone analyses from the July 2026 dewar-vacuum sessions. Each folder is
self-contained; all figures regenerate from the scripts beside them.

## bakeout_reference/
The original bakeout study: `model.py` (first-generation single-file model:
gas conduction, Redhead surface water, two-population Fickian polymer, sealed
life), `figures.py` (figs 1–4), `build_pdf.py` (markdown → PDF builder),
`dewar_bakeout_reference.md/.pdf` (the write-up: required vacuum, bake
duration, failure modes, procedure), and the four figures.
Superseded for modeling work by `../dewar_vacuum_model/` (config-driven,
Monte Carlo, cooldown) — kept because the write-up and figures reference it.
Regenerate: `python3 figures.py && python3 build_pdf.py`.

## vacuum_sources_review/
The ranked literature review of vacuum-loss mechanisms:
`vacuum_degradation_sources.md/.pdf` (ranking table, per-mechanism calculation
methods, measurement practice, tiered bibliography), `fig_sources.py`
(mechanism-vs-time chart; imports `../../dewar_vacuum_model`), figure PNG,
and its PDF builder.

## onepager_doc_generator/
Generator for the documentation block inserted into `../../bottleneck_pumpdown.html`
(2026-07-30): `build_onepager.py` reads `chart_data.json` (crossover times and
SVG path data computed from `dewar_vacuum_model`) and rewrites the page with
the regime chart, dominance timeline, caveats, metal-surface review, and
references. Re-run after model changes to refresh the page's numbers:
first regenerate `chart_data.json` (see script header), then
`python3 build_onepager.py`.
