"""Gas heat conduction between the warm shell and the cold space.

Free-molecular regime (Kn >> 1): Corruccini/Kennard result
    q = alpha_eff * Lambda0 * P * (T_hot - T_cold)      [W/m^2, P in Pa]
    Lambda0 = (gamma+1)/(gamma-1) * sqrt( R / (8 pi M T_gauge) )
Continuum plateau: q = k_gas * dT / gap.
Transition regime bridged with the parallel-sum (Sherman-type) interpolation.

References: Corruccini, Vacuum 7-8, 19 (1959); Barron & Nellis, Cryogenic Heat
Transfer 2nd ed., gas-conduction chapter.
"""
import numpy as np
from .constants import R_GAS, TORR_PA, T_ACCOUNT


class GasSpecies:
    """gamma, molar mass [kg/mol], combined accommodation, continuum k [W/m/K] near the
    log-mean gap temperature (representative)."""

    def __init__(self, name, gamma, molar_mass, alpha_eff, k_cont):
        self.name, self.gamma, self.M = name, gamma, molar_mass
        self.alpha_eff, self.k_cont = alpha_eff, k_cont

    def lambda0(self, T_gauge=T_ACCOUNT):
        """Free-molecular conduction coefficient, W m^-2 Pa^-1 K^-1."""
        g = self.gamma
        return (g + 1.0) / (g - 1.0) * np.sqrt(R_GAS / (8.0 * np.pi * self.M * T_gauge))


# Representative species set. alpha_eff values are combined two-surface
# accommodation coefficients (design-dependent; He and H2 accommodate poorly).
SPECIES = {
    "air": GasSpecies("air/N2", 1.40, 28.97e-3, 0.9, 0.0177),
    "h2": GasSpecies("H2", 1.41, 2.016e-3, 0.4, 0.125),
    "he": GasSpecies("He", 1.667, 4.003e-3, 0.31, 0.11),
}


def gas_heat_flux(P_torr, dT, gas="air", gap_m=5e-3):
    """Heat flux [W/m^2] vs pressure [torr, measured warm], bridging fm->continuum."""
    sp = SPECIES[gas]
    P = np.asarray(P_torr, dtype=float) * TORR_PA
    if dT <= 0.0:
        return np.zeros_like(P) if P.ndim else 0.0
    q_fm = sp.alpha_eff * sp.lambda0() * P * dT
    q_ct = sp.k_cont * dT / gap_m
    return 1.0 / (1.0 / np.maximum(q_fm, 1e-300) + 1.0 / np.maximum(q_ct, 1e-300))


def gas_load_W(P_torr, cfg, gas="air", T_cold=None):
    """Total gas-conduction load [W] on the cold space for a config dict."""
    dT = cfg["shell_temp_K"] - (cfg["cold_temp_K"] if T_cold is None else T_cold)
    dT = max(dT, 0.0)
    A = cfg["cold_area_cm2"] * 1e-4
    return gas_heat_flux(P_torr, dT, gas=gas, gap_m=cfg["gap_mm"] * 1e-3) * A


def mean_free_path_air_m(P_torr, T=T_ACCOUNT):
    """Mean free path of air, m (lambda*P ~ 6.6e-3 Pa*m at 295 K)."""
    return 6.6e-3 / (np.asarray(P_torr) * TORR_PA)
