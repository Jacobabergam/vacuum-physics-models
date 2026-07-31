#!/usr/bin/env python3
"""Synthesis figure: instantaneous gas load per mechanism vs time since pinch-off,
representative sealed dewar (300 cm2 steel, 0.1 L). Uses the dewar_model package."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dewar_vacuum_model"))
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from dewar_model.config import load_config
from dewar_model.outgassing import OutgassingModel
from dewar_model.constants import DAY, YEAR

SURF, INK, INK2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
CAT = ['#2a78d6', '#008300', '#e87ba4', '#eda100', '#1baf7a', '#eb6834']
CRIT = '#d03b3b'

mpl.rcParams.update({
    'font.family': 'sans-serif', 'font.size': 10.5,
    'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.titlepad': 12})

cfg = load_config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "dewar_vacuum_model", "configs", "baseline_idca.yaml"))
og = OutgassingModel(cfg)

t = np.logspace(np.log10(0.02 * DAY), np.log10(30 * YEAR), 400)

def water_rate(bake_days, T_bake=358.15):
    rel = og.water_released_after_seal_torrL(bake_days * DAY, T_bake, t, 295.0)
    return np.gradient(rel, t)

q_w_short = water_rate(3)          # under-baked: 85 C x 3 d
q_w_good = water_rate(14)          # well-baked: 85 C x 14 d
q_h2_hi = 1e-12 * 300 * np.ones_like(t)
q_h2_lo = 1e-13 * 300 * np.ones_like(t)
q_ch4 = 1e-15 * 300 * np.ones_like(t)
q_he_glass = 1.2e-13 * np.ones_like(t)   # borosilicate window 4 cm2 x 1 mm (estimate)
q_leak_allow = cfg["p_crit_torr"] * cfg["free_volume_L"] / (10 * YEAR)

fig, ax = plt.subplots(figsize=(8.8, 5.4), constrained_layout=True)
ax.plot(t / DAY, np.maximum(q_w_short, 1e-30), color=CAT[0], lw=2,
        label='water — under-baked (85 °C × 3 d)')
ax.plot(t / DAY, np.maximum(q_w_good, 1e-30), color=CAT[0], lw=2, ls=(0, (5, 3)),
        label='water — well-baked (85 °C × 14 d)')
ax.fill_between(t / DAY, q_h2_lo, q_h2_hi, color=CAT[1], alpha=0.18, lw=0)
ax.plot(t / DAY, q_h2_hi, color=CAT[1], lw=2, label='H$_2$ from steel bulk (band)')
ax.plot(t / DAY, q_h2_lo, color=CAT[1], lw=1.2)
ax.plot(t / DAY, q_ch4, color=CAT[2], lw=2, label='CH$_4$ (non-getterable)')
ax.plot(t / DAY, q_he_glass, color=CAT[3], lw=2,
        label='He permeation, glass window case')
ax.axhline(q_leak_allow, color=CRIT, lw=1.8, ls=(0, (5, 4)))
ax.text(0.025, q_leak_allow * 1.8,
        'allowable TOTAL for 10-yr life, no getter:  P·V/t = 3×10$^{-13}$ torr·L/s',
        color=CRIT, fontsize=9)

# direct labels
ax.annotate('water, 3 d bake', (0.4, 8.5e-8), color=CAT[0], fontsize=9.5, fontweight='bold')
ax.annotate('water, 14 d bake', (0.4, 2.6e-12), color=CAT[0], fontsize=9.5, fontweight='bold')
ax.annotate('H$_2$', (1.1e3, 4.2e-10), color=CAT[1], fontsize=10, fontweight='bold')
ax.annotate('CH$_4$  (sits right AT the no-getter allowance)', (28, 5.6e-13),
            color=CAT[2], fontsize=9.5, fontweight='bold')
ax.annotate('He (glass window)', (1.1e3, 5.2e-14), color=CAT[3], fontsize=9.5, fontweight='bold')
ax.text(0.025, 2.5e-16, 'with getter: water, H$_2$, CO pumped after seal-off — '
        'CH$_4$, He, and Ar from any air leak remain', color=INK2, fontsize=9)

ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xticks([0.05, 1, 7, 30, 182, 365, 3652, 10957],
              ['1 h', '1 d', '1 wk', '1 mo', '6 mo', '1 yr', '10 yr', '30 yr'])
ax.minorticks_off()
ax.set_xlim(0.02, 11000); ax.set_ylim(1e-16, 3e-5)
ax.set_xlabel('time after pinch-off  (22 °C storage)')
ax.set_ylabel('instantaneous gas load into sealed volume  (torr·L·s$^{-1}$)')
ax.set_title('Ranked sources of vacuum degradation vs time — representative sealed dewar\n'
             '(300 cm² steel, 0.1 L; leaks excluded — if present they dominate)')
ax.legend(loc='upper right', frameon=False, labelcolor=INK2, fontsize=9)
fig.savefig('fig_sources_vs_time.png', dpi=200)
print('written fig_sources_vs_time.png')

# supporting numbers for the doc
for name, arr in [('water 3d @1wk', water_rate(3)[np.argmin(abs(t-7*DAY))]),
                  ('water 3d @1mo', water_rate(3)[np.argmin(abs(t-30*DAY))]),
                  ('water 14d @1wk', water_rate(14)[np.argmin(abs(t-7*DAY))])]:
    print(f"{name}: {arr:.2e} torr L/s")
print(f"leak allowance (no getter, 10yr): {q_leak_allow:.2e} torr L/s = "
      f"{q_leak_allow/0.76:.2e} atm cc/s")
cap = cfg['getter']['capacity_torrL']
print(f"air-leak allowance with getter, capacity {cap} torr·L / 10 yr: "
      f"{cap/(10*YEAR):.2e} torr L/s = {cap/(10*YEAR)/0.76:.2e} atm cc/s")
print(f"argon-accumulation limit on air leak (0.93% Ar): "
      f"{cfg['p_crit_torr']*cfg['free_volume_L']/0.0093/(10*YEAR):.2e} torr L/s air")
