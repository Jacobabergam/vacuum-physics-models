"""Monte Carlo uncertainty quantification for the water-outgassing model.

Answers: given honest parameter ignorance AND known model-form weaknesses
(single-stage Fickian sorption, perfect pumping during bake, uniform surface
energy window), what is the spread on (a) extractable water after a bake,
(b) sealed water-only life, and (c) the required bake duration for a target
life — and which parameters drive it?

Parameter ranges (log-uniform unless noted) and their basis:
  c_sat        0.3–3 wt %       epoxy moisture saturation, literature spread
  D_295        5e-10–8e-9 cm2/s water diffusivity in epoxies at 295 K
  E_a          0.35–0.55 eV     (uniform) diffusion activation energy
  L_geom       0.5–2.5 x        venting-geometry factor on L_eff = V/A
  f_bound      0–0.4            (uniform) slow 'bound' moisture fraction with
                                D/30 — proxy for dual-stage / non-Fickian tails
                                reported for epoxy compounds
  f_bake       0.3–1            (uniform) bake efficiency — readsorption,
                                pinch-off-tube conductance starvation, thermal lag
  N_ML         1–10             surface monolayers (humidity/history)
  E_hi         1.05–1.25 eV     (uniform) top of surface binding-energy window
  nu           1e12–1e14 1/s    desorption attempt frequency
  q_H2         1e-13–3e-12      torr·L/s/cm2, baked-steel hydrogen (context only)

Run:  python3 -m dewar_model.sensitivity [N_draws]
"""
import sys
import numpy as np
from .constants import DAY, YEAR, MG_H2O_TORRL
from .outgassing import SurfaceWater, Adhesive

RNG = np.random.default_rng(20260716)

RANGES = {
    "c_sat_wtpct": ("log", 0.3, 3.0),
    "D_295":       ("log", 5e-10, 8e-9),
    "E_a":         ("lin", 0.35, 0.55),
    "L_geom":      ("log", 0.5, 2.5),
    "f_bound":     ("lin", 0.0, 0.4),
    "f_bake":      ("lin", 0.3, 1.0),
    "N_ML":        ("log", 1.0, 10.0),
    "E_hi":        ("lin", 1.05, 1.25),
    "nu":          ("log", 1e12, 1e14),
    "q_H2":        ("log", 1e-13, 3e-12),
}


def draw(n):
    out = {}
    for k, (kind, lo, hi) in RANGES.items():
        u = RNG.random(n)
        out[k] = np.exp(np.log(lo) + u * (np.log(hi / lo))) if kind == "log" \
            else lo + u * (hi - lo)
    return out


class _Case:
    """One parameter draw -> fast water-release evaluator (reduced grids)."""

    def __init__(self, cfg, p, i):
        self.V = cfg["free_volume_L"]
        self.P_crit = cfg["p_crit_torr"]
        self.f_bake = p["f_bake"][i]
        self.surface = SurfaceWater(
            area_cm2=cfg["steel_area_cm2"], monolayers=p["N_ML"][i],
            E_hi=p["E_hi"][i], nu=p["nu"][i], nE=500)
        self.adh = []
        for a in cfg["adhesives"]:
            common = dict(density_g_cm3=a.get("density_g_cm3", 1.15),
                          water_wt_pct=p["c_sat_wtpct"][i],
                          D_295K_cm2_s=p["D_295"][i], E_a_eV=p["E_a"][i])
            fast = Adhesive(a["name"], a["volume_cm3"] * (1 - p["f_bound"][i]),
                            a["exposed_area_cm2"] / p["L_geom"][i], **common)
            slow = Adhesive(a["name"] + "_bound", a["volume_cm3"] * p["f_bound"][i],
                            a["exposed_area_cm2"] / p["L_geom"][i],
                            **{**common, "D_295K_cm2_s": p["D_295"][i] / 30.0})
            self.adh += [fast, slow]

    def inventory_torrL(self, t_bake, T_bake):
        tb = t_bake * self.f_bake
        inv = self.surface.remaining_torrL(tb, T_bake)
        inv += sum(a.remaining_mg(tb, T_bake) for a in self.adh) * MG_H2O_TORRL
        return inv

    def water_life_s(self, t_bake, T_bake, T_store=295.0):
        tb = t_bake * self.f_bake
        tg = np.logspace(np.log10(600.0), np.log10(60 * YEAR), 160)
        rel = self.surface.released_after_seal_torrL(tb, T_bake, tg, T_store)
        for a in self.adh:
            rel = rel + a.released_after_seal_mg(tb, T_bake, tg, T_store) * MG_H2O_TORRL
        p = rel / self.V
        if p[-1] < self.P_crit:
            return np.inf
        return float(np.interp(self.P_crit, p, tg))

    def required_bake_days(self, T_bake, target_life_s=10 * YEAR,
                           grid=np.logspace(np.log10(1.0), np.log10(90.0), 15)):
        for b in grid:
            if self.water_life_s(b * DAY, T_bake) >= target_life_s:
                return b
        return np.inf


def run(cfg, n=800, T_bake=358.15):
    p = draw(n)
    res = {"inv7": [], "inv14": [], "life7": [], "life14": [], "req": []}
    for i in range(n):
        c = _Case(cfg, p, i)
        res["inv7"].append(c.inventory_torrL(7 * DAY, T_bake))
        res["inv14"].append(c.inventory_torrL(14 * DAY, T_bake))
        res["life7"].append(c.water_life_s(7 * DAY, T_bake))
        res["life14"].append(c.water_life_s(14 * DAY, T_bake))
        res["req"].append(c.required_bake_days(T_bake))
    res = {k: np.array(v) for k, v in res.items()}
    return p, res


def spearman(x, y):
    rx = np.argsort(np.argsort(x)).astype(float)
    ry = np.argsort(np.argsort(y)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    return float((rx * ry).sum() / np.sqrt((rx ** 2).sum() * (ry ** 2).sum()))


def pct(a, q):
    a = np.asarray(a, float)
    return np.percentile(a[np.isfinite(a)], q) if np.any(np.isfinite(a)) else np.nan


def fmt_life(s):
    if not np.isfinite(s):
        return ">60 yr"
    if s < 2 * DAY:
        return f"{s/3600:.1f} h"
    if s < 120 * DAY:
        return f"{s/DAY:.0f} d"
    return f"{s/YEAR:.1f} yr"


def main(n=800):
    sys.path.insert(0, ".")
    from .config import load_config
    import os
    base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                        "configs", "baseline_idca.yaml")
    cfg = load_config(base)
    p, res = run(cfg, n=n)

    print(f"Monte Carlo, N = {n}, bake at 85 C, storage 22 C")
    print("\nExtractable water remaining (torr·L):")
    for k, lab in [("inv7", "after 7 d"), ("inv14", "after 14 d")]:
        print(f"  {lab:11s}: median {pct(res[k],50):.2e}  "
              f"68% [{pct(res[k],16):.1e}, {pct(res[k],84):.1e}]  "
              f"95% [{pct(res[k],2.5):.1e}, {pct(res[k],97.5):.1e}]")
    print("\nSealed water-only life (no getter):")
    for k, lab in [("life7", "7 d bake"), ("life14", "14 d bake")]:
        v = res[k]
        never = np.mean(~np.isfinite(v)) * 100
        print(f"  {lab:11s}: median {fmt_life(pct(v,50))}  "
              f"68% [{fmt_life(pct(v,16))}, {fmt_life(pct(v,84))}]  "
              f"({never:.0f} % of draws never cross 1e-3 torr)")
    r = res["req"]
    print(f"\nRequired 85 C bake for 10-yr water-only life:")
    print(f"  median {pct(r,50):.1f} d   68% [{pct(r,16):.1f}, {pct(r,84):.1f}] d   "
          f"95% [{pct(r,2.5):.1f}, {pct(r,97.5):.1f}] d")
    print("\nDrivers of required bake duration (Spearman rank correlation):")
    fin = np.isfinite(r)
    rank = sorted(((k, spearman(p[k][fin], r[fin])) for k in RANGES),
                  key=lambda kv: -abs(kv[1]))
    for k, rho in rank:
        print(f"  {k:12s} {rho:+.2f}")
    return p, res, rank


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 800)
