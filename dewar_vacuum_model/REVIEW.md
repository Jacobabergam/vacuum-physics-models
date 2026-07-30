# Model Review — Adhesive & Metal Outgassing Accuracy, Directional Correctness, and Error Budget

*July 16, 2026 · Covers `dewar_model/outgassing.py` (our package), your `bottleneck_pumpdown.py`, the new `dewar_model/sensitivity.py` Monte Carlo module, and the error question: how wrong can the water-outgassing model be, both from its own parameters and from the vacuum-loss mechanisms it does not include.*

---

## 1. Verdict: directionally correct, with four independent anchors

1. **It reproduces the empirical law it did not assume.** The multi-energy surface model integrates to the published 1/t water pump-down law within ×1.5 of the CERN coefficient (2.2×10⁻⁹ torr·L·s⁻¹·cm⁻² at 1 h) over three decades of time — checked in `selfcheck.py`.
2. **It reproduces industry bake practice** (one to two weeks at 85 °C assembled; days at 100–125 °C) from physics constants, not curve-fitting.
3. **It agrees with your independent model.** Your `bottleneck_pumpdown.py` uses an adhesive water source of 5×10⁻⁵ torr·L·s⁻¹·cm⁻² at 85 °C, 1 h into the bake. Our Fickian early-time flux, c₀·√(D/π·t) with nominal epoxy parameters, gives 2.4×10⁻⁵ at the same point — **agreement within ×2 from two different starting points.**
4. **Monte Carlo medians bracket the nominal curves** rather than running away from them (Fig. `outputs/mc_life_band.png`) — no structural pathology.

So: use it with confidence for *shape, scaling, and design margin*. Do not use it for absolute life prediction at a fixed bake — Section 4 quantifies why.

## 2. Review findings — our models

**Adhesive (Fickian reservoir) model.** Ranked by impact, with bias direction; each now carried as an explicit uncertainty in `sensitivity.py`:

| # | Assumption | Reality | Bias | Now captured as |
|---|---|---|---|---|
| 1 | L_eff = volume/exposed-area slab | buried bond lines vent via perimeter/labyrinth; effective depth larger | optimistic | `L_geom` ×0.5–2.5 — **the top driver** (ρ ≈ +0.5) |
| 2 | Single literature D | epoxy D spans decades of formulations | either | `D_295` 5×10⁻¹⁰–8×10⁻⁹ cm²/s — second driver (ρ ≈ −0.4) |
| 3 | Perfect sink during bake | readsorption + pinch-off-tube conductance starvation slow real bakes | optimistic | `f_bake` 0.3–1 |
| 4 | Single-stage Fickian sorption | epoxy compounds show **dual-stage / non-Fickian** uptake with a bound-water tail that Fickian fits miss (well documented for molding compounds) | optimistic late-time | `f_bound` 0–0.4 of inventory at D/30 |
| 5 | Fixed saturation (1 wt %) | 0.3–3 wt % by resin chemistry and humidity history | either | `c_sat` range |
| 6 | Water only | epoxies also emit organics (ASTM E595 CVCM species) | small for pressure; real for cold-optics contamination | noted, not modeled |

**Metal-container model.** The uniform binding-energy window (0.75–1.15 eV, ν = 10¹³ s⁻¹) vs literature (0.9–1.06 eV, ν spread 10¹²–10¹⁴) turns out to be almost irrelevant to the outputs that matter: after any competent bake the surface term is gone, and the tornado puts `N_ML`, `E_hi`, `ν` at the bottom (|ρ| ≤ 0.06). Two things about metals *do* matter: (a) the **hydrogen band** — we hold q_H₂ constant at 10⁻¹³–3×10⁻¹² torr·L·s⁻¹·cm⁻²; ignoring its slow √t decay is conservative by ≤×3, while the band itself is a full decade — it dominates *ungettered* life uncertainty; (b) the published spread on unbaked water rates is enormous (Grinham & Chew's "fresh stainless" 2.2×10⁻⁷ vs CERN's 1-h 2.2×10⁻⁹ — different clock-zeros and histories), which is exactly why the model carries ranges, not point values.

## 3. Review findings — your `bottleneck_pumpdown.py`

The core is right: end-corrected molecular conductance (12.1·d³/(L+1.333d)), the Poiseuille viscous form (180·d⁴·P̄/L), an additive Knudsen bridge, a stable backward-Euler two-volume integrator with sensible adaptive stepping, and — the best part — the **RGA-attenuation result** (manifold water reads lower than chamber water by ≈ S/C) falls out of it, which is the same conductance-starvation effect our bake analysis flags. Nits, none of which change conclusions: (1) the viscous conductance for the water species uses the air coefficient — water vapor's viscosity is ~0.55× air's, so its viscous conductance is ~1.9× higher; only matters near-viscous. (2) Treating species as independently conducted is wrong in the viscous regime (water is *entrained* by the air bulk flow early on), making your early water removal slightly pessimistic. (3) Conductances are evaluated at 20 °C while the gas is at 85 °C — molecular conductance scales as √T, about +10 %. (4) The additive viscous+molecular bridge overshoots the true Knudsen-minimum region by ~15 %. (5) The 1/t source with a 60 s floor never depletes by construction — swap in the package's reservoir-depleting Fickian source (`Adhesive.released_after_seal_mg` logic) and your model will show a bake *endpoint*, which the 1/t form cannot.

## 4. Error quantification

**(a) Within-model parameter uncertainty** (Monte Carlo, N = 800, 85 °C bake, log-uniform ranges of Section 2):

| Output | Median | 68 % band | Read |
|---|---|---|---|
| Extractable water after 7 d bake | 0.11 torr·L | 1.9×10⁻⁴ – 0.75 torr·L | inventory known only to **×/÷ ~25** (68 %) |
| Extractable water after 14 d | 1.5×10⁻² torr·L | 8×10⁻⁸ – 0.37 torr·L | worse — you are on the cliff |
| Water-only sealed life, 7 d bake | ~1 h | 0.2 h – 11 h (15 % of draws: never) | **life at fixed bake is not a predictable quantity** |
| Required bake for 10-yr water life | ~20–25 d | ~5–7 to ~50–65 d | the *actionable* output: uncertain by ~×2.5 each way, not by orders of magnitude |

The asymmetry between the last two rows is the central point: because life is exponentially sensitive to bake time near the knee, *predicted life* at a fixed bake swings from hours to forever across plausible parameters — but the *required bake duration* for a target life only swings ×2–3, because the same exponential compresses errors in the inverse direction. Design with the second number (knee × 1.5–2 margin), never the first. Drivers, in order: venting geometry factor (ρ ≈ +0.5), diffusivity (−0.4), activation energy (−0.25), bake efficiency (−0.2), bound-water fraction (+0.15); everything about the metal surface is noise (|ρ| ≤ 0.06).

**(b) Structural error from the mechanisms this model omits** (your specific question). The omitted loads are additive and non-negative, so omission bias is **one-sided: the model is always optimistic**, by:

| Omitted mechanism | Magnitude (representative dewar) | Impact on prediction |
|---|---|---|
| CH₄/non-getterables (in package, excluded from *water-only* curves) | ~3×10⁻¹³ torr·L/s | caps any life prediction at ~10-yr class; the water-only ">30 yr" reads are ceilings, not forecasts |
| He permeation | <10⁻¹⁴ (metal-sealed) to 1.2×10⁻¹³ torr·L/s (glass window) | ≤ +4×10⁻⁵ torr per decade — negligible vs parameter band |
| Virtual leaks | 0 if vented; else p₀·V_t (1 mm³ air = 7.6× the whole budget) | design audit item, not a model term |
| Real leaks | binary | any leak ≥10⁻¹¹ torr·L/s invalidates the model entirely; screened by process, not modeled |
| Organic volatiles (CVCM) | ≲0.1× water inventory | minor for pressure; relevant for cold-optics contamination |
| H₂ decay ignored | conservative, ≤×3 the other way | partially cancels omission bias for ungettered cases |

Bottom line: for a leak-free, all-metal, vented, gettered design, the omitted-mechanism error on P(t) is ≤ ~5×10⁻¹³ torr·L/s ≈ +1.5×10⁻⁴ torr per decade — **an order of magnitude smaller than the parameter-uncertainty band**. The model's honest failure modes are (1) an undetected leak (binary invalidation) and (2) treating water-only ">30 yr" outputs as life predictions when CH₄/He own the deep-time behavior.

**(c) How to collapse the band.** One calibrated bake collapses most of it: fit `D` and the geometry factor to a measured 85 °C bake (RGA mass-18 decay curve gives the Fickian time constant directly; a warm rate-of-rise after gives the residual inventory). With those two fitted, the 68 % band on required bake tightens from ×2.5 to roughly ×1.3 — at which point the model is a quantitative tool for *your* hardware rather than a representative one.

## 5. Changes made this pass

`dewar_model/sensitivity.py` (Monte Carlo + tornado, run `python3 -m dewar_model.sensitivity`), `mc_figures.py` (band + tornado figures in `outputs/`), README updated. Core physics modules unchanged — the review found parameter ignorance, not equation errors.
