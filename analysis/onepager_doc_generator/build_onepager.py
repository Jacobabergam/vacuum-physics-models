#!/usr/bin/env python3
"""Insert documentation cards (chart, regime bars, tables, caveats, references)
into Jake's bottleneck_pumpdown.html one-pager, matching its existing style system."""
import json

d = json.load(open("chart_data.json"))
SRC = "../../bottleneck_pumpdown.html"  # run from analysis/onepager_doc_generator/
DST = "../../bottleneck_pumpdown.html"

CSS = """
  /* DOC-CSS-START */
  /* ---------- documentation block (added 2026-07-30) ---------- */
  .viz-root {
    --doc-w:  #2a78d6; --doc-h2: #008300; --doc-ch4: #e87ba4;
    --doc-he: #eda100; --doc-crit: #d03b3b;
  }
  @media (prefers-color-scheme: dark) {
    :root:where(:not([data-theme="light"])) .viz-root {
      --doc-w: #3987e5; --doc-ch4: #d55181; --doc-he: #c98500; --doc-crit: #e66767;
    }
  }
  :root[data-theme="dark"] .viz-root {
    --doc-w: #3987e5; --doc-ch4: #d55181; --doc-he: #c98500; --doc-crit: #e66767;
  }
  .doc h3 { font-size: 13.5px; font-weight: 650; margin: 2px 0 6px; }
  .doc p { color: var(--text-2); max-width: 100ch; margin-bottom: 8px; }
  .doc p b, .doc li b { color: var(--text-1); }
  .doc .fine { font-size: 12px; color: var(--muted); }
  .legend { display: flex; flex-wrap: wrap; gap: 14px; margin: 4px 0 6px; font-size: 12.5px; color: var(--text-2); }
  .legend svg { vertical-align: -2px; margin-right: 5px; }
  .rrow { display: grid; grid-template-columns: 205px 1fr; gap: 10px; align-items: center; margin: 24px 0 10px; }
  .rrow:last-child { margin-top: 6px; }
  .rlab { font-size: 12.5px; color: var(--text-2); text-align: right; line-height: 1.25; }
  .rlab b { color: var(--text-1); }
  .rbar { position: relative; height: 26px; border-radius: 6px; overflow: visible; background: var(--band); }
  .rseg { position: absolute; top: 0; bottom: 0; }
  .rseg span { position: absolute; inset: 0; display: flex; align-items: center; justify-content: center;
               font-size: 11.5px; font-weight: 650; color: #fff; white-space: nowrap; overflow: hidden; }
  .rband { position: absolute; top: -3px; bottom: -3px; border-left: 2px dashed var(--doc-crit);
           border-right: 2px dashed var(--doc-crit); background: transparent; }
  .rmark { position: absolute; top: -5px; bottom: -5px; width: 0; border-left: 2px solid var(--doc-crit); }
  .rnote { position: absolute; top: -20px; transform: translateX(-50%); font-size: 11px;
           color: var(--doc-crit); font-weight: 650; white-space: nowrap; }
  .raxis { position: relative; height: 18px; margin-top: 2px; }
  .raxis span { position: absolute; transform: translateX(-50%); font-size: 11px; color: var(--muted); white-space: nowrap; }
  .raxis span:first-child { transform: none; }
  .raxis span:last-child { transform: translateX(-100%); }
  .doctab { width: 100%; border-collapse: collapse; font-size: 12.5px; margin-top: 6px; }
  .doctab th { text-align: left; color: var(--text-2); font-weight: 650; border-bottom: 1px solid var(--baseline);
               padding: 5px 8px 5px 0; }
  .doctab td { color: var(--text-2); border-bottom: 1px solid var(--grid); padding: 6px 8px 6px 0; vertical-align: top; }
  .doctab td:first-child { color: var(--text-1); font-weight: 600; white-space: nowrap; }
  .refs { columns: 2; column-gap: 26px; font-size: 12.5px; color: var(--text-2); padding-left: 18px; }
  @media (max-width: 900px) { .refs { columns: 1; } }
  .refs li { margin-bottom: 7px; break-inside: avoid; }
  .refs a { color: var(--series-1); text-decoration: none; }
  .refs a:hover { text-decoration: underline; }
  .tag { font-size: 10.5px; font-weight: 650; border: 1px solid var(--border); border-radius: 4px;
         padding: 0 5px; color: var(--muted); white-space: nowrap; }
  .docchart svg { display: block; width: 100%; height: auto; }
  .docchart .gl { stroke: var(--grid); stroke-width: 1; }
  .docchart .ax { stroke: var(--baseline); stroke-width: 1.2; }
  .docchart text { font: 11px system-ui, -apple-system, "Segoe UI", sans-serif; fill: var(--muted); }
  .docchart .anno { fill: var(--text-2); font-size: 11.5px; }
  .docchart .annoc { fill: var(--doc-crit); font-weight: 650; font-size: 11.5px; }
  /* DOC-CSS-END */
"""


def seg(l, r, color, label=""):
    lab = f'<span>{label}</span>' if label else ""
    return (f'<div class="rseg" style="left:{l}%;width:{max(r - l, 0):.2f}%;'
            f'background:var(--doc-{color})">{lab}</div>')


p = d["pct"]
axis = "".join(f'<span style="left:{pos}%">{lab}</span>' for pos, lab in p["ticks"])

# ---------------- SVG chart ----------------
grid_x = "".join(f'<line class="gl" x1="{x}" y1="18" x2="{x}" y2="330"/>' for x, _ in d["xticks"])
grid_y = "".join(f'<line class="gl" x1="52" y1="{y}" x2="610" y2="{y}"/>' for y, _ in d["yticks"])
tick_x = "".join(f'<text x="{x}" y="346" text-anchor="middle">{lab}</text>' for x, lab in d["xticks"])
tick_y = "".join(f'<text x="46" y="{y + 4}" text-anchor="end">10<tspan baseline-shift="super" font-size="8">{e}</tspan></text>'
                 for y, e in d["yticks"])

SVG = f"""
<svg viewBox="0 0 760 360" role="img" aria-label="Gas load per mechanism versus time after pinch-off, one hour to thirty years">
  {grid_x}{grid_y}
  <line class="ax" x1="52" y1="330" x2="610" y2="330"/><line class="ax" x1="52" y1="18" x2="52" y2="330"/>
  {tick_x}{tick_y}
  <text x="20" y="174" transform="rotate(-90 20 174)" text-anchor="middle">gas load into sealed volume  (Torr·L/s, log)</text>
  <polygon points="{d['h2band']}" fill="var(--doc-h2)" opacity="0.14"/>
  <polyline points="{d['h2hi']}" fill="none" stroke="var(--doc-h2)" stroke-width="2"/>
  <polyline points="{d['h2lo']}" fill="none" stroke="var(--doc-h2)" stroke-width="1.2"/>
  <polyline points="{d['ch4']}" fill="none" stroke="var(--doc-ch4)" stroke-width="2"/>
  <polyline points="{d['he']}" fill="none" stroke="var(--doc-he)" stroke-width="2" stroke-dasharray="7 4"/>
  <polyline points="{d['allow']}" fill="none" stroke="var(--doc-crit)" stroke-width="1.8" stroke-dasharray="5 4"/>
  <polyline points="{d['w3']}" fill="none" stroke="var(--doc-w)" stroke-width="2.2"/>
  <polyline points="{d['w14']}" fill="none" stroke="var(--doc-w)" stroke-width="2.2" stroke-dasharray="6 4"/>
  <text class="anno" x="70" y="52">water, 85 °C × 3 d bake (under-baked)</text>
  <text class="anno" x="70" y="150">water, 85 °C × 14 d (well-baked, dashed)</text>
  <text class="anno" x="490" y="{d['ylab_h2'] - 8}">H₂ from steel (band)</text>
  <text class="annoc" x="70" y="{d['ylab_allow'] - 15}">10-yr no-getter allowance P·V/t — note CH₄ sits right ON it</text>
  <text class="anno" x="614" y="{d['ylab_he'] + 12}">He (glass-window case)</text>
  <text class="anno" x="614" y="{d['ylab_ch4'] - 2}">CH₄</text>
</svg>"""

LEGEND = """
<div class="legend">
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-w)" stroke-width="2.5"/></svg>water, under-baked (3 d)</span>
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-w)" stroke-width="2.5" stroke-dasharray="5 3"/></svg>water, well-baked (14 d)</span>
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-h2)" stroke-width="2.5"/></svg>H₂, steel bulk</span>
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-ch4)" stroke-width="2.5"/></svg>CH₄ (non-getterable)</span>
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-he)" stroke-width="2.5" stroke-dasharray="5 3"/></svg>He (only if glass)</span>
  <span><svg width="22" height="10"><line x1="0" y1="5" x2="22" y2="5" stroke="var(--doc-crit)" stroke-width="2.5" stroke-dasharray="4 3"/></svg>10-yr no-getter allowance</span>
</div>"""

BARS = f"""
<div class="rrow"><div class="rlab"><b>Under-baked</b> (85 °C × 3 d)<br>no getter</div>
  <div class="rbar">{seg(0, p['t_wx'], 'w', 'water dominates')}{seg(p['t_wx'], 100, 'h2', 'H₂')}
    <div class="rmark" style="left:1.2%"><div class="rnote" style="left:0;transform:none">EOL ≈ 30 min</div></div>
  </div></div>
<div class="rrow"><div class="rlab"><b>Well-baked</b> (85 °C × 14 d)<br>no getter</div>
  <div class="rbar">{seg(0, 100, 'h2', 'H₂ dominates from day one')}
    <div class="rband" style="left:{p['eol14_lo']}%;width:{p['eol14_hi'] - p['eol14_lo']:.2f}%"></div>
    <div class="rnote" style="left:{(p['eol14_lo'] + p['eol14_hi']) / 2:.1f}%">EOL 1–39 d (q<sub>H₂</sub> band)</div>
  </div></div>
<div class="rrow"><div class="rlab"><b>Any decent bake</b><br>healthy activated getter</div>
  <div class="rbar">{seg(0, 100, 'ch4', 'CH₄ (+ He if glass) — water & H₂ absorbed by getter')}
    <div class="rband" style="left:{p['eolg_lo']}%;width:{min(p['eolg_hi'], 100) - p['eolg_lo']:.2f}%"></div>
    <div class="rnote" style="left:{p['eolg']:.1f}%;transform:translateX(-85%)">EOL ≈ 10 yr (3.5–35)</div>
  </div></div>
<div class="rrow"><div class="rlab"></div><div class="raxis">{axis}</div></div>"""

DOC = f"""
  <!-- DOC-BLOCK-START -->
  <!-- ================= documentation block (added 2026-07-30, generated from dewar_vacuum_model v0.2) ================= -->
  <div class="card explain doc">
    <h2>Vacuum-loss documentation — who owns the gas load, and when</h2>
    <p>The sealed-dewar gas budget is brutally small: staying below the ~10⁻³ Torr soft-vacuum threshold in a
    0.1 L volume is a total budget of <b>P·V ≈ 10⁻⁴ Torr·L ≈ 0.1 µg of water</b>, while one milligram of
    absorbed water is ≈ 1 Torr·L and outgassing is ~90 % of the gas load in a typical high-vacuum system
    (Grinham &amp; Chew 2017, ref. 3). Which species owns that budget changes by orders of magnitude over
    life — the chart and bars below are computed from the companion model in
    <code>dewar_vacuum_model/</code> (300 cm² steel, 0.1 L, 85 °C bakes; REVIEW.md has the error budget).</p>
    <div class="docchart">{SVG}</div>
    {LEGEND}
    <p class="fine">Sharp knees are model-sharp (single-stage Fickian); the Monte Carlo band on these curves is
    roughly ×2.5 each way on required bake duration — see REVIEW.md. Real leaks are excluded: if one exists it
    dominates everything (the 10-yr no-getter allowance, 3×10⁻¹³ Torr·L/s ≈ 4×10⁻¹³ atm·cc/s, is below
    standard He leak-test sensitivity — hermeticity is a process-control result, not a test result).</p>

    <div class="sect">
      <h3>Time regimes of domination, 1 hour → 30 years</h3>
      {BARS}
      <table class="doctab">
        <tr><th>Time window</th><th>Dominant load</th><th>Scaling law</th><th>Basis</th></tr>
        <tr><td>first hours–days</td><td>surface water (metal walls)</td><td>q ∝ 1/t (Elovich / multi-energy desorption)</td>
            <td>refs 1, 2, 4, 5 — gone within hours at 85 °C</td></tr>
        <tr><td>days–months</td><td>adhesive / polymer water</td><td>q ∝ 1/√t, then exp(−π²Dt/4L²); L = volume/vent area</td>
            <td>refs 2, 6, 7 — sets required bake time; dual-stage tails make Fickian optimistic</td></tr>
        <tr><td>weeks–years (no getter)</td><td>H₂ from steel bulk</td><td>≈ constant (slow √t decay), 10⁻¹³–3×10⁻¹² Torr·L/s/cm²</td>
            <td>refs 1, 2, 8 — alone reaches 10⁻³ Torr in 1–39 d in 0.1 L → getters are mandatory</td></tr>
        <tr><td>years–decades (gettered)</td><td>CH₄ (+ He through any glass)</td><td>linear accumulation; CH₄ ~10⁻¹⁵ Torr·L/s/cm² (rough)</td>
            <td>refs 2, 9, 10, 11 — sets the ~10-yr-class ceiling of a well-built dewar</td></tr>
        <tr><td>any time</td><td>real leak (weld/braze/pinch-off)</td><td>constant; binary — absent or dominant</td>
            <td>screen by process + He accumulation test (ref 2: accumulation reaches ~10⁻¹⁸ mbar·L/s for nobles)</td></tr>
      </table>
    </div>

    <div class="sect">
      <h3>The caveat: water stops being the problem — CH₄ and He inherit it</h3>
      <p><b>With a healthy activated getter</b>, water and hydrogen are absorbed after seal-off, so they stop
      being <i>pressure</i> problems at all — leftover water instead spends getter capacity and, during cold
      operation, cryopumps onto the coldest optic (water ice absorbs strongly at 3.16 / 4.6 / 6.1 / 13 µm;
      ~0.1 µm on a cold filter is already measurable, ref 12). The long-term pressure rise is then owned by
      what the getter cannot pump: <b>methane from the steel and helium through any glass</b>. Our
      representative CH₄ rate lands almost exactly on the 10-year no-getter allowance — which is the deep
      reason well-built gettered dewars are a "10-year-class" product — but that rate is uncertain by about
      a decade (hence EOL 3.5–35 yr in the bars). Helium only matters through glass windows or frits
      (~4×10⁻⁵ Torr per decade for a 4 cm², 1 mm borosilicate window at the atmosphere's 5.2 ppm He);
      metal-brazed Ge/Si/sapphire windows make it negligible (refs 9, 13). <b>Without a getter</b>, the story
      never gets that far: after any competent bake, H₂ owns the budget within days — water only re-enters the
      picture if the bake was cut short of the knee. Practical consequence: <i>bake quality is measured in
      getter-capacity margin and ice budget, while end-of-life is measured in CH₄/He accumulation</i> — two
      different currencies, verified by different tests (rate-of-rise + RGA composition vs. long-interval
      storage trending).</p>
    </div>

    <div class="sect">
      <h3>Water desorption from the metal surfaces — reviewed</h3>
      <p>Every air-exposed metal surface carries a few monolayers of water (1 monolayer = 10¹⁵ molecules/cm²
      ≈ 3.1×10⁻⁵ Torr·L/cm²; 3 monolayers on 300 cm² ≈ 0.027 Torr·L). Unbaked, it leaves following the
      famous inverse-time law <b>q ≈ 3×10⁻⁹/t(h) mbar·L·s⁻¹·cm⁻²</b> (refs 1, 2) — the rate depends on how
      long you have pumped, not on the material being "done". The physical origin is first-order desorption
      over a broad distribution of binding energies (~0.75–1.15 eV, attempt frequency ν ≈ 10¹³ s⁻¹): the
      superposition of exponentials over that distribution <i>is</i> the 1/t law (Redhead 1995, Li &amp; Dylla
      1993 — refs 4, 5; our implementation reproduces the empirical coefficient within ×1.5 with no fitting).
      Baking advances an "erosion front" <b>E* = k_B·T·ln(ν·t)</b>: each decade of time buys only 2.3 k_B·T
      (~0.07 eV at 85 °C) while temperature multiplies the whole front — bake hotter beats bake longer.
      Worked equivalences: 85 °C × 1 day out-anneals 10 years of 22 °C storage; 60 °C needs ~13 days for the
      same front; covering six months of 71 °C storage soak takes ~30 days at 85 °C but only ~5 at 100 °C.</p>
      <p class="fine">Two honest footnotes. First, measured "unbaked metal" rates scatter ~100× across sources
      (compare ref 3's fresh-stainless table against ref 1's 1-h value) — history and measurement method, not
      physics; and throughput measurements over-read water by ~3× from readsorption (ref 3). Second, our Monte
      Carlo says that <i>after</i> any competent bake the surface-water parameters barely move the answers
      (|rank correlation| ≤ 0.06 on required bake time) — the precision belongs on the adhesives. Where surface
      water does matter is pump-down behavior and RGA interpretation: this page's simulator shows the
      manifold-vs-chamber H₂O attenuation (~S/C) that makes the gauge read optimistic during exactly that phase.</p>
    </div>

    <div class="sect">
      <h3>References</h3>
      <ol class="refs">
        <li>P. Chiggiato, <i>Outgassing</i>, CERN Accelerator School lecture notes (2017) — 1/t water law, H₂ rates vs bake, polymer water content. <a href="https://cas.web.cern.ch/sites/default/files/lectures/glumslov-2017/chiggiato.pdf">PDF</a> <span class="tag">read</span></li>
        <li>P. Chiggiato, "Outgassing properties of vacuum materials for particle accelerators," CERN Yellow Rep. (2020) — equations for desorption, diffusion, permeation; accumulation-method sensitivity. <a href="https://arxiv.org/abs/2006.07124">arXiv:2006.07124</a> <span class="tag">read</span></li>
        <li>R. Grinham &amp; A. Chew, "A Review of Outgassing and Methods for its Reduction," <i>Appl. Sci. Converg. Technol.</i> 26(5), 95 (2017) — source taxonomy, rate tables, measurement-method comparison. <a href="https://www.e-asct.org/journal/view.html?volume=26&amp;number=5&amp;spage=95&amp;vmd=Full">open access</a> <span class="tag">read</span></li>
        <li>P. A. Redhead, "Modeling the pump-down of a reversibly adsorbed phase," <i>J. Vac. Sci. Technol. A</i> 13, 467 (1995); and "Recommended practices for measuring and reporting outgassing data," <i>JVST A</i> 20, 1667 (2002). <span class="tag">citation verified</span></li>
        <li>M. Li &amp; H. F. Dylla, "Model for the outgassing of water from metal surfaces," <i>JVST A</i> 11, 1702 (1993). <span class="tag">citation verified</span></li>
        <li>Fan et al., "Effect of temperature and humidity on moisture diffusion in an epoxy moulding compound," <i>Microelectron. Reliab.</i> (2019). <a href="https://www.sciencedirect.com/science/article/pii/S0026271419311771">link</a> <span class="tag">dual-stage evidence</span></li>
        <li>"Characterization of dual-stage moisture diffusion … of epoxy molding compounds," IEEE ECTC (2008). <a href="https://ieeexplore.ieee.org/document/4525009/">link</a> <span class="tag">dual-stage evidence</span></li>
        <li>"Hydrogen outgassing and permeation in stainless steel and its reduction for UHV applications" (review), <i>Mater. Today Proc.</i> <a href="https://www.sciencedirect.com/science/article/abs/pii/S2214785320385795">link</a></li>
        <li>W. G. Perkins, "Permeation and Outgassing of Vacuum Materials," <i>J. Vac. Sci. Technol.</i> 10, 543 (1973) — permeation data incl. He/glass. <a href="https://pubs.aip.org/avs/jvst/article/10/4/543/248393">link</a> <span class="tag">citation verified</span></li>
        <li>Sandia National Labs, SAES St 707 getter hydrogen capacity &amp; activation data. <a href="https://psec.uchicago.edu/getters/sandia_ST707_getter_data_105402.pdf">PDF</a> <span class="tag">read</span></li>
        <li>UChicago PSEC getter notes — St 707 H₂O capacity and pumping-speed estimates. <a href="https://psec.uchicago.edu/getters/H2O_monolayer_v2.pdf">PDF</a> <span class="tag">read</span></li>
        <li>AFRL/AEDC, "The Infrared Spectral Signature of Water Ice…" DTIC ADA443824 — ice band positions and thickness effects. <a href="https://apps.dtic.mil/sti/pdfs/ADA443824.pdf">PDF</a> <span class="tag">read</span></li>
        <li>DSPE thermomechanics knowledge base — free-molecular heat-transfer formula (Corruccini form; original: R. J. Corruccini, <i>Vacuum</i> 7–8, 19 (1959)). <a href="https://www.dspe.nl/knowledge/thermomechanics/chapter-2-in-depth/conduction-in-gasses/regime-1-free-molecular-heat-transfer/">link</a></li>
        <li>Dewar-specific reliability: "Accelerated test and life prediction of integrated Dewar for infrared detector" (<a href="https://ieeexplore.ieee.org/document/7107176/">IEEE 7107176</a>); Lai &amp; Yang, "Failure analysis of integrated detector dewar cryocooler assembly" (<a href="https://ieeexplore.ieee.org/document/6625721/">IEEE 6625721</a>); "Five year operation of a cooler Dewar assembly … GCOM-C," <i>Cryogenics</i> (2024) (<a href="https://www.sciencedirect.com/science/article/abs/pii/S0011227524000432">link</a>). <span class="tag">metadata verified</span></li>
        <li>NASA outgassing database (ASTM E595 TML/CVCM screening data, 10 000+ materials). <a href="https://outgassing.nasa.gov">outgassing.nasa.gov</a></li>
        <li>J. F. O'Hanlon, <i>A User's Guide to Vacuum Technology</i>, 3rd ed., Wiley (2003) — conductance formulas used by this page's simulator. <span class="tag">textbook</span></li>
      </ol>
      <p class="fine">Tags: <b>read</b> = source fetched and used directly in this project's sessions; <b>citation verified</b> = canonical
      reference cross-checked via the read sources (full text paywalled); <b>metadata verified</b> = bibliographic record confirmed,
      full text not retrieved. Representative magnitudes above are design-dependent — regenerate for your geometry with
      <code>dewar_vacuum_model/run_model.py</code>; uncertainty analysis in <code>REVIEW.md</code>.</p>
    </div>
  </div>
  <!-- DOC-BLOCK-END -->
"""

html = open(SRC).read()
if "DOC-BLOCK-START" in html:
    import re
    html = re.sub(r"\n  <!-- DOC-BLOCK-START -->.*?<!-- DOC-BLOCK-END -->\n*", "", html, flags=re.S)
    html = re.sub(r"\n  /\* DOC-CSS-START \*/.*?/\* DOC-CSS-END \*/\n*", "", html, flags=re.S)
elif "documentation block" in html:
    raise SystemExit("Page contains a pre-sentinel documentation block (2026-07-30 vintage). "
                     "Delete it manually once (from '<!-- ====== documentation block' through the "
                     "card's closing </div>, plus the doc CSS in <style>), then re-run — future "
                     "runs will be idempotent via sentinels.")
html = html.replace("</style>", CSS + "</style>", 1)
# insert DOC after the explain card (2nd </div> after its final line), before wrap close
key = "adaptive log-time grid.</div>"
i0 = html.find(key)
assert i0 > 0, "explain-card anchor text not found"
i1 = html.find("</div>", i0 + len(key))   # explain card close
i2 = html.find("</div>", i1 + 6)          # .wrap close
assert i2 > i1 > 0
html = html[:i2] + DOC + "\n" + html[i2:]
open(DST, "w").write(html)
print("written", DST, len(html), "bytes")
