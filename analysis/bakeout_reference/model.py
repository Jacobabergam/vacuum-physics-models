#!/usr/bin/env python3
"""
Dewar bakeout / vacuum-life model for a sealed IR detector dewar (IDCA class).
Physics:
  1. Free-molecular gas conduction (Corruccini/Kennard form) -> required vacuum.
  2. Surface water desorption: first-order kinetics over a distribution of
     binding energies (Redhead-type multi-energy model) -> 1/t law, bake T-t equivalence.
  3. Polymer (epoxy/PCB) water reservoir: Fickian slab diffusion, Arrhenius D(T).
  4. Fixed H2 (and CH4) outgassing baselines for baked stainless steel.
  5. Sealed-volume pressure accumulation after pinch-off; getter as capacity-limited pump.
All representative parameters are collected in PARAMS and printed.
Units: torr, liter, cm, s, eV unless noted. SI given in printout where useful.
"""
import numpy as np

kB_eV = 8.617333e-5      # eV/K
R = 8.314462             # J/mol/K
TORR = 133.322           # Pa
T_ref = 295.0            # K reference for gas accounting

def torrL_molecules(T=T_ref):
    """molecules per torr*liter at temperature T"""
    return TORR * 1e-3 / (1.380649e-23 * T)

ML_torrL_per_cm2 = 1e15 / torrL_molecules()   # 1 monolayer (1e15 /cm^2) in torr*L/cm^2

# ----------------------------------------------------------------------------
# 1. FREE-MOLECULAR CONDUCTION
# ----------------------------------------------------------------------------
def Lambda0(gamma, M, Tg=T_ref):
    """Free-molecular conduction coefficient, W m^-2 Pa^-1 K^-1
    q = alpha * Lambda0 * P[Pa] * (T2-T1).  Corruccini (1959) / Kennard form."""
    return (gamma + 1.0) / (gamma - 1.0) * np.sqrt(R / (8.0 * np.pi * M * Tg))

GASES = {
    #        gamma   M kg/mol  alpha_eff  k_cont W/m/K at ~190K (representative)
    'air/N2': (1.40, 0.02897, 0.9, 0.0177),
    'H2':     (1.41, 0.002016, 0.4, 0.125),
    'He':     (1.667, 0.004003, 0.31, 0.11),
}

# Geometry (representative tactical IDCA)
A_cold = 40e-4    # m^2  cold-shield + cold-finger lateral area (40 cm^2)
gap    = 5e-3     # m    shell-to-shield gap
T_hot, T_cold = 293.0, 80.0

def gas_load_W(P_torr, gas):
    """total gas-conduction load [W] vs internal pressure, fm-continuum bridge"""
    g, M, a, k = GASES[gas]
    P = np.asarray(P_torr) * TORR
    q_fm = a * Lambda0(g, M) * P * (T_hot - T_cold)          # W/m^2
    q_ct = k * (T_hot - T_cold) / gap                        # W/m^2 (plateau)
    q = 1.0 / (1.0/np.maximum(q_fm, 1e-30) + 1.0/q_ct)       # Sherman-type bridge
    return q * A_cold

# ----------------------------------------------------------------------------
# 2. SURFACE WATER (multi-energy first-order desorption)
# ----------------------------------------------------------------------------
NU = 1e13                          # s^-1 attempt frequency (Redhead)
E_LO, E_HI = 0.75, 1.15            # eV binding-energy window, water on oxidized metal
NE = 4000
E = np.linspace(E_LO, E_HI, NE)
A_int = 300.0                      # cm^2 internal wetted metal area
N_ML = 3.0                         # monolayer-equivalents adsorbed after air exposure
I_SURF0 = N_ML * ML_torrL_per_cm2 * A_int   # torr*L initial surface inventory

def k_des(T):
    return NU * np.exp(-E / (kB_eV * T))

def surf_remaining_frac(t_bake, T_bake):
    """fraction of initial surface inventory remaining after bake"""
    theta = np.exp(-t_bake * k_des(T_bake))
    return np.trapezoid(theta, E) / (E_HI - E_LO)

def surf_released_after_seal(t_bake, T_bake, t_store, T_store=T_ref):
    """torr*L released into sealed volume at storage temp after bake (vector over t_store)"""
    theta_b = np.exp(-t_bake * k_des(T_bake))                 # (NE,)
    ks = k_des(T_store)
    rel = [np.trapezoid(theta_b * (1 - np.exp(-t * ks)), E) / (E_HI - E_LO)
           for t in np.atleast_1d(t_store)]
    return I_SURF0 * np.array(rel)

# ----------------------------------------------------------------------------
# 3. POLYMER WATER (Fickian slab, two thickness populations)
# ----------------------------------------------------------------------------
E_D  = 0.45          # eV activation energy for water diffusion in epoxy
D295 = 2e-9          # cm^2/s at 295 K (epoxy-class)
D0   = D295 / np.exp(-E_D / (kB_eV * 295.0))
M_POLY   = 0.5       # g epoxy/PCB-class organics inside dewar
C_W      = 0.01      # initial water mass fraction (1 wt%, ~50% RH storage)
POPS = [(0.6, 0.03), (0.4, 0.10)]   # (mass fraction, half-thickness cm): 0.3 mm bonds, 1 mm potting
M_W0 = M_POLY * C_W * 1e3           # mg water total;  1 mg H2O ~= 1.02 torr*L at 295 K
MG_TO_TORRL = 1e-3/18.015*6.02214e23/torrL_molecules()

def D_of(T):
    return D0 * np.exp(-E_D / (kB_eV * T))

def slab_frac(Dt_over_L2, nterms=60):
    """remaining fraction for slab of half-thickness L drying from both faces"""
    x = np.asarray(Dt_over_L2, dtype=float)
    f = np.zeros_like(x)
    for n in range(nterms):
        m = 2*n + 1
        f += 8.0/(m*np.pi)**2 * np.exp(-(m*np.pi/2.0)**2 * x)
    return np.minimum(f, 1.0)

def poly_remaining_mg(t_bake, T_bake):
    out = 0.0
    for w, L in POPS:
        out += M_W0 * w * slab_frac(D_of(T_bake)*t_bake/L**2)
    return out

def poly_released_after_seal(t_bake, T_bake, t_store, T_store=T_ref):
    """mg released into sealed volume after pinch-off.
    Exact two-stage Fickian solution: the eigenmode decay argument is additive,
    so remaining fraction depends only on (D_bake*t_bake + D_store*t_store)/L^2.
    Boundary treated as near-perfect sink (sealed water partial pressure stays far
    below the polymer's equilibrium sorption isotherm at these magnitudes)."""
    t = np.atleast_1d(t_store).astype(float)
    rel = np.zeros_like(t)
    for w, L in POPS:
        Xb = D_of(T_bake) * t_bake / L**2
        rel += M_W0 * w * (slab_frac(Xb) - slab_frac(Xb + D_of(T_store)*t/L**2))
    return rel

# ----------------------------------------------------------------------------
# 4. FIXED GAS BASELINES (representative, post-85-100C bake)
# ----------------------------------------------------------------------------
Q_H2  = 1e-12 * A_int    # torr*L/s  (range 1e-13..3e-12 per cm^2)
Q_CH4 = 1e-15 * A_int    # torr*L/s  non-getterable
V_FREE = 0.10            # liter free volume
P_CRIT = 1e-3            # torr warm end-of-life criterion

def sealed_pressure(t_bake, T_bake, t_store):
    """total warm pressure [torr] vs storage time (no getter)"""
    t = np.atleast_1d(t_store).astype(float)
    p_w = (surf_released_after_seal(t_bake, T_bake, t)
           + poly_released_after_seal(t_bake, T_bake, t) * MG_TO_TORRL) / V_FREE
    p_fix = (Q_H2 + Q_CH4) * t / V_FREE
    return p_w + p_fix, p_w

def water_life(t_bake, T_bake, span=(60.0, 3.15e9)):
    """storage time for WATER partial pressure alone to reach P_CRIT (np.inf if never)"""
    tg = np.logspace(np.log10(span[0]), np.log10(span[1]), 400)
    _, pw = sealed_pressure(t_bake, T_bake, tg)
    if pw[-1] < P_CRIT:
        return np.inf
    return np.interp(P_CRIT, pw, tg)

# ----------------------------------------------------------------------------
# PRINT KEY NUMBERS
# ----------------------------------------------------------------------------
if __name__ == '__main__':
    day = 86400.0
    yr = 3.156e7
    print("=== conversions ===")
    print(f"molecules per torr*L at 295K: {torrL_molecules():.3e}")
    print(f"1 monolayer H2O = {ML_torrL_per_cm2:.3e} torr*L/cm^2 ; {A_int:.0f} cm^2 x {N_ML} ML = {I_SURF0:.3e} torr*L")
    print(f"1 mg H2O = {MG_TO_TORRL:.3f} torr*L at 295 K; polymer water inventory = {M_W0:.1f} mg")
    print("\n=== free-molecular coefficients (W m^-2 Pa^-1 K^-1 at 295K gauge) ===")
    for gname,(g,M,a,k) in GASES.items():
        print(f"  {gname:6s} Lambda0={Lambda0(g,M):.3f}  alpha_eff={a}  -> q/PdT={a*Lambda0(g,M):.3f}")
    print("\n=== gas-conduction load, representative geometry (A=40cm^2, d=5mm, 293->80K) ===")
    for P in [1e-5, 1e-4, 1e-3, 1e-2, 1e-1, 1.0]:
        row = "  P={:8.0e} torr: ".format(P)
        for gname in GASES:
            row += f"{gname}={gas_load_W(P,gname)*1e3:8.2f} mW  "
        print(row)
    lam_air_mm = 6.6e-3/ (1e-3*TORR) # mean free path mm at 1 mtorr... (6.6e-3 Pa*m /P)
    print(f"  mean free path air ~ 6.6e-3/P[Pa] m -> at 1e-3 torr: {6.6e-3/(1e-3*TORR)*1e3:.0f} mm (vs gap {gap*1e3:.0f} mm)")

    print("\n=== bake erosion front E* = kB*T*ln(nu*t) ===")
    for TC, tb in [(22,10*yr),(22,day),(60,7*day),(60,14*day),(85,day),(85,7*day),(85,14*day),(100,3*day),(125,2*day)]:
        T = TC+273.15
        print(f"  T={TC:5.0f}C t={tb/day:7.1f}d -> E* = {kB_eV*T*np.log(NU*tb):.3f} eV")

    print("\n=== polymer drying time constants tau1 = 4L^2/(pi^2 D) ===")
    for TC in [22,60,85,100,125]:
        T=TC+273.15
        taus = [4*L**2/(np.pi**2*D_of(T))/day for _,L in POPS]
        print(f"  {TC:4d}C: D={D_of(T):.2e} cm^2/s  tau1 = {taus[0]:.2f} d (0.3mm), {taus[1]:.2f} d (1mm)")

    print("\n=== remaining extractable water after bake at 85C ===")
    for tb_d in [0.25,1,3,7,14,28]:
        s = surf_remaining_frac(tb_d*day, 358.15)*I_SURF0
        p = poly_remaining_mg(tb_d*day, 358.15)
        print(f"  {tb_d:5.2f} d: surface {s:.2e} torr*L, polymer {p*1e3:8.3f} ug ({p*MG_TO_TORRL:.2e} torr*L)")

    print("\n=== sealed storage: time for water partial pressure to hit 1e-3 torr ===")
    for TC in [60, 85, 100, 125]:
        for tb_d in [0.5, 1, 2, 3, 5, 7, 10, 14, 21, 28]:
            wl = water_life(tb_d*day, TC+273.15)
            s = ("never" if np.isinf(wl) else
                 (f"{wl/day:7.1f} days" if wl < 120*day else f"{wl/yr:7.2f} years"))
            print(f"  bake {TC:3d}C x {tb_d:5.1f} d -> water-only life: {s}")
        print()

    print("\n=== fixed-gas ceilings (no getter), V=0.1 L ===")
    print(f"  H2  : dP/dt = {Q_H2/V_FREE:.2e} torr/s -> 1e-3 torr in {P_CRIT/(Q_H2/V_FREE)/day:.1f} days")
    print(f"  CH4 : dP/dt = {Q_CH4/V_FREE:.2e} torr/s -> 1e-3 torr in {P_CRIT/(Q_CH4/V_FREE)/yr:.1f} years (getter does NOT pump CH4)")
    print(f"  pinch-off tube conductance (d=4mm,L=5cm, H2O): {12.1*0.4**3/5*np.sqrt(28.97/18.015):.3f} L/s")
