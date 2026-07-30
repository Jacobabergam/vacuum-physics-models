"""Water and fixed-gas outgassing sources inside the dewar.

Three source classes:

1. SurfaceWater — physisorbed/chemisorbed water on metal surfaces. First-order
   desorption over a uniform distribution of binding energies (Redhead-type
   multi-energy model, JVST A 13, 467 (1995)). Reproduces the empirical 1/t
   pump-down law for unbaked metal within ~x1.5 (see selfcheck).

2. Adhesive — a Fickian water reservoir parameterized by VOLUME and EXPOSED
   AREA. The governing length is the effective diffusion depth
        L_eff = volume / exposed_area
   i.e. a slab of thickness L_eff drying through its exposed face (back face
   sealed — the usual case for a bond line or potting against metal). The
   two-stage bake->storage history is exact for Fickian kinetics because the
   eigenmode decay argument is additive:  X = (D_bake*t_bake + D_store*t_store)/L_eff^2.

3. FixedGas — constant-rate emitters per unit steel area (H2 from the metal
   bulk, CH4 trace). Conservative (no decay over years).

All amounts in torr·L at the accounting temperature (295 K).
"""
import numpy as np
from .constants import KB_EV, ML_TORRL_PER_CM2, MG_H2O_TORRL, DAY


def slab_remaining_frac(X, nterms=80):
    """Remaining mass fraction of a slab, X = D*t/L^2 (one exposed face,
    initial uniform concentration, perfect-sink boundary)."""
    X = np.asarray(X, dtype=float)
    f = np.zeros_like(X)
    norm = 0.0
    for n in range(nterms):
        m = 2 * n + 1
        coef = 8.0 / (m * np.pi) ** 2
        f += coef * np.exp(-((m * np.pi / 2.0) ** 2) * X)
        norm += coef
    return np.clip(f / norm, 0.0, 1.0)   # normalized so f(0) = 1 exactly


class SurfaceWater:
    def __init__(self, area_cm2, monolayers=3.0, E_lo=0.75, E_hi=1.15,
                 nu=1e13, nE=3000):
        self.area = area_cm2
        self.monolayers = monolayers
        self.nu = nu
        self.E = np.linspace(E_lo, E_hi, nE)
        self.dE = E_hi - E_lo
        self.inventory0 = monolayers * ML_TORRL_PER_CM2 * area_cm2  # torr·L

    def _k(self, T):
        return self.nu * np.exp(-self.E / (KB_EV * T))

    def remaining_torrL(self, t_bake_s, T_bake_K):
        theta = np.exp(-t_bake_s * self._k(T_bake_K))
        return self.inventory0 * np.trapezoid(theta, self.E) / self.dE

    def released_after_seal_torrL(self, t_bake_s, T_bake_K, t_store_s, T_store_K):
        """Cumulative torr·L released into the sealed volume (vector over t_store)."""
        theta_b = np.exp(-t_bake_s * self._k(T_bake_K))
        ks = self._k(T_store_K)
        t = np.atleast_1d(np.asarray(t_store_s, dtype=float))
        rel = [np.trapezoid(theta_b * (1.0 - np.exp(-tt * ks)), self.E) / self.dE
               for tt in t]
        return self.inventory0 * np.array(rel)

    def rate_torrL_s(self, t_s, T_K):
        """Instantaneous outgassing rate under pumping at temperature T."""
        k = self._k(T_K)
        return self.inventory0 * np.trapezoid(k * np.exp(-t_s * k), self.E) / self.dE


class Adhesive:
    """Fickian water reservoir defined by volume and exposed area."""

    def __init__(self, name, volume_cm3, exposed_area_cm2, density_g_cm3=1.15,
                 water_wt_pct=1.0, D_295K_cm2_s=2e-9, E_a_eV=0.45):
        self.name = name
        self.volume = volume_cm3
        self.area = exposed_area_cm2
        self.L_eff = volume_cm3 / exposed_area_cm2            # cm
        self.water_mg0 = volume_cm3 * density_g_cm3 * (water_wt_pct / 100.0) * 1e3
        self.D0 = D_295K_cm2_s / np.exp(-E_a_eV / (KB_EV * 295.0))
        self.E_a = E_a_eV

    def D(self, T_K):
        return self.D0 * np.exp(-self.E_a / (KB_EV * T_K))

    def tau1_s(self, T_K):
        """Slowest Fickian time constant, 4 L^2 / (pi^2 D)."""
        return 4.0 * self.L_eff ** 2 / (np.pi ** 2 * self.D(T_K))

    def remaining_mg(self, t_bake_s, T_bake_K):
        X = self.D(T_bake_K) * t_bake_s / self.L_eff ** 2
        return self.water_mg0 * slab_remaining_frac(X)

    def released_after_seal_mg(self, t_bake_s, T_bake_K, t_store_s, T_store_K):
        Xb = self.D(T_bake_K) * t_bake_s / self.L_eff ** 2
        Xs = self.D(T_store_K) * np.atleast_1d(np.asarray(t_store_s, float)) / self.L_eff ** 2
        return self.water_mg0 * (slab_remaining_frac(Xb) - slab_remaining_frac(Xb + Xs))


class OutgassingModel:
    """Aggregates all sources from a config dict (see configs/baseline_idca.yaml)."""

    def __init__(self, cfg):
        self.cfg = cfg
        sw = cfg["surface_water"]
        self.surface = SurfaceWater(
            area_cm2=sw.get("area_cm2", cfg["steel_area_cm2"]),
            monolayers=sw["monolayers"],
            E_lo=sw.get("E_lo_eV", 0.75), E_hi=sw.get("E_hi_eV", 1.15),
            nu=sw.get("nu_hz", 1e13))
        self.adhesives = [Adhesive(**a) for a in cfg.get("adhesives", [])]
        fg = cfg["fixed_gases"]
        A = cfg["steel_area_cm2"]
        self.Q_h2 = fg["q_h2_torrL_s_cm2"] * A       # torr·L/s
        self.Q_ch4 = fg["q_ch4_torrL_s_cm2"] * A

    # ---- inventory bookkeeping (bake progress) ----
    def water_inventory_torrL(self, t_bake_s, T_bake_K):
        inv = self.surface.remaining_torrL(t_bake_s, T_bake_K)
        inv += sum(a.remaining_mg(t_bake_s, T_bake_K) for a in self.adhesives) * MG_H2O_TORRL
        return inv

    def water_released_after_seal_torrL(self, t_bake_s, T_bake_K, t_store_s, T_store_K):
        rel = self.surface.released_after_seal_torrL(t_bake_s, T_bake_K, t_store_s, T_store_K)
        for a in self.adhesives:
            rel = rel + a.released_after_seal_mg(t_bake_s, T_bake_K, t_store_s, T_store_K) * MG_H2O_TORRL
        return rel
