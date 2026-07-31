#!/usr/bin/env python3
"""Figures for the dewar bakeout reference. Palette per dataviz reference instance (light mode)."""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from model import (gas_load_W, GASES, surf_remaining_frac, poly_remaining_mg,
                   sealed_pressure, water_life, I_SURF0, MG_TO_TORRL, V_FREE,
                   Q_H2, Q_CH4, P_CRIT, A_int)

DAY, YR = 86400.0, 3.156e7
# ---- palette (validated reference instance, light mode) ----
SURF   = '#fcfcfb'
INK    = '#0b0b0b'; INK2 = '#52514e'; MUTED = '#898781'
GRID   = '#e1e0d9'; AXIS = '#c3c2b7'
CAT    = ['#2a78d6', '#008300', '#e87ba4', '#eda100']          # categorical slots 1-4
ORD4   = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']          # ordinal blue ramp 250/400/550/700
CRIT   = '#d03b3b'; SERIOUS = '#ec835a'; GOOD = '#0ca30c'

mpl.rcParams.update({
    'font.family': 'sans-serif', 'font.size': 10.5,
    'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
    'xtick.color': MUTED, 'ytick.color': MUTED,
    'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8,
    'axes.spines.top': False, 'axes.spines.right': False,
    'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
    'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.titlepad': 12,
})

def style(ax):
    ax.grid(True, which='major', color=GRID, lw=0.8)
    ax.grid(True, which='minor', color=GRID, lw=0.4, alpha=0.5)
    ax.set_axisbelow(True)

def endlabel(ax, x, y, s, color, dx=1.12, va='center', ha='left', fs=9.5):
    ax.annotate(s, (x, y), xytext=(x*dx, y), color=color, fontsize=fs,
                fontweight='bold', va=va, ha=ha, annotation_clip=False)

# ============================================================ FIGURE 1
# Gas-conduction heat load vs internal pressure
fig, ax = plt.subplots(figsize=(8.2, 5.0), constrained_layout=True)
P = np.logspace(-7, 1, 400)
names = {'air/N2': 'air / N$_2$', 'H2': 'H$_2$', 'He': 'He'}
for i, g in enumerate(['air/N2', 'H2', 'He']):
    Q = gas_load_W(P, g) * 1e3
    ax.plot(P, Q, color=CAT[i], lw=2, label=names[g])
ax.text(3.5, 2.75e4, 'H$_2$', color=CAT[1], fontsize=10, fontweight='bold')
ax.text(3.5, 8.2e3, 'He', color=CAT[2], fontsize=10, fontweight='bold')
ax.text(3.5, 1.55e3, 'air / N$_2$', color=CAT[0], fontsize=10, fontweight='bold')
ax.axhline(40, color=MUTED, lw=1.4, ls=(0, (5, 4)))
ax.text(1.6e-7, 48, 'typical radiative + lead conduction baseline (~40 mW)',
        color=INK2, fontsize=9)
ax.axvline(1e-4, color=MUTED, lw=1.4, ls=(0, (2, 3)))
ax.text(8.3e-5, 1.1e3, 'design allocation:\n~10 mW at 10$^{-4}$ torr', color=INK2, fontsize=9, ha='right')
ax.axvline(1e-3, color=CRIT, lw=1.6, ls=(0, (5, 4)))
ax.text(1.2e-3, 1.2e-2, 'soft-vacuum failure:\n>100 mW at 10$^{-3}$ torr', color=CRIT, fontsize=9)
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlim(1e-7, 10); ax.set_ylim(3e-3, 4.5e4)
ax.set_xlabel('internal pressure  (torr, warm)  —  1 torr = 133 Pa')
ax.set_ylabel('gas-conduction heat load on 80 K stage  (mW)')
ax.set_title('Why the vacuum level matters: gas conduction 293 K shell → 80 K cold shield')
ax.text(3e-6, 6e3, 'free-molecular regime:  Q ∝ P', color=INK2, fontsize=9.5, rotation=0)
ax.text(0.45, 3.6e3, 'continuum\n(Q independent of P)', color=INK2, fontsize=9.5, ha='center')
ax.text(2.2e-6, 4.6e-3, 'A$_{cold}$ = 40 cm²,  gap = 5 mm,  ΔT = 213 K,  α: air 0.9, H$_2$ 0.4, He 0.31   (representative)',
        color=MUTED, fontsize=8.5)
ax.legend(loc='upper left', frameon=False, labelcolor=INK2)
fig.savefig('fig1_gas_conduction.png', dpi=200)
plt.close(fig)

# ============================================================ FIGURE 2
# Extractable water inventory vs bake duration, four temperatures
fig, ax = plt.subplots(figsize=(8.2, 5.0), constrained_layout=True)
tb = np.logspace(np.log10(0.05), np.log10(60), 300) * DAY
temps = [60, 85, 100, 125]
for i, TC in enumerate(temps):
    T = TC + 273.15
    inv = np.array([surf_remaining_frac(t, T) * I_SURF0 +
                    poly_remaining_mg(t, T) * MG_TO_TORRL for t in tb])
    ax.plot(tb / DAY, inv, color=ORD4[i], lw=2, label=f'{TC} °C bake')
    # direct label at the point each curve crosses 1e-6
    j = np.argmin(np.abs(np.log10(np.maximum(inv, 1e-30)) - (-5.2)))
    ax.annotate(f'{TC} °C', (tb[j]/DAY, inv[j]*1.8), color=ORD4[i],
                fontsize=10, fontweight='bold', ha='left')
ax.axhline(P_CRIT * V_FREE, color=CRIT, lw=1.6, ls=(0, (5, 4)))
ax.text(0.055, P_CRIT*V_FREE*1.6, 'no-getter budget:  P$_{crit}$·V = 10$^{-4}$ torr·L', color=CRIT, fontsize=9)
ax.axhline(0.041, color=SERIOUS, lw=1.6, ls=(0, (5, 4)))
ax.text(0.055, 0.041*1.6, 'ice budget: ~100 nm on cold filter ≈ 0.04 mg ≈ 0.04 torr·L', color=SERIOUS, fontsize=9)
ax.axhline(I_SURF0/3.0, color=MUTED, lw=1.2, ls=(0, (2, 3)))
ax.text(20, I_SURF0/3.0*1.5, '1 monolayer on 300 cm²', color=MUTED, fontsize=8.5)
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xlim(0.05, 60); ax.set_ylim(1e-7, 12)
ax.set_xlabel('bake duration under pump  (days)')
ax.set_ylabel('extractable water remaining inside dewar  (torr·L)')
ax.set_title('Bakeout progress: water inventory vs bake time and temperature')
ax.text(0.055, 2.2e-7, 'surface: 3 monolayers on 300 cm² · polymer: 0.5 g epoxy-class @ 1 wt% H$_2$O, 0.3 & 1 mm layers  (representative)',
        color=MUTED, fontsize=8.5)
ax.legend(loc='upper right', frameon=False, labelcolor=INK2)
fig.savefig('fig2_bake_inventory.png', dpi=200)
plt.close(fig)

# ============================================================ FIGURE 3
# Sealed warm pressure vs storage time, family of 85C bake durations
fig, ax = plt.subplots(figsize=(8.6, 5.2), constrained_layout=True)
ts = np.logspace(np.log10(3600), np.log10(30 * YR), 500)
bakes = [1, 3, 7, 14]
for i, bd in enumerate(bakes):
    ptot, pw = sealed_pressure(bd * DAY, 358.15, ts)
    ax.plot(ts / DAY, pw, color=ORD4[i], lw=2, label=f'85 °C × {bd} d bake — water')
    k = np.argmin(np.abs(np.log10(pw + 1e-12) - np.log10(np.maximum(pw.max()*0.7, 1e-9))))
    ax.annotate(f'{bd} d', (ts[k]/DAY, pw[k]*1.7), color=ORD4[i], fontsize=10, fontweight='bold')
# hydrogen accumulation (no getter)
ax.plot(ts / DAY, Q_H2 * ts / V_FREE, color=MUTED, lw=1.8, ls=(0, (5, 3)),
        label='H$_2$, baked steel (no getter)')
ax.annotate('H$_2$ (no getter)', (130, 0.085), color=MUTED,
            fontsize=9.5, fontweight='bold', rotation=13)
# gettered case
pget = np.maximum(1e-7, Q_CH4 * ts / V_FREE)
ax.plot(ts / DAY, pget, color=CAT[1], lw=2, ls='solid', label='with activated getter (any bake)')
ax.annotate('with getter → CH$_4$/He-limited', (1.2e3, 2.2e-7), color=CAT[1],
            fontsize=9.5, fontweight='bold')
ax.axhline(P_CRIT, color=CRIT, lw=1.6, ls=(0, (5, 4)))
ax.text(0.05, P_CRIT*1.7, 'end-of-life criterion 10$^{-3}$ torr', color=CRIT, fontsize=9.5)
xt = [1/24, 1, 7, 30, 182, 365, 3652, 10957]
ax.set_xscale('log'); ax.set_yscale('log')
ax.set_xticks(xt, ['1 h', '1 d', '1 wk', '1 mo', '6 mo', '1 yr', '10 yr', '30 yr'])
ax.set_xlim(1/24, 11000); ax.set_ylim(3e-8, 30)
ax.minorticks_off()
ax.set_xlabel('storage time after pinch-off  (22 °C)')
ax.set_ylabel('sealed dewar internal pressure  (torr, warm)')
ax.set_title('What the vacuum does after you stop pumping: pressure vs storage time')
ax.legend(loc='upper left', frameon=False, labelcolor=INK2, fontsize=9)
fig.savefig('fig3_sealed_pressure.png', dpi=200)
plt.close(fig)

# ============================================================ FIGURE 4
# Vacuum life vs bake duration ("stop early" curve)
fig, ax = plt.subplots(figsize=(8.6, 5.2), constrained_layout=True)
tbd = np.logspace(np.log10(0.3), np.log10(45), 140)
CAP = 30 * YR
for i, TC in enumerate(temps):
    life = np.array([water_life(b * DAY, TC + 273.15) for b in tbd])
    lifec = np.minimum(life, CAP)
    ax.plot(tbd, lifec / DAY, color=ORD4[i], lw=2, label=f'{TC} °C bake')
    # label just right of the near-vertical section, at life = 75 days
    fin = np.isfinite(life)
    xc = np.interp(np.log10(75.0), np.log10(np.maximum(life[fin]/DAY, 1e-3)), tbd[fin])
    ax.annotate(f'{TC} °C', (xc*1.10, 75), color=ORD4[i],
                fontsize=10, fontweight='bold', ha='left', va='center')
# no-getter H2 ceiling band: q_H2 1e-13..1e-12 torr L/s/cm2
lo = P_CRIT / (1e-12 * A_int / V_FREE) / DAY
hi = P_CRIT / (1e-13 * A_int / V_FREE) / DAY
ax.axhspan(lo, hi, color=MUTED, alpha=0.16, lw=0)
ax.text(0.33, np.sqrt(lo*hi), 'no-getter ceiling — H$_2$ from steel alone\n(q$_{H_2}$ = 10$^{-13}$…10$^{-12}$ torr·L·s$^{-1}$·cm$^{-2}$)',
        color=INK2, fontsize=9, va='center')
ax.axhline(10 * 365, color=CAT[1], lw=1.8, ls=(0, (5, 3)))
ax.text(0.33, 10*365*1.12, 'with getter: water & H$_2$ pumped after seal-off —\nlife → getter capacity, CH$_4$, He (~10–20 yr class)',
        color=CAT[1], fontsize=9, va='bottom')
ax.set_xscale('log'); ax.set_yscale('log')
yt = [1/24, 1, 7, 30, 182, 365, 3652]
ax.set_yticks(yt, ['1 h', '1 d', '1 wk', '1 mo', '6 mo', '1 yr', '10 yr'])
ax.set_xticks([0.5, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45], ['0.5', '1', '2', '3', '5', '7', '10', '14', '21', '30', '45'])
ax.minorticks_off()
ax.set_xlim(0.3, 45); ax.set_ylim(1/24, CAP/DAY)
ax.set_xlabel('bake duration under pump  (days)')
ax.set_ylabel('sealed life to 10$^{-3}$ torr from water alone')
ax.set_title('The curve you asked for: vacuum life vs bake duration')
ax.legend(loc='lower right', frameon=False, labelcolor=INK2)
fig.savefig('fig4_life_vs_bake.png', dpi=200)
plt.close(fig)
print('figures written')
