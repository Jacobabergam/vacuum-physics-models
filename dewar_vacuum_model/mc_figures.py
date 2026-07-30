#!/usr/bin/env python3
"""Monte Carlo uncertainty figures: life-vs-bake percentile band + tornado."""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from dewar_model.config import load_config
from dewar_model.constants import DAY, YEAR
from dewar_model.outgassing import OutgassingModel
from dewar_model.sealed_life import SealedDewar
from dewar_model.sensitivity import draw, _Case, RANGES, spearman

SURF, INK, INK2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
BLUE, BLUE_L, CRIT, GOODG = '#2a78d6', '#9ec5f4', '#d03b3b', '#008300'
mpl.rcParams.update({
    'font.family': 'sans-serif', 'font.size': 10.5,
    'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.titlepad': 12})

cfg = load_config("configs/baseline_idca.yaml")
N = 400
p = draw(N)
bgrid = np.logspace(np.log10(1.0), np.log10(90.0), 15)
CAP = 60 * YEAR

lives = np.zeros((N, len(bgrid)))
req = np.zeros(N)
for i in range(N):
    c = _Case(cfg, p, i)
    lv = np.array([c.water_life_s(b * DAY, 358.15) for b in bgrid])
    lives[i] = np.minimum(np.nan_to_num(lv, posinf=CAP), CAP)
    fin = lv >= 10 * YEAR
    req[i] = bgrid[np.argmax(fin)] if fin.any() else np.inf

# nominal
og = OutgassingModel(cfg)
sd = SealedDewar(cfg, og)
nom = np.array([min(sd.life_to_crit_s(b * DAY, 358.15, "water"), CAP) for b in bgrid])

# ---------------- Figure A: band ----------------
fig, ax = plt.subplots(figsize=(8.6, 5.2), constrained_layout=True)
p16, p50, p84 = [np.percentile(lives, q, axis=0) for q in (16, 50, 84)]
p025, p975 = [np.percentile(lives, q, axis=0) for q in (2.5, 97.5)]
ax.fill_between(bgrid, p025 / DAY, p975 / DAY, color=BLUE_L, alpha=0.45, lw=0,
                label='95 % of parameter draws')
ax.fill_between(bgrid, p16 / DAY, p84 / DAY, color=BLUE, alpha=0.35, lw=0,
                label='68 % of parameter draws')
ax.plot(bgrid, p50 / DAY, color=BLUE, lw=2, label='median')
ax.plot(bgrid, nom / DAY, color=INK, lw=1.8, ls=(0, (5, 3)), label='nominal config')
ax.axhline(10 * 365, color=GOODG, lw=1.5, ls=(0, (2, 3)))
ax.text(1.05, 10 * 365 * 1.5, '10-yr target', color=GOODG, fontsize=9)
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_yticks([1 / 24, 1, 7, 30, 182, 365, 3652, 21915],
              ['1 h', '1 d', '1 wk', '1 mo', '6 mo', '1 yr', '10 yr', '60 yr'])
ax.set_xticks([1, 2, 3, 5, 7, 10, 14, 21, 30, 45, 60, 90],
              ['1', '2', '3', '5', '7', '10', '14', '21', '30', '45', '60', '90'])
ax.minorticks_off()
ax.set_xlim(1, 90); ax.set_ylim(1 / 24, CAP / DAY)
ax.set_xlabel('bake duration at 85 °C  (days)')
ax.set_ylabel('sealed water-only life to 10$^{-3}$ torr')
fin = np.isfinite(req)
ax.set_title('Uncertainty band on the life-vs-bake curve (Monte Carlo, N = 400)\n'
             f'required bake for 10-yr: median {np.median(req[fin]):.0f} d, '
             f'68 % [{np.percentile(req[fin],16):.0f}, {np.percentile(req[fin],84):.0f}] d')
ax.legend(loc='lower right', frameon=False, labelcolor=INK2, fontsize=9)
fig.savefig('outputs/mc_life_band.png', dpi=200)
plt.close(fig)

# ---------------- Figure B: tornado ----------------
labels = {
    "L_geom": "venting geometry factor (L_eff = V/A × g)",
    "D_295": "water diffusivity D(295 K)",
    "f_bake": "bake efficiency (readsorption/conductance)",
    "E_a": "diffusion activation energy",
    "f_bound": "bound-water fraction (dual-stage tail)",
    "E_hi": "surface binding-energy window top",
    "c_sat_wtpct": "epoxy water saturation (wt %)",
    "nu": "desorption attempt frequency",
    "q_H2": "H2 rate (context)",
    "N_ML": "surface monolayers",
}
rank = sorted(((k, spearman(p[k][fin], req[fin])) for k in RANGES),
              key=lambda kv: abs(kv[1]))
fig, ax = plt.subplots(figsize=(8.6, 5.0), constrained_layout=True)
ys = np.arange(len(rank))
vals = [rho for _, rho in rank]
cols = [BLUE if v > 0 else '#1c5cab' for v in vals]
ax.barh(ys, vals, color=cols, height=0.62)
for y, (k, rho) in zip(ys, rank):
    s = 1 if rho >= 0 else -1
    ax.text(-0.03 * s, y, labels[k], va='center',
            ha='right' if s > 0 else 'left', fontsize=9.3, color=INK2)
    ax.text(rho + 0.025 * s, y, f'{rho:+.2f}', va='center',
            ha='left' if s > 0 else 'right', fontsize=9, color=INK)
ax.axvline(0, color=AXIS, lw=1)
ax.set_yticks([])
ax.set_xlim(-0.75, 0.75)
ax.set_xlabel('Spearman rank correlation with required bake duration')
ax.set_title('What actually drives the answer: sensitivity tornado\n'
             '(positive → parameter increase lengthens required bake)')
fig.savefig('outputs/mc_tornado.png', dpi=200)
plt.close(fig)
print('figures written; finite-req fraction:', fin.mean())
