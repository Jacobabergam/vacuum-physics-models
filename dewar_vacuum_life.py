#!/usr/bin/env python3
"""IR-camera dewar vacuum life: sealed pressure rise, getter budget, heat load.

A tactical IDCA-class dewar is baked, pinched off, and then lives or dies on
its internal gas balance. This model tracks, over 1 day .. 30 years of sealed
storage at the warm temperature:

  * water re-emerging from what the bake left behind - metal surfaces
    (Redhead multi-energy desorption), adhesive bond lines / potting (Fickian
    reservoirs, two-stage bake->storage), and the cold-shield black coating
    (a thin Fickian film: Aeroglaze Z306 paint, or Acktar's inorganic film);
  * hydrogen from the steel bulk and methane trace, constant in time;
  * a St707-class getter as a DUAL capacity ledger - water (surface-limited,
    ~2.4 torr.L/g) and H2 (bulk, ~170 torr.L/g) - blind to CH4;
  * the free-molecular gas-conduction heat load those partials put on the
    cold space when operating (q = alpha.Lambda0.P.dT per unit area, times the
    cold-shield area - the load is AREA-dependent, not gap-dependent, until
    the continuum plateau near 0.1 torr), with the honest species accounting:
    the 80 K shield cryopumps water, so the operating load is carried by
    H2 and CH4 - and per torr those conduct MORE than air
    (Lambda0: H2 4.38, CH4 1.97, air 1.18 W m-2 K-1 Pa-1);
  * cooldown time and stall as the pressure rises over life (Debye c_p(Cu),
    linear cooler lift between 80 K / 300 K anchors).

Physics is mirrored 1:1 from dewar_vacuum_model/dewar_model/{outgassing,
sealed_life,gas,cooldown}.py, stdlib-only so `--check` runs anywhere. The HTML
twin (dewar_vacuum_life.html) implements identical physics; the PARITY block
printed by --check must agree with the page's __parity() to <= 0.5 % (REQ-U2).

Every constant traces to research/data/*.json (REQ-D1): mainly
dewar_life_materials.json (this page's materials, sourced 2026-08-13) and
outgassing_anchor_rates.json (rates and getter capacities).

Equation sources:
  Fickian slab series & two-stage additivity . Crank, The Mathematics of
      Diffusion 2nd ed. (1975), ch. 4 (plane sheet) and ch. 7 (t' = int D dt)
  Multi-energy first-order desorption ........ Redhead, JVST A 13, 467 (1995);
      Li & Dylla, JVST A 11, 1702 (1993); Chiggiato, arXiv:2006.07124
  Free-molecular conduction + bridge ......... Corruccini, Vacuum 7-8, 19
      (1959); Kennard, Kinetic Theory of Gases (1938); Barron & Nellis,
      Cryogenic Heat Transfer 2nd ed. (Sherman-type parallel-sum bridge)
  Ice vapor pressure at 80 K << 1e-10 torr ... Honig & Hook, RCA Rev. 21, 360
      (1960) - why water drops out of the cold conduction budget
  Getter capacities .......................... Sandia St707 report
      (psec.uchicago.edu/getters/sandia_ST707_getter_data_105402.pdf);
      UChicago PSEC H2O-monolayer note
  Debye c_p, theta_D(Cu)=343 K ............... Kittel, Intro. Solid State Phys.

Units (REQ-U1): torr, torr.L at 295 K, cm for outgassing, m for heat transfer,
eV, K internally (deg C only in the UI). 1 mg H2O = 1.02 torr.L;
1 monolayer = 3.05e-5 torr.L/cm^2.

Numeric self-check:  python3 dewar_vacuum_life.py --check
Static figure:       python3 dewar_vacuum_life.py   (needs matplotlib)
"""

import json
import math
import sys

# ---------------- constants ----------------
KB_EV = 8.617333e-5      # Boltzmann, eV/K
KB_J = 1.380649e-23      # Boltzmann, J/K
R_GAS = 8.314462         # molar gas constant, J/(mol K)
NA = 6.02214076e23       # Avogadro, 1/mol
SIGMA_SB = 5.670374e-8   # Stefan-Boltzmann, W/(m^2 K^4)
TORR_PA = 133.322        # Pa per torr
DAY = 86400.0            # s
YEAR = 3.156e7           # s
T_ACCOUNT = 295.0        # K - torr.L amounts accounted here (REQ-U1)
M_H2O = 18.015e-3        # kg/mol
M_CU = 63.546e-3         # kg/mol
THETA_D_CU = 343.0       # K, Debye temperature of copper (Kittel)

# ideal-gas accounting: molecules in 1 torr.L at 295 K, then the two
# conversions the whole model runs on (computed, outgassing_anchor_rates.json
# entry monolayer_conversion)
MOLEC_PER_TORRL = TORR_PA * 1e-3 / (KB_J * T_ACCOUNT)          # 3.27e19
ML_TORRL_PER_CM2 = 1e15 / MOLEC_PER_TORRL                      # 3.05e-5
MG_H2O_TORRL = (1e-3 / (M_H2O * 1e3)) * NA / MOLEC_PER_TORRL   # 1.02

# ---- fixed dewar context (baseline_idca.yaml; dewar_life_materials.json
#      entry cooler_thermal_baseline - representative tactical class) ----
T_SHELL = 293.0          # K, vacuum shell
T_COLD = 80.0            # K, reference FPA setpoint (anchors); the UI setpoint
                         # is the cold_K parameter, 80-150 K (HOT-detector trend)
GAP_MM = 5.0             # shell-to-shield gap (sets the continuum plateau)
P_CRIT = 1e-3            # torr warm - end-of-life criterion (VACUUM_REQUIREMENT.md)
M_CU_G = 15.0            # g, Cu-equivalent cold mass
EPS_EFF = 0.03           # shell<->shield effective emissivity
G_LEADS = 0.7e-3         # W/K, leads + supports
Q_LIFT_80 = 0.6          # W net lift at 80 K
Q_LIFT_300 = 3.0         # W net lift near ambient
FILTER_CM2 = 2.0         # cm^2 cold filter collecting cryopumped water
RHO_ICE = 0.93           # g/cm^3 (dewar_life_materials.json ice_on_filter_conversion)

# ---- fixed gas emitters, per cm^2 of internal steel ----
# H2: baked 304-class steel, band 1e-13..3e-12 (Chiggiato CAS lecture;
#     outgassing_anchor_rates.json H2_baked_steel). CH4: ~1e-15, decade
#     uncertainty, NOT gettered - it alone sets the gettered-life ceiling
#     (outgassing_anchor_rates.json CH4_steel).
Q_H2_CM2 = 1e-12         # torr.L/s/cm^2
Q_CH4_CM2 = 1e-15        # torr.L/s/cm^2

# ---- surface water (Redhead multi-energy; outgassing.py mirror) ----
# 3 ML initial after air exposure (1-10 typical), uniform binding-energy
# window 0.75-1.15 eV, nu = 1e13 /s (Redhead 1995; Li & Dylla 1993;
# outgassing_anchor_rates.json water_desorption_energy_window).
SW_ML = 3.0
SW_E_LO, SW_E_HI = 0.75, 1.15   # eV
SW_NU = 1e13                    # 1/s
SW_NE = 400                     # energy-grid points - SAME in the HTML twin
                                # (parity needs matching discretization)

# ---- shared water diffusivity for all organics ----
# D(295 K) = 2e-9 cm^2/s (range 5e-10..8e-9), Ea = 0.45 eV - epoxy moisture
# literature (outgassing_anchor_rates.json epoxy_water_diffusivity). Shared
# with the polyurethane paint film: flagged assumption, see
# dewar_life_materials.json shared_water_diffusivity - thin films fully
# deplete during any competent bake, so coating results are D-insensitive.
D_295 = 2e-9             # cm^2/s
E_A = 0.45               # eV
D0 = D_295 / math.exp(-E_A / (KB_EV * 295.0))


def d_coef(T_K):
    """Arrhenius water diffusivity in the organic, cm^2/s."""
    return D0 * math.exp(-E_A / (KB_EV * T_K))


# ================= materials (dewar_life_materials.json) ==================
# Adhesive presets. water_wt_pct is the ASTM E595 WVR except for the generic
# entry (equilibrium moisture) - the WVR proxy is a LOWER bound on long-soak
# moisture, flagged in the data file and in-app.
ADHESIVES = {
    "generic": dict(
        label="Generic epoxy (repo anchor)", rho=1.15, wt=1.0,
        note="1 wt% equilibrium moisture at ~50% RH - the calibrated conservative default (Chiggiato arXiv:2006.07124)"),
    "h70e": dict(
        label="EPO-TEK H70E", rho=1.88, wt=0.25,
        note="thermally conductive die attach; WVR 0.25 (GSFC12127, range 0.15-0.28); rho from part SGs 1.5/2.5 at 1:1"),
    "353nd": dict(
        label="EPO-TEK 353ND", rho=1.18, wt=0.35,
        note="optics/fiber bonding; WVR 0.35 (GSFC29110, 0.34-0.36 across lots); rho from part SGs 1.2/1.02 at 10:1"),
    "2850ft": dict(
        label="Stycast 2850FT", rho=2.29, wt=0.10,
        note="silica-filled potting, the driest preset; WVR 0.05-0.15 (GSFC); rho 2.29 (Henkel TDS 12/2024)"),
    "2216": dict(
        label="Scotch-Weld 2216 gray", rho=1.30, wt=0.30,
        note="flexible structural, the wet comparison; WVR 0.23 TDS / 0.21-0.51 GSFC gray lots; rho 1.3 (3M TDS)"),
}

# Cold-shield black coatings. Thin Fickian film: L_eff = thickness (dries
# through its free face, metal-backed), reservoir = area x thickness x rho x wt%.
COATINGS = {
    "z306": dict(
        label="Aeroglaze Z306 paint", rho=1.12, wt=0.6, um=60.0,
        note="polyurethane flat black; TML 1.0/CVCM 0.02 (Lord DS3017), WVR 0.3-0.9 GSFC paint lots, median 0.6; "
             "dry-film rho computed from datasheet solids; ~28 um/coat max, 2-3 coats typical"),
    "acktar": dict(
        label="Acktar vacuum black", rho=1.8, wt=2.0, um=4.0,
        note="inorganic vacuum-deposited film 3-5 um; porous - physisorbs 1.2-3.8 wt% water at ambient (ESA ISME09), "
             "CVCM 0.00-0.01; tiny absolute reservoir, releases fast"),
    "bare": dict(
        label="Bare metal shield", rho=0.0, wt=0.0, um=0.0,
        note="no film reservoir - surface water on the metal is counted with the internal steel area"),
}

# Getter options: St707-class Zr-V-Fe alloy grams (representative sizes, not
# catalog part numbers - flagged). Dual ledger per gram: H2O ~2.4 torr.L/g
# surface-limited estimate (PSEC note), H2 ~170 torr.L/g bulk (Sandia).
# Floor 1e-7 torr while healthy (representative). This dual ledger is a
# documented improvement over dewar_vacuum_model's single capacity.
GETTER_CAP_W = 2.4       # torr.L per g, water (estimate)
GETTER_CAP_H = 170.0     # torr.L per g, H2 (Sandia St707)
GETTER_FLOOR = 1e-7      # torr
GETTERS = {
    "none": 0.0, "g025": 0.25, "g05": 0.5, "g1": 1.0, "g2": 2.0,
}

# Gas species for conduction: gamma, M (kg/mol), combined two-surface
# accommodation alpha_eff, continuum k (W/m/K) near the log-mean gap
# temperature (~190 K) - air/H2 from dewar_vacuum_model/gas.py, CH4 per
# dewar_life_materials.json ch4_gas_conduction (CRC; alpha representative).
SPECIES = {
    "air": dict(gamma=1.40, M=28.97e-3, alpha=0.9, k=0.0177),
    "h2":  dict(gamma=1.41, M=2.016e-3, alpha=0.4, k=0.125),
    "ch4": dict(gamma=1.31, M=16.043e-3, alpha=0.9, k=0.021),
}

DEFAULTS = dict(
    adhesive="generic", coating="z306", getter="g1",
    bake_c=85.0, bake_days=7.0, store_c=22.0,
    adh_v=0.25, adh_a=4.0,          # cm^3, cm^2 -> L_eff 0.625 mm
    shield_cm2=40.0, coat_um=60.0,  # one knob: coated area = cold gas/radiation area
    steel_cm2=300.0, vol_l=0.10,
    cold_k=80.0,                    # K, FPA / cold-space setpoint (80-150)
    target_yr=10.0,
    air_equiv=False, surface_on=True,
)

# time grids - SAME in the HTML twin
NT_CHART = 240           # chart grid, 1 day .. 30 yr, log-spaced
NT_LIFE = 500            # life-crossing grid, 60 s .. 100 yr
NT_LIFE_BISECT = 160     # reduced grid inside the required-bake bisection
NT_COOL = 20             # cooldown sample points along life


def logspace(lo, hi, n):
    a, b = math.log(lo), math.log(hi)
    return [math.exp(a + (b - a) * i / (n - 1)) for i in range(n)]


# ---------------- Fickian reservoirs (Crank ch. 4; outgassing.py mirror) ----
def slab_remaining_frac(X, nterms=80):
    """Remaining fraction of a one-face-exposed slab, X = D*t/L^2.
    f(X) = sum 8/(m pi)^2 exp(-(m pi/2)^2 X), m odd; normalized so f(0)=1."""
    f = norm = 0.0
    for n in range(nterms):
        m = 2 * n + 1
        coef = 8.0 / (m * math.pi) ** 2
        f += coef * math.exp(-((m * math.pi / 2.0) ** 2) * min(X, 700.0))
        norm += coef
    return min(max(f / norm, 0.0), 1.0)


def reservoir_released_torrL(mg0, L_eff, t_bake, T_bake, ts, T_store):
    """Cumulative torr.L released into the sealed volume at each storage time.
    Two-stage bake->storage is exact: X arguments add (Crank ch. 7,
    t' = int D dt). ts is a list; returns a list."""
    if mg0 <= 0.0 or L_eff <= 0.0:
        return [0.0] * len(ts)
    L2 = L_eff * L_eff
    Xb = d_coef(T_bake) * t_bake / L2
    fb = slab_remaining_frac(Xb)
    Ds = d_coef(T_store)
    return [mg0 * MG_H2O_TORRL * (fb - slab_remaining_frac(Xb + Ds * t / L2))
            for t in ts]


def reservoir_remaining_torrL(mg0, L_eff, t_bake, T_bake):
    if mg0 <= 0.0 or L_eff <= 0.0:
        return 0.0
    return mg0 * MG_H2O_TORRL * slab_remaining_frac(
        d_coef(T_bake) * t_bake / (L_eff * L_eff))


def adh_q1h_cm2():
    """Pre-depletion adhesive flux at 1 h, 85 C, per cm^2 (REQ-P4.3 anchor):
    q = c0 sqrt(D/(pi t)), c0 = 1 wt% x 1.15 g/cm^3 = 11.7 torr.L/cm^3."""
    c0 = 1.15 * 0.01 * 1e3 * MG_H2O_TORRL           # torr.L per cm^3
    return c0 * math.sqrt(d_coef(358.15) / (math.pi * 3600.0))


# ---------------- surface water (Redhead multi-energy) ----------------
def sw_energies():
    return [SW_E_LO + (SW_E_HI - SW_E_LO) * i / (SW_NE - 1) for i in range(SW_NE)]


def trapz_mean(vals):
    """Trapezoid mean over the uniform energy grid (equals trapz/(Ehi-Elo))."""
    s = 0.5 * (vals[0] + vals[-1]) + sum(vals[1:-1])
    return s / (SW_NE - 1)


def surface_released_torrL(area_cm2, t_bake, T_bake, ts, T_store):
    """Cumulative torr.L from the metal surfaces at each storage time:
    <theta_bake(E) * (1 - exp(-k_store(E) t))> over the energy window."""
    inv0 = SW_ML * ML_TORRL_PER_CM2 * area_cm2
    E = sw_energies()
    thb = [math.exp(-t_bake * SW_NU * math.exp(-e / (KB_EV * T_bake))) for e in E]
    ks = [SW_NU * math.exp(-e / (KB_EV * T_store)) for e in E]
    out = []
    for t in ts:
        out.append(inv0 * trapz_mean(
            [thb[i] * (1.0 - math.exp(-ks[i] * min(t, 1e30))) for i in range(SW_NE)]))
    return out


def surface_remaining_torrL(area_cm2, t_bake, T_bake):
    inv0 = SW_ML * ML_TORRL_PER_CM2 * area_cm2
    E = sw_energies()
    return inv0 * trapz_mean(
        [math.exp(-t_bake * SW_NU * math.exp(-e / (KB_EV * T_bake))) for e in E])


def surface_rate_torrL_s(area_cm2, t_s, T_K):
    """Instantaneous rate under pumping (the 1/t-law cross-check, REQ-P7.1)."""
    inv0 = SW_ML * ML_TORRL_PER_CM2 * area_cm2
    E = sw_energies()
    k = [SW_NU * math.exp(-e / (KB_EV * T_K)) for e in E]
    return inv0 * trapz_mean([k[i] * math.exp(-k[i] * t_s) for i in range(SW_NE)])


# ---------------- sealed pressure (sealed_life.py mirror) ----------------
def water_released_torrL(p, ts):
    """Total cumulative water (surface + adhesive + coating) at each storage
    time for parameter dict p (keys of DEFAULTS, temps in K, times in s)."""
    adh = ADHESIVES[p["adhesive"]]
    coat = COATINGS[p["coating"]]
    mg_adh = p["adh_v"] * adh["rho"] * (adh["wt"] / 100.0) * 1e3
    L_adh = p["adh_v"] / p["adh_a"]
    th_cm = p["coat_um"] * 1e-4
    mg_coat = p["shield_cm2"] * th_cm * coat["rho"] * (coat["wt"] / 100.0) * 1e3
    tb, Tb, Tst = p["bake_s"], p["bake_K"], p["store_K"]
    tot = reservoir_released_torrL(mg_adh, L_adh, tb, Tb, ts, Tst)
    for i, v in enumerate(reservoir_released_torrL(mg_coat, th_cm, tb, Tb, ts, Tst)):
        tot[i] += v
    if p["surface_on"]:
        for i, v in enumerate(surface_released_torrL(p["steel_cm2"], tb, Tb, ts, Tst)):
            tot[i] += v
    return tot


def pressures(p, ts):
    """Partial and total pressures [torr] on the storage-time grid ts.
    Returns dict of lists: w, h2, ch4, tot (no getter), get (with getter),
    plus the getter ledgers (torr.L consumed)."""
    V = p["vol_l"]
    Qh2 = Q_H2_CM2 * p["steel_cm2"]
    Qch4 = Q_CH4_CM2 * p["steel_cm2"]
    W = water_released_torrL(p, ts)
    g = GETTERS[p["getter"]]
    cap_w, cap_h = GETTER_CAP_W * g, GETTER_CAP_H * g
    out = dict(w=[], h2=[], ch4=[], tot=[], get=[], led_w=[], led_h=[])
    for i, t in enumerate(ts):
        pw, ph, pc = W[i] / V, Qh2 * t / V, Qch4 * t / V
        out["w"].append(pw)
        out["h2"].append(ph)
        out["ch4"].append(pc)
        out["tot"].append(pw + ph + pc)
        if g > 0.0:
            ov_w = max(0.0, W[i] - cap_w)
            ov_h = max(0.0, Qh2 * t - cap_h)
            # mirror of sealed_life.pressure_with_getter, dual-ledger form:
            # getterables sit at the floor, CH4 accumulates, overflow adds
            out["get"].append(max(GETTER_FLOOR, pc) + (ov_w + ov_h) / V)
            out["led_w"].append(min(W[i], cap_w))
            out["led_h"].append(min(Qh2 * t, cap_h))
        else:
            out["get"].append(pw + ph + pc)
            out["led_w"].append(0.0)
            out["led_h"].append(0.0)
    return out


def life_to_crit_s(p, gettered, nt=NT_LIFE):
    """Storage time to reach P_CRIT (first crossing, local linear interp -
    sealed_life.life_to_crit_s). None if not reached inside 100 yr."""
    ts = logspace(60.0, 100 * YEAR, nt)
    pr = pressures(p, ts)
    y = pr["get"] if gettered else pr["tot"]
    for i in range(len(ts)):
        if y[i] >= P_CRIT:
            if i == 0:
                return ts[0]
            f = (P_CRIT - y[i - 1]) / (y[i] - y[i - 1])
            return ts[i - 1] + f * (ts[i] - ts[i - 1])
    return None


def required_bake_days(p, gettered):
    """Bake duration at the current bake temperature for life >= target.
    Bisection on log t_bake in [0.05, 200] d (REVIEW.md: this inverse question
    is x2.5-determined, vs x25 for life at fixed bake). Returns
    (days | None, note): None with note 'unreachable' when even 200 d fails -
    then the binding mechanism is not water (H2 without a getter, CH4 with)."""
    tgt = p["target_yr"] * YEAR

    def life_at(days):
        q = dict(p)
        q["bake_s"] = days * DAY
        v = life_to_crit_s(q, gettered, nt=NT_LIFE_BISECT)
        return math.inf if v is None else v

    if life_at(200.0) < tgt:
        return None, "unreachable"
    if life_at(0.05) >= tgt:
        return 0.05, "no bake needed"
    lo, hi = math.log(0.05), math.log(200.0)
    for _ in range(40):
        mid = 0.5 * (lo + hi)
        if life_at(math.exp(mid)) >= tgt:
            hi = mid
        else:
            lo = mid
    return math.exp(hi), "ok"


# ---------------- gas conduction (gas.py mirror) ----------------
def lambda0(sp, T_gauge=T_ACCOUNT):
    """Free-molecular conduction coefficient, W m-2 Pa-1 K-1 (Corruccini):
    Lambda0 = (gamma+1)/(gamma-1) sqrt(R/(8 pi M T_gauge))."""
    s = SPECIES[sp]
    g = s["gamma"]
    return (g + 1.0) / (g - 1.0) * math.sqrt(
        R_GAS / (8.0 * math.pi * s["M"] * T_gauge))


def gas_flux_Wm2(P_torr, dT, sp):
    """Heat flux vs warm-gauge pressure, free-molecular bridged to the
    continuum plateau by the parallel sum (Sherman-type; gas.py)."""
    if dT <= 0.0 or P_torr <= 0.0:
        return 0.0
    s = SPECIES[sp]
    q_fm = s["alpha"] * lambda0(sp) * (P_torr * TORR_PA) * dT
    q_ct = s["k"] * dT / (GAP_MM * 1e-3)
    return 1.0 / (1.0 / q_fm + 1.0 / q_ct)


def heat_load_W(p, ph2, pch4, ptot, dT=None):
    """Cold-space gas load [W] for one life point. Species mode: H2 + CH4
    partials (water cryopumped by the cold shield - ice v.p. is 1e-10 torr at
    80 K and still only ~1e-6 at 150 K, Honig & Hook 1960, so the exclusion
    holds across the 80-150 K setpoint range). Air-equivalent mode: total warm
    pressure through the air coefficients - the classic textbook curve (12 mW
    at 1e-4 torr, 116 mW at 1e-3, at 80 K), which UNDERSTATES a CH4/H2-rich
    late-life mix (Lambda0 1.97/4.38 vs air 1.18) and overstates a
    water-dominated one."""
    A = p["shield_cm2"] * 1e-4
    dT = (T_SHELL - p["cold_k"]) if dT is None else dT
    if p["air_equiv"]:
        return gas_flux_Wm2(ptot, dT, "air") * A
    return (gas_flux_Wm2(ph2, dT, "h2") + gas_flux_Wm2(pch4, dT, "ch4")) * A


def species_partials_for_load(p, pr, i):
    """(p_h2, p_ch4, p_total_warm) at grid index i for the ACTIVE getter
    config. With a healthy getter the floor rides the H2 channel (the
    equilibrium-isotherm species; water sticks essentially irreversibly)."""
    g = GETTERS[p["getter"]]
    if g > 0.0:
        cap_h = GETTER_CAP_H * g
        ov_h = max(0.0, Q_H2_CM2 * p["steel_cm2"] * pr["_ts"][i] - cap_h) / p["vol_l"]
        return GETTER_FLOOR + ov_h, pr["ch4"][i], pr["get"][i]
    return pr["h2"][i], pr["ch4"][i], pr["tot"][i]


# ---------------- cooldown (cooldown.py mirror, stdlib RK4) ----------------
# Debye c_p(Cu) precomputed once: T grid 4..340 K x 400, inner integral
# 2000-point trapezoid - SAME discretization in the HTML twin.
_CP_T = [4.0 + (340.0 - 4.0) * i / 399 for i in range(400)]


def _debye_cp_kg(T):
    x_up = THETA_D_CU / T
    n = 2000
    s = 0.0
    for i in range(n):
        x0 = 1e-6 + (x_up - 1e-6) * i / (n - 1)
        ex = math.exp(x0)
        v = x0 ** 4 * ex / (ex - 1.0) ** 2
        s += v * (0.5 if (i == 0 or i == n - 1) else 1.0)
    integ = s * (x_up - 1e-6) / (n - 1)
    return 9.0 * R_GAS * (T / THETA_D_CU) ** 3 * integ / M_CU


_CP_V = [_debye_cp_kg(t) for t in _CP_T]


def cp_cu(T):
    if T <= _CP_T[0]:
        return _CP_V[0]
    if T >= _CP_T[-1]:
        return _CP_V[-1]
    i = int((T - _CP_T[0]) / (_CP_T[1] - _CP_T[0]))
    i = min(i, len(_CP_T) - 2)
    f = (T - _CP_T[i]) / (_CP_T[i + 1] - _CP_T[i])
    return _CP_V[i] + f * (_CP_V[i + 1] - _CP_V[i])


def q_lift_W(T):
    """Linear net-refrigeration between the 80 K / 300 K anchors."""
    return max(0.0, Q_LIFT_80 + (Q_LIFT_300 - Q_LIFT_80) / 220.0 * (T - 80.0))


def cooldown_minutes(p, ph2, pch4, ptot):
    """RK4 (dt = 2 s, cap 7200 s) on m c_p dT/dt = -(lift - loads); loads =
    radiation (eps_eff) + leads (G) + gas at the instantaneous dT with the
    partials frozen at this life point. Returns (minutes | None, stalled)."""
    A = p["shield_cm2"] * 1e-4
    m = M_CU_G * 1e-3
    T_set = p["cold_k"]

    def net(T):
        loads = (EPS_EFF * SIGMA_SB * A * (T_SHELL ** 4 - T ** 4)
                 + G_LEADS * (T_SHELL - T)
                 + heat_load_W(p, ph2, pch4, ptot, dT=T_SHELL - T))
        return q_lift_W(T) - loads

    def rhs(T):
        return -net(T) / (m * cp_cu(T))

    T, t, dt = T_SHELL, 0.0, 2.0
    while t < 7200.0:
        if net(T) < 1e-4:                 # stall: no margin left while warm
            return None, True
        k1 = rhs(T)
        k2 = rhs(T + 0.5 * dt * k1)
        k3 = rhs(T + 0.5 * dt * k2)
        k4 = rhs(T + dt * k3)
        Tn = T + dt / 6.0 * (k1 + 2 * k2 + 2 * k3 + k4)
        t += dt
        if Tn <= T_set:
            f = (T - T_set) / (T - Tn)    # linear crossing inside the step
            return (t - dt + f * dt) / 60.0, False
        T = Tn
    return None, True


# ---------------- full scenario ----------------
def prep(state):
    p = dict(state)
    p["bake_s"] = p["bake_days"] * DAY
    p["bake_K"] = p["bake_c"] + 273.15
    p["store_K"] = p["store_c"] + 273.15
    return p


def compute(state):
    """Everything the page shows, for one parameter set."""
    p = prep(state)
    ts = logspace(DAY, 30 * YEAR, NT_CHART)
    pr = pressures(p, ts)
    pr["_ts"] = ts

    heat_sp, heat_ae = [], []
    for i in range(NT_CHART):
        ph2, pch4, ptot = species_partials_for_load(p, pr, i)
        q = dict(p)
        q["air_equiv"] = False
        heat_sp.append(heat_load_W(q, ph2, pch4, ptot))
        q["air_equiv"] = True
        heat_ae.append(heat_load_W(q, ph2, pch4, ptot))

    tc = logspace(DAY, 30 * YEAR, NT_COOL)
    prc = pressures(p, tc)
    prc["_ts"] = tc
    cool_min, stalled = [], []
    for i in range(NT_COOL):
        ph2, pch4, ptot = species_partials_for_load(p, prc, i)
        mns, st = cooldown_minutes(p, ph2, pch4, ptot)
        cool_min.append(mns)
        stalled.append(st)
    stall_t = None
    for i in range(NT_COOL):
        if stalled[i]:
            stall_t = tc[i] if i == 0 else math.sqrt(tc[i - 1] * tc[i])
            break

    life_ng = life_to_crit_s(p, gettered=False)
    life_g = life_to_crit_s(p, gettered=True)
    req, req_note = required_bake_days(p, gettered=GETTERS[p["getter"]] > 0.0)

    tb, Tb = p["bake_s"], p["bake_K"]
    adh = ADHESIVES[p["adhesive"]]
    coat = COATINGS[p["coating"]]
    mg_adh = p["adh_v"] * adh["rho"] * (adh["wt"] / 100.0) * 1e3
    th_cm = p["coat_um"] * 1e-4
    mg_coat = p["shield_cm2"] * th_cm * coat["rho"] * (coat["wt"] / 100.0) * 1e3
    inv_adh = reservoir_remaining_torrL(mg_adh, p["adh_v"] / p["adh_a"], tb, Tb)
    inv_coat = reservoir_remaining_torrL(mg_coat, th_cm, tb, Tb)
    inv_surf = surface_remaining_torrL(p["steel_cm2"], tb, Tb) if p["surface_on"] else 0.0

    it = min(range(NT_CHART), key=lambda i: abs(ts[i] - p["target_yr"] * YEAR))
    W_t = water_released_torrL(p, [p["target_yr"] * YEAR])[0]
    ice_mg = W_t / MG_H2O_TORRL
    ice_um = ice_mg * 1e-3 / (RHO_ICE * FILTER_CM2) * 1e4

    g = GETTERS[p["getter"]]
    return dict(
        p=p, ts=ts, pr=pr, heat_sp=heat_sp, heat_ae=heat_ae,
        tc=tc, cool_min=cool_min, stalled=stalled, stall_t=stall_t,
        life_ng=life_ng, life_g=life_g, req_bake=req, req_note=req_note,
        inv_adh=inv_adh, inv_coat=inv_coat, inv_surf=inv_surf,
        mg_adh0=mg_adh, mg_coat0=mg_coat,
        heat_sp_t=heat_sp[it], heat_ae_t=heat_ae[it],
        ice_mg=ice_mg, ice_um=ice_um,
        led_w_t=(pr["led_w"][it] / (GETTER_CAP_W * g) if g else 0.0),
        led_h_t=(pr["led_h"][it] / (GETTER_CAP_H * g) if g else 0.0),
    )


def parity(state=None):
    """The numbers the HTML twin must reproduce to <= 0.5 % (REQ-U2)."""
    r = compute(state or dict(DEFAULTS))
    p, ts, pr = r["p"], r["ts"], r["pr"]

    def at(t_want, arr):
        i = min(range(len(ts)), key=lambda j: abs(ts[j] - t_want))
        return arr[i]

    dT = T_SHELL - T_COLD
    A = p["shield_cm2"] * 1e-4
    return {
        "lambda0_air": lambda0("air"),
        "lambda0_h2": lambda0("h2"),
        "lambda0_ch4": lambda0("ch4"),
        "q_air_1e4_mW": gas_flux_Wm2(1e-4, dT, "air") * A * 1e3,
        "q_air_1e3_mW": gas_flux_Wm2(1e-3, dT, "air") * A * 1e3,
        "adh_q1h": adh_q1h_cm2(),
        "cp_cu_300": cp_cu(300.0),
        "inv_surf": r["inv_surf"], "inv_adh": r["inv_adh"], "inv_coat": r["inv_coat"],
        "p_nog_1d": at(DAY, pr["tot"]),
        "p_nog_1yr": at(YEAR, pr["tot"]),
        "p_nog_10yr": at(10 * YEAR, pr["tot"]),
        "p_get_1yr": at(YEAR, pr["get"]),
        "p_get_10yr": at(10 * YEAR, pr["get"]),
        "life_ng_days": (r["life_ng"] or 0.0) / DAY,
        "life_g_years": (r["life_g"] or 0.0) / YEAR,
        "req_bake_days": r["req_bake"] or -1.0,
        "heat_sp_10yr_mW": r["heat_sp_t"] * 1e3,
        "heat_ae_10yr_mW": r["heat_ae_t"] * 1e3,
        "ice_10yr_um": r["ice_um"],
        "led_w_pct": r["led_w_t"] * 100.0,
        "led_h_pct": r["led_h_t"] * 100.0,
        "cool_1d_min": r["cool_min"][0] or -1.0,
        "cool_last_min": r["cool_min"][-1] or -1.0,
        "stall_year": (r["stall_t"] or 0.0) / YEAR,
    }


# ---------------- formatting ----------------
def fmt_time(s):
    if s is None:
        return "> 30 yr"
    if s < 3600:
        return f"{s/60:.3g} min"
    if s < 2 * DAY:
        return f"{s/3600:.3g} h"
    if s < 0.5 * YEAR:
        return f"{s/DAY:.3g} days"
    return f"{s/YEAR:.3g} yr"


def fmt_p(v):
    return f"{v:.3g}"


# ---------------- headless check ----------------
def check():
    ok = [0, 0]

    def expect(name, got, want, tol):
        good = abs(got - want) <= tol * abs(want)
        ok[0 if good else 1] += 1
        print(f"  [{'PASS' if good else 'FAIL'}] {name:<38} {got:.4g}  "
              f"(expect {want:.4g} +-{tol*100:.0f}%)")

    print("== materials (research/data/dewar_life_materials.json) ==")
    for k, a in ADHESIVES.items():
        print(f"  adhesive {a['label']:<28} rho {a['rho']:.2f}  water {a['wt']:.2f} wt%")
    for k, c in COATINGS.items():
        if c["rho"]:
            print(f"  coating  {c['label']:<28} rho {c['rho']:.2f}  water {c['wt']:.2f} wt%  "
                  f"typ. {c['um']:.0f} um")
    print(f"  getter   St707-class: {GETTER_CAP_W:.1f} torr.L/g water (est.), "
          f"{GETTER_CAP_H:.0f} torr.L/g H2, floor {GETTER_FLOOR:.0e} torr")

    print("\n== physics anchors ==")
    expect("Lambda0(air, 295 K) [W/m2/K/Pa]", lambda0("air"), 1.180, 0.02)
    expect("Lambda0(H2)", lambda0("h2"), 4.384, 0.02)
    expect("Lambda0(CH4)", lambda0("ch4"), 1.970, 0.02)
    dT = T_SHELL - T_COLD
    A0 = 40e-4
    expect("air load 40cm2/5mm @1e-4 torr [mW]",
           gas_flux_Wm2(1e-4, dT, "air") * A0 * 1e3, 12.0, 0.02)
    expect("air load @1e-3 torr [mW]",
           gas_flux_Wm2(1e-3, dT, "air") * A0 * 1e3, 116.0, 0.02)
    expect("adhesive q(1 h, 85 C) [torr.L/s/cm2]", adh_q1h_cm2(), 2.34e-5, 0.01)
    q1h = surface_rate_torrL_s(1.0, 3600.0, 295.0)
    expect("surface q(1 h, 22 C) vs 1/t law", q1h, 2.2e-9, 2.0)  # within x3
    expect("1 mg H2O [torr.L]", MG_H2O_TORRL, 1.02, 0.02)
    expect("c_p Cu(300 K) Debye [J/kg/K]", cp_cu(300.0), 368.0, 0.05)

    print("\n== defaults scenario ==")
    r = compute(dict(DEFAULTS))
    p = r["p"]
    print(f"  bake {p['bake_days']:g} d @ {p['bake_c']:g} C, store {p['store_c']:g} C; "
          f"adhesive {ADHESIVES[p['adhesive']]['label']} {p['adh_v']:g} cm3 / {p['adh_a']:g} cm2; "
          f"coating {COATINGS[p['coating']]['label']} {p['shield_cm2']:g} cm2 x {p['coat_um']:g} um; "
          f"getter {GETTERS[p['getter']]:g} g")
    print(f"  water at pinch-off: surface {fmt_p(r['inv_surf'])} + adhesive "
          f"{fmt_p(r['inv_adh'])} + coating {fmt_p(r['inv_coat'])} torr.L "
          f"(reservoirs before bake: adh {r['mg_adh0']*MG_H2O_TORRL:.3g}, "
          f"coat {r['mg_coat0']*MG_H2O_TORRL:.3g} torr.L)")
    print(f"  life without getter  {fmt_time(r['life_ng'])} (H2 owns it: "
          f"{Q_H2_CM2*p['steel_cm2']:.2g} torr.L/s into {p['vol_l']:g} L)")
    print(f"  life with getter     {fmt_time(r['life_g'])} (CH4 ceiling "
          f"{P_CRIT*p['vol_l']/(Q_CH4_CM2*p['steel_cm2'])/YEAR:.3g} yr)")
    rb = "-" if r["req_bake"] is None else f"{r['req_bake']:.3g} d"
    print(f"  required bake for {p['target_yr']:g} yr: {rb} [{r['req_note']}]")
    print(f"  heat load at {p['target_yr']:g} yr: species {r['heat_sp_t']*1e3:.3g} mW, "
          f"air-equivalent {r['heat_ae_t']*1e3:.3g} mW")
    print(f"  ice budget at {p['target_yr']:g} yr: {r['ice_mg']:.3g} mg -> "
          f"{r['ice_um']:.3g} um on {FILTER_CM2:g} cm2 (0.1 um measurable / 1 um severe)")
    print(f"  getter ledger at {p['target_yr']:g} yr: water {r['led_w_t']*100:.1f} %, "
          f"H2 {r['led_h_t']*100:.1f} %")
    c0 = r["cool_min"][0]
    print(f"  cooldown at pinch-off {('stalled' if c0 is None else f'{c0:.3g} min')}, "
          f"stall {'never (<=30 yr)' if r['stall_t'] is None else fmt_time(r['stall_t'])}")

    expect("life without getter [days]", (r["life_ng"] or 0) / DAY, 3.85, 0.10)
    expect("life with getter [yr] (CH4 ceiling)", (r["life_g"] or 0) / YEAR, 10.6, 0.05)
    expect("Z306 reservoir 40 cm2 x 60 um [torr.L]",
           r["mg_coat0"] * MG_H2O_TORRL, 1.64, 0.05)

    print("\n== cooldown anchors (air-equivalent mode, 80 K setpoint) ==")
    q = prep(dict(DEFAULTS, air_equiv=True))
    m1, s1 = cooldown_minutes(q, 0.0, 0.0, 1e-6)
    expect("15 g @ 1e-6 torr [min]", m1 or 0.0, 12.1, 0.05)
    m2, s2 = cooldown_minutes(q, 0.0, 0.0, 1e-2)
    print(f"  [{'PASS' if s2 else 'FAIL'}] stall at 1e-2 torr"
          f"{'' if s2 else f'  (cooled in {m2:.3g} min)'}")
    ok[0 if s2 else 1] += 1

    print("\n== HOT-detector setpoint (cold space at 150 K) ==")
    rh = compute(dict(DEFAULTS, cold_k=150.0))
    print(f"  heat load at {DEFAULTS['target_yr']:g} yr: species "
          f"{rh['heat_sp_t']*1e3:.3g} mW (vs {r['heat_sp_t']*1e3:.3g} at 80 K - dT 143/213)")
    ch = rh["cool_min"][0]
    print(f"  cooldown at pinch-off {('stalled' if ch is None else f'{ch:.3g} min')} "
          f"(more lift, less enthalpy); stall "
          f"{'never (<=30 yr)' if rh['stall_t'] is None else fmt_time(rh['stall_t'])}")
    good = (rh["heat_sp_t"] < r["heat_sp_t"]) and (ch is not None and c0 is not None and ch < c0)
    print(f"  [{'PASS' if good else 'FAIL'}] 150 K setpoint lowers load and cooldown time")
    ok[0 if good else 1] += 1

    print(f"\n{ok[0]} pass, {ok[1]} fail")
    print("\nPARITY " + json.dumps({k: (round(v, 10) if isinstance(v, float) else v)
                                    for k, v in sorted(parity().items())}))
    return ok[1] == 0


# ---------------- static figure (optional) ----------------
def interactive():
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("matplotlib not available - run with --check, or open "
              "dewar_vacuum_life.html for the interactive model")
        return
    r = compute(dict(DEFAULTS))
    ts_yr = [t / YEAR for t in r["ts"]]
    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(15, 4.6))
    a1.loglog(ts_yr, r["pr"]["w"], label="H2O")
    a1.loglog(ts_yr, r["pr"]["h2"], label="H2")
    a1.loglog(ts_yr, r["pr"]["ch4"], label="CH4")
    a1.loglog(ts_yr, r["pr"]["tot"], "k", label="total, no getter")
    a1.loglog(ts_yr, r["pr"]["get"], "k--", label="with getter")
    a1.axhline(P_CRIT, ls=":", lw=1)
    a1.set_xlabel("storage (yr)"); a1.set_ylabel("warm pressure (torr)")
    a1.legend(fontsize=8); a1.set_title("sealed pressure")
    a2.loglog(ts_yr, [max(v, 1e-9) * 1e3 for v in r["heat_sp"]], label="species-resolved")
    a2.loglog(ts_yr, [max(v, 1e-9) * 1e3 for v in r["heat_ae"]], "--", label="air-equivalent")
    a2.set_xlabel("storage (yr)"); a2.set_ylabel("cold-space gas load (mW)")
    a2.legend(fontsize=8); a2.set_title("heat load when operated")
    tc_yr = [t / YEAR for t in r["tc"]]
    a3.semilogx(tc_yr, [m if m is not None else float("nan") for m in r["cool_min"]])
    a3.set_xlabel("storage (yr)"); a3.set_ylabel("cooldown (min)")
    a3.set_title("cooldown vs life")
    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(0 if check() else 1)
    else:
        interactive()
