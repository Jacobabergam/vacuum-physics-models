"""Sealed-volume pressure evolution after pinch-off, with and without a getter.

Without getter: P(t) = [water released + (Q_H2 + Q_CH4)*t] / V.
With getter (non-evaporable, Zr-V-Fe class): water and hydrogen are pumped to a
low floor while cumulative getterable load < capacity; methane and noble gases
are not pumped and accumulate regardless. After capacity exhaustion the
getterable gases accumulate from that point onward.
"""
import numpy as np
from .constants import DAY, YEAR


class SealedDewar:
    def __init__(self, cfg, outgassing):
        self.cfg = cfg
        self.og = outgassing
        self.V = cfg["free_volume_L"]
        self.P_crit = cfg["p_crit_torr"]
        g = cfg["getter"]
        self.getter_enabled = g["enabled"]
        self.capacity = g["capacity_torrL"]
        self.P_floor = g.get("p_floor_torr", 1e-7)

    def pressure_components(self, t_bake_s, T_bake_K, t_store_s, T_store_K=295.0):
        """Returns dict of partial pressures [torr] vs storage-time array (no getter)."""
        t = np.atleast_1d(np.asarray(t_store_s, float))
        p_w = self.og.water_released_after_seal_torrL(t_bake_s, T_bake_K, t, T_store_K) / self.V
        p_h2 = self.og.Q_h2 * t / self.V
        p_ch4 = self.og.Q_ch4 * t / self.V
        return {"water": p_w, "h2": p_h2, "ch4": p_ch4, "total": p_w + p_h2 + p_ch4}

    def pressure_with_getter(self, t_bake_s, T_bake_K, t_store_s, T_store_K=295.0):
        """Total pressure [torr] with the getter active. Capacity-limited."""
        t = np.atleast_1d(np.asarray(t_store_s, float))
        W = self.og.water_released_after_seal_torrL(t_bake_s, T_bake_K, t, T_store_K)
        consumed = W + self.og.Q_h2 * t                       # torr·L sorbed
        p = np.maximum(self.P_floor, self.og.Q_ch4 * t / self.V)
        over = consumed > self.capacity
        if np.any(over):
            p[over] += (consumed[over] - self.capacity) / self.V
        return p

    def life_to_crit_s(self, t_bake_s, T_bake_K, which="water",
                       T_store_K=295.0, t_max_s=100 * YEAR):
        """Storage time to reach P_crit. which: 'water' | 'total' | 'gettered'.
        Returns np.inf if never reached within t_max."""
        tg = np.logspace(np.log10(60.0), np.log10(t_max_s), 500)
        if which == "gettered":
            p = self.pressure_with_getter(t_bake_s, T_bake_K, tg, T_store_K)
        else:
            p = self.pressure_components(t_bake_s, T_bake_K, tg, T_store_K)[which]
        if p[-1] < self.P_crit:
            return np.inf
        return float(np.interp(self.P_crit, p, tg))
