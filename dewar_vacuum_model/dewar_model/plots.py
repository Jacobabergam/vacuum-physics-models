"""Figure set for a configured dewar. Palette: validated dataviz reference
instance (light mode); ordered families use the ordinal blue ramp."""
import numpy as np
import matplotlib as mpl
import matplotlib.pyplot as plt
from .constants import DAY, YEAR, MG_H2O_TORRL
from .cooldown import cooldown, cooldown_time_vs_pressure

SURF, INK, INK2, MUTED = '#fcfcfb', '#0b0b0b', '#52514e', '#898781'
GRID, AXIS = '#e1e0d9', '#c3c2b7'
CAT = ['#2a78d6', '#008300', '#e87ba4', '#eda100']
ORD4 = ['#86b6ef', '#3987e5', '#1c5cab', '#0d366b']
ORD3 = ['#86b6ef', '#2a78d6', '#0d366b']
CRIT, SERIOUS = '#d03b3b', '#ec835a'


def setup_style():
    mpl.rcParams.update({
        'font.family': 'sans-serif', 'font.size': 10.5,
        'axes.edgecolor': AXIS, 'axes.labelcolor': INK2, 'axes.titlecolor': INK,
        'xtick.color': MUTED, 'ytick.color': MUTED,
        'axes.grid': True, 'grid.color': GRID, 'grid.linewidth': 0.8,
        'axes.spines.top': False, 'axes.spines.right': False,
        'figure.facecolor': SURF, 'axes.facecolor': SURF, 'savefig.facecolor': SURF,
        'axes.titlesize': 12, 'axes.titleweight': 'bold', 'axes.titlepad': 12,
    })


def fig_inventory(cfg, og, out):
    fig, ax = plt.subplots(figsize=(8.4, 5.0), constrained_layout=True)
    tb = np.logspace(np.log10(0.05), np.log10(60), 250) * DAY
    temps = cfg["bake"]["temps_C"]
    for i, TC in enumerate(temps):
        inv = np.array([og.water_inventory_torrL(t, TC + 273.15) for t in tb])
        ax.plot(tb / DAY, inv, color=ORD4[i % 4], lw=2, label=f'{TC} °C bake')
    ax.axhline(cfg["p_crit_torr"] * cfg["free_volume_L"], color=CRIT, lw=1.6, ls=(0, (5, 4)))
    ax.text(0.055, cfg["p_crit_torr"] * cfg["free_volume_L"] * 1.6,
            'no-getter budget  P·V', color=CRIT, fontsize=9)
    ax.axhline(0.041, color=SERIOUS, lw=1.6, ls=(0, (5, 4)))
    ax.text(0.055, 0.041 * 1.6, 'ice budget ~100 nm on cold filter', color=SERIOUS, fontsize=9)
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_xlim(0.05, 60); ax.set_ylim(1e-7, 30)
    ax.set_xlabel('bake duration under pump  (days)')
    ax.set_ylabel('extractable water remaining  (torr·L)')
    ax.set_title('Bakeout progress — configured dewar')
    ax.legend(loc='upper right', frameon=False, labelcolor=INK2)
    fig.savefig(out, dpi=200); plt.close(fig)


def fig_life_vs_bake(cfg, sealed, out):
    fig, ax = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    tbd = np.logspace(np.log10(0.3), np.log10(45), 90)
    CAPY = 30 * YEAR
    temps = cfg["bake"]["temps_C"]
    Ts = cfg["bake"]["storage_temp_C"] + 273.15
    for i, TC in enumerate(temps):
        life = np.array([sealed.life_to_crit_s(b * DAY, TC + 273.15, "water", Ts)
                         for b in tbd])
        ax.plot(tbd, np.minimum(life, CAPY) / DAY, color=ORD4[i % 4], lw=2,
                label=f'{TC} °C bake')
    budget = cfg["p_crit_torr"] * cfg["free_volume_L"]
    lo = budget / (1e-12 * cfg["steel_area_cm2"]) / DAY   # q_H2 = 1e-12 torr·L/s/cm2
    hi = budget / (1e-13 * cfg["steel_area_cm2"]) / DAY   # q_H2 = 1e-13
    ax.axhspan(lo, hi, color=MUTED, alpha=0.15, lw=0)
    ax.text(0.33, np.sqrt(lo * hi),
            'no-getter ceiling — H$_2$ from steel alone', color=INK2, fontsize=9, va='center')
    ax.axhline(10 * 365, color=CAT[1], lw=1.8, ls=(0, (5, 3)))
    ax.text(0.33, 10 * 365 * 1.12, 'with getter: capacity / CH$_4$ / He limited',
            color=CAT[1], fontsize=9, va='bottom')
    ax.set_xscale('log'); ax.set_yscale('log')
    ax.set_yticks([1 / 24, 1, 7, 30, 182, 365, 3652],
                  ['1 h', '1 d', '1 wk', '1 mo', '6 mo', '1 yr', '10 yr'])
    ax.set_xticks([0.5, 1, 2, 3, 5, 7, 10, 14, 21, 30, 45],
                  ['0.5', '1', '2', '3', '5', '7', '10', '14', '21', '30', '45'])
    ax.minorticks_off()
    ax.set_xlim(0.3, 45); ax.set_ylim(1 / 24, CAPY / DAY)
    ax.set_xlabel('bake duration under pump  (days)')
    ax.set_ylabel(f'sealed life to {cfg["p_crit_torr"]:.0e} torr, water alone')
    ax.set_title('Vacuum life vs bake duration — configured dewar')
    ax.legend(loc='lower right', frameon=False, labelcolor=INK2)
    fig.savefig(out, dpi=200); plt.close(fig)


def fig_cooldown_traces(cfg, out, pressures=(1e-5, 1e-3, 3e-3, 1e-2)):
    fig, ax = plt.subplots(figsize=(8.4, 5.0), constrained_layout=True)
    for i, P in enumerate(pressures):
        r = cooldown(cfg, P, t_max_s=3600.0)
        lab = f'{P:.0e} torr' + ('  (stalls)' if r["stalled"] else '')
        ax.plot(r["t_trace"] / 60.0, r["T_trace"], lw=2, color=ORD4[i % 4], label=lab)
        if r["stalled"]:
            ax.annotate('stall', (r["t_trace"][-1] / 60, r["T_trace"][-1] + 4),
                        color=CRIT, fontsize=9, fontweight='bold', ha='right')
    ax.axhline(cfg["cold_temp_K"], color=MUTED, lw=1.2, ls=(0, (2, 3)))
    ax.text(0.3, cfg["cold_temp_K"] + 3, f'setpoint {cfg["cold_temp_K"]:.0f} K',
            color=INK2, fontsize=9)
    ax.set_xlabel('time  (minutes)')
    ax.set_ylabel('cold-space temperature  (K)')
    ax.set_title(f'Cooldown traces vs internal pressure — '
                 f'{cfg["thermal"]["m_cu_g"]:.0f} g effective Cu')
    ax.set_xlim(0, None); ax.set_ylim(60, cfg["shell_temp_K"] + 5)
    ax.legend(loc='upper right', frameon=False, labelcolor=INK2)
    fig.savefig(out, dpi=200); plt.close(fig)


def fig_cooldown_vs_pressure(cfg, out, mass_factors=(0.5, 1.0, 2.0)):
    fig, ax = plt.subplots(figsize=(8.4, 5.2), constrained_layout=True)
    P = np.logspace(-6, -1.3, 40)
    m0 = cfg["thermal"]["m_cu_g"]
    for i, f in enumerate(mass_factors):
        tt = cooldown_time_vs_pressure(cfg, P, m_cu_g=m0 * f) / 60.0
        ax.plot(P, tt, lw=2, color=ORD3[i % 3], label=f'{m0*f:.0f} g effective Cu')
        ok = np.isfinite(tt)
        if np.any(~ok):
            ax.axvline(P[np.argmax(~ok)], color=ORD3[i % 3], lw=1.0, ls=(0, (2, 3)))
    ax.axvline(1e-4, color=MUTED, lw=1.3, ls=(0, (2, 3)))
    ax.text(1.13e-4, ax.get_ylim()[0] + 0.5, 'operating ceiling 10$^{-4}$ torr',
            color=INK2, fontsize=9, rotation=90, va='bottom')
    ax.set_xscale('log')
    ax.set_xlabel('internal pressure during cooldown  (torr, non-condensable air-equivalent)')
    ax.set_ylabel('cooldown time to setpoint  (minutes)')
    ax.set_title('Cooldown time vs vacuum and effective copper mass\n'
                 '(curves end where the cooler stalls)')
    ax.legend(loc='upper left', frameon=False, labelcolor=INK2)
    fig.savefig(out, dpi=200); plt.close(fig)
