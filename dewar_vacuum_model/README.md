# Dewar Vacuum Model

Python model of vacuum bakeout, sealed vacuum life, and cooldown for an
infrared detector dewar (integrated detector–dewar–cooler assembly class).
Companion code to the reference write-up *"Dewar Vacuum Bakeout — Required
Vacuum, Bake Duration, and Vacuum-Life Curves"* (July 2026, saved in the
IR Camera technologies project).

## Quick start

```bash
python3 -m dewar_model.selfcheck            # physics sanity checks (10 asserts)
python3 run_model.py configs/baseline_idca.yaml
```

The runner prints a report (gas-conduction thresholds, water inventory, bake
study, getter budget, cooldown table) and writes four figures to `outputs/`:

| Figure | What it shows |
|---|---|
| `inventory_vs_bake.png` | extractable water vs bake time & temperature, against the no-getter and ice budgets |
| `life_vs_bake.png` | sealed water-only life vs bake duration (the "stop early" cliff), H₂ ceiling, getter regime |
| `cooldown_traces.png` | cold-space temperature vs time at several internal pressures, stall shown |
| `cooldown_vs_pressure.png` | cooldown time vs pressure for a family of effective copper masses |

## The knobs (edit the YAML, don't touch code)

Everything hardware-specific lives in `configs/*.yaml` — copy
`baseline_idca.yaml` and edit. The two knobs this project was built around:

**Adhesive volume and exposed area** — each entry under `adhesives:` is an
independent Fickian water reservoir. The controlling depth is

```
L_eff = volume_cm3 / exposed_area_cm2
```

a slab drying through its exposed face (back face against metal). Total water
content = volume × density × water_wt_pct. A buried bond line that can only
vent at its perimeter should be entered with the small *perimeter* area, which
correctly makes it a deep, slow reservoir. Drying time constant
τ₁ = 4·L_eff²/(π²·D) with D Arrhenius (default: 2×10⁻⁹ cm²/s at 295 K,
E_a = 0.45 eV, epoxy-class).

**Effective copper mass** (`thermal: m_cu_g`) — the copper-equivalent heat
capacity of everything the cold tip must cool (cold shield, platform, focal-
plane array, filter mount). Copper specific heat comes from the Debye model
(θ_D = 343 K), so the strong c_p(T) falloff below 300 K is captured. For
non-copper members convert by specific-heat ratio near ~150 K:
`m_eff ≈ Σ mᵢ·c_pᵢ/c_p,Cu`. Cooldown solves
`m·c_p(T)·dT/dt = −(Q_lift − Q_rad − Q_leads − Q_gas)` with a linear cooler
lift curve between the configured 80 K and 300 K anchor points, and detects
stall (net refrigeration → 0 above setpoint). Note the stall *pressure* is
independent of mass — mass sets how long, load-vs-lift sets whether.

## Package layout

```
dewar_model/
  constants.py    physical constants, torr·L accounting, unit anchors
  gas.py          free-molecular + continuum gas conduction (Corruccini form)
  outgassing.py   surface water (Redhead multi-energy) + Adhesive reservoirs + H2/CH4
  sealed_life.py  post-pinch-off pressure vs storage time, getter capacity model
  cooldown.py     Debye c_p(Cu), cooler lift, load stack, RK integration, stall
  plots.py        figure set (palette-consistent)
  selfcheck.py    asserts against published anchors
run_model.py      CLI: report + figures for a config
configs/          YAML dewar definitions (all units in comments)
outputs/          generated figures
```

## Units

Pressure in torr (1 torr = 133.322 Pa), gas amounts in torr·L at 295 K
(1 mg H₂O ≈ 1.02 torr·L; 1 monolayer ≈ 3.1×10⁻⁵ torr·L/cm²), energies in eV,
temperatures in K (°C only in config bake grids), lengths in cm inside
outgassing code and m inside heat-transfer code (documented per function).

## Physics anchors and self-checks

`python3 -m dewar_model.selfcheck` asserts: Λ₀(air) = 1.18 W·m⁻²·K⁻¹·Pa⁻¹
(Corruccini); the surface model reproduces the empirical 1/t water-outgassing
law (CERN/Chiggiato: ~2×10⁻⁹ torr·L·s⁻¹·cm⁻² at 1 h) within ×1.5 and slope
within ±25 %; unit anchors; slab-kinetics limits and exact two-stage
bake→storage consistency; Debye c_p(Cu) at 300 K and 80 K; and the 293→80 K
enthalpy of the baseline cold mass (~1 kJ for 15 g).


## Uncertainty quantification

`python3 -m dewar_model.sensitivity [N]` runs a Monte Carlo over honest parameter
ranges (adhesive diffusivity/saturation, venting-geometry factor on L_eff, bake
efficiency, dual-stage bound-water fraction, surface-water and H2 parameters) and
prints percentile bands on inventory-after-bake, sealed water-only life, and the
required bake duration for a 10-year target, plus a Spearman tornado of drivers.
`mc_figures.py` renders the band and tornado into `outputs/`. See REVIEW.md for
the full model review and error budget.

## Known limitations (deliberate)

- Bake assumes a perfect pump (no readsorption, no pinch-off-tube conductance
  starvation) — real bakes are somewhat slower; calibrate against your RGA and
  rate-of-rise data.
- Fickian reservoirs use constant D per stage and a perfect-sink boundary;
  knees in the life-vs-bake curve are model-sharp.
- H₂ rate held constant over life (conservative); helium permeation not
  modeled (add as a FixedGas if you have a glass window).
- Cooldown treats the internal pressure as a constant non-condensable
  air-equivalent; in reality water cryopumps out as the shield passes ~150 K,
  so a water-rich soft dewar cools better than this model says — until the ice
  lands on your cold filter.
- Cooler lift is a straight line between two anchors; swap in a measured lift
  map for program work.

## Provenance of default numbers

Chiggiato (CERN Accelerator School) outgassing lecture — water 1/t law, H₂
rates, polymer water content; Redhead JVST A 13, 467 (1995) and 20, 1667
(2002) — desorption model and practices; Corruccini, Vacuum 7–8, 19 (1959) —
free-molecular conduction; Sandia SAND2010-style St 707 getter data and
UChicago PSEC getter notes — capacities and activation; AFRL/DTIC ADA443824 —
water-ice infrared signature (ice budget); Kittel — Debye θ of copper.
Representative geometry/cooler values are stated in the config comments and
should be replaced with your hardware's.
