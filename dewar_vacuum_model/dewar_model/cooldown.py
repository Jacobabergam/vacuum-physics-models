"""Cooldown of the cold space: lumped copper thermal mass vs cooler lift and loads.

    m_Cu * c_p(T) * dT/dt = -( Q_lift(T) - Q_loads(T, P) )

- c_p(T) for copper from the Debye model (theta_D = 343 K), accurate to ~5-10 %
  over 60-300 K (slightly low vs measured values: 373 vs 385 J/kg/K at 300 K,
  ~190 vs ~205 at 80 K). Good enough for trade studies; substitute a NIST table
  if you need better.
- Q_lift(T): representative linear net-refrigeration curve between the 80 K and
  300 K points from the config (rotary/linear Stirling class).
- Q_loads: radiation (effective emissivity), lead/support conduction (linear G),
  and gas conduction at the instantaneous cold temperature and the configured
  internal pressure (treated as non-condensable air-equivalent, constant during
  cooldown — conservative; water cryopumps out below ~150 K shield temperature).

'Effective copper mass' = the copper-equivalent heat capacity of everything the
cold tip must cool (shield, platform, FPA, filter mount). For other materials,
convert: m_eff = sum(m_i * cp_i / cp_Cu) near ~150 K.
"""
import numpy as np
from scipy.integrate import solve_ivp
from .constants import R_GAS, M_CU, THETA_D_CU, SIGMA_SB
from .gas import gas_heat_flux

# ---- Debye specific heat for copper, precomputed on a grid ----
_Tgrid = np.linspace(4.0, 340.0, 400)


def _debye_cv_molar(T):
    x_up = THETA_D_CU / T
    x = np.linspace(1e-6, x_up, 2000)
    integ = np.trapezoid(x ** 4 * np.exp(x) / (np.exp(x) - 1.0) ** 2, x)
    return 9.0 * R_GAS * (T / THETA_D_CU) ** 3 * integ  # J/(mol K)


_cp_grid = np.array([_debye_cv_molar(t) for t in _Tgrid]) / M_CU  # J/(kg K)


def cp_cu(T):
    """Copper specific heat, J/(kg K), Debye model."""
    return np.interp(T, _Tgrid, _cp_grid)


def enthalpy_cu_J(m_kg, T1, T2):
    """Heat removed cooling m_kg of copper from T2 down to T1."""
    T = np.linspace(T1, T2, 500)
    return m_kg * np.trapezoid(cp_cu(T), T)


def q_lift_W(T_cold, cfg):
    c = cfg["cooler"]
    slope = (c["q_lift_300K_W"] - c["q_lift_80K_W"]) / 220.0
    return np.maximum(0.0, c["q_lift_80K_W"] + slope * (T_cold - 80.0))


def q_loads_W(T_cold, P_torr, cfg):
    th = cfg["thermal"]
    Tsh = cfg["shell_temp_K"]
    A = cfg["cold_area_cm2"] * 1e-4
    q_rad = th["eps_eff"] * SIGMA_SB * A * (Tsh ** 4 - T_cold ** 4)
    q_lead = th["g_leads_W_K"] * (Tsh - T_cold)
    q_gas = gas_heat_flux(P_torr, Tsh - T_cold, gas="air",
                          gap_m=cfg["gap_mm"] * 1e-3) * A
    return q_rad + q_lead + q_gas


def cooldown(cfg, P_torr, m_cu_g=None, t_max_s=7200.0):
    """Integrate the cooldown. Returns dict:
    time_s (to setpoint, np.nan if stalled), stalled, stall_T_K, t_trace, T_trace."""
    m = (cfg["thermal"]["m_cu_g"] if m_cu_g is None else m_cu_g) * 1e-3
    T0, Tset = cfg["shell_temp_K"], cfg["cold_temp_K"]

    def rhs(t, y):
        T = y[0]
        net = q_lift_W(T, cfg) - q_loads_W(T, P_torr, cfg)
        return [-net / (m * cp_cu(T))]

    def hit_setpoint(t, y):
        return y[0] - Tset
    hit_setpoint.terminal, hit_setpoint.direction = True, -1

    def stalled_ev(t, y):
        # stall: net refrigeration ~ 0 while still warm
        return (q_lift_W(y[0], cfg) - q_loads_W(y[0], P_torr, cfg)) - 1e-4
    stalled_ev.terminal, stalled_ev.direction = True, -1

    sol = solve_ivp(rhs, (0.0, t_max_s), [float(T0)],
                    events=[hit_setpoint, stalled_ev],
                    max_step=t_max_s / 200.0, rtol=1e-6, atol=1e-4)
    reached = len(sol.t_events[0]) > 0
    stalled = (not reached)
    return {
        "time_s": float(sol.t_events[0][0]) if reached else float("nan"),
        "stalled": stalled,
        "stall_T_K": float(sol.y[0, -1]) if stalled else None,
        "t_trace": sol.t, "T_trace": sol.y[0],
    }


def cooldown_time_vs_pressure(cfg, P_array, m_cu_g=None):
    """Vector of cooldown times [s] (nan where stalled)."""
    return np.array([cooldown(cfg, P, m_cu_g=m_cu_g)["time_s"] for P in P_array])
