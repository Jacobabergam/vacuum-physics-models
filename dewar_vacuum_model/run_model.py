#!/usr/bin/env python3
"""Run the full dewar bakeout / vacuum-life / cooldown study for a config.

    python3 run_model.py configs/baseline_idca.yaml

Writes a text report to stdout and four figures into outputs/.
"""
import sys, os
import numpy as np
from dewar_model.config import load_config
from dewar_model.constants import DAY, YEAR, MG_H2O_TORRL
from dewar_model.gas import gas_load_W
from dewar_model.outgassing import OutgassingModel
from dewar_model.sealed_life import SealedDewar
from dewar_model.cooldown import cooldown, enthalpy_cu_J, cp_cu
from dewar_model import plots


def fmt_life(s):
    if not np.isfinite(s):
        return ">30 yr"
    if s < 2 * DAY:
        return f"{s/3600:.1f} h"
    if s < 120 * DAY:
        return f"{s/DAY:.1f} d"
    return f"{s/YEAR:.2f} yr"


def main(cfg_path):
    cfg = load_config(cfg_path)
    og = OutgassingModel(cfg)
    sealed = SealedDewar(cfg, og)
    Ts = cfg["bake"]["storage_temp_C"] + 273.15

    print("=" * 78)
    print(f"DEWAR VACUUM MODEL — {os.path.basename(cfg_path)}")
    print("=" * 78)

    # ---- gas-conduction thresholds ----
    print("\n[1] Gas-conduction load on the cold space (air-equivalent):")
    for P in (1e-5, 1e-4, 1e-3, 1e-2):
        print(f"    P = {P:7.0e} torr  ->  {gas_load_W(P, cfg)*1e3:8.1f} mW")

    # ---- inventory ----
    print("\n[2] Water inventory (torr·L):")
    inv0 = og.water_inventory_torrL(0.0, 295.0)
    print(f"    initial: surface {og.surface.inventory0:.3f} + adhesives "
          f"{sum(a.water_mg0 for a in og.adhesives)*MG_H2O_TORRL:.3f}  =  {inv0:.3f}")
    print(f"    no-getter budget P_crit*V = {cfg['p_crit_torr']*cfg['free_volume_L']:.1e} torr·L")
    for a in og.adhesives:
        print(f"    - {a.name}: {a.water_mg0:.2f} mg, L_eff = {a.L_eff*10:.2f} mm, "
              f"tau1(85C) = {a.tau1_s(358.15)/3600:.1f} h, tau1(22C) = {a.tau1_s(295.15)/DAY:.1f} d")

    # ---- bake study ----
    print("\n[3] Remaining water and sealed water-only life vs bake:")
    hdr = "    bake      " + "".join(f"{d:>10d} d" for d in cfg["bake"]["durations_days"])
    print(hdr)
    for TC in cfg["bake"]["temps_C"]:
        T = TC + 273.15
        row_inv = [og.water_inventory_torrL(d * DAY, T) for d in cfg["bake"]["durations_days"]]
        row_life = [sealed.life_to_crit_s(d * DAY, T, "water", Ts)
                    for d in cfg["bake"]["durations_days"]]
        print(f"    {TC:3d} C inv " + "".join(f"{v:>11.1e}" for v in row_inv) + "  torr·L")
        print(f"          life" + "".join(f"{fmt_life(v):>12s}" for v in row_life))

    # ---- getter ----
    print("\n[4] Getter budget:")
    print(f"    capacity {cfg['getter']['capacity_torrL']:.1f} torr·L; "
          f"10-yr H2 load = {og.Q_h2*10*YEAR:.2f} torr·L; "
          f"10-yr CH4 pressure = {og.Q_ch4*10*YEAR/cfg['free_volume_L']:.1e} torr")
    for d in cfg["bake"]["durations_days"]:
        left = og.water_inventory_torrL(d * DAY, 358.15)
        print(f"    85C x {d:2d} d leftover water consumes "
              f"{left/cfg['getter']['capacity_torrL']*100:5.1f} % of getter capacity")

    # ---- cooldown ----
    th = cfg["thermal"]
    print(f"\n[5] Cooldown (effective Cu mass {th['m_cu_g']:.0f} g; "
          f"enthalpy 293->80 K = {enthalpy_cu_J(th['m_cu_g']*1e-3, 80, 293):.0f} J; "
          f"cp_Cu(300 K) = {cp_cu(300):.0f} J/kg/K Debye):")
    for P in (1e-6, 1e-4, 1e-3, 3e-3, 1e-2):
        for mf in (1.0, 2.0):
            r = cooldown(cfg, P, m_cu_g=th["m_cu_g"] * mf)
            s = (f"STALLS at {r['stall_T_K']:.0f} K" if r["stalled"]
                 else f"{r['time_s']/60:6.1f} min")
            print(f"    P = {P:7.0e} torr, m = {th['m_cu_g']*mf:5.1f} g  ->  {s}")

    # ---- figures ----
    outdir = os.path.join(os.path.dirname(os.path.abspath(cfg_path)), "..", "outputs")
    outdir = os.path.normpath(outdir)
    os.makedirs(outdir, exist_ok=True)
    plots.setup_style()
    plots.fig_inventory(cfg, og, os.path.join(outdir, "inventory_vs_bake.png"))
    plots.fig_life_vs_bake(cfg, sealed, os.path.join(outdir, "life_vs_bake.png"))
    plots.fig_cooldown_traces(cfg, os.path.join(outdir, "cooldown_traces.png"))
    plots.fig_cooldown_vs_pressure(cfg, os.path.join(outdir, "cooldown_vs_pressure.png"))
    print(f"\nFigures written to {outdir}/")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "configs/baseline_idca.yaml")
