#!/usr/bin/env python3
"""Bottleneck-limited pumpdown: viscous vs. molecular flow.

Edwards nXDS10iC dry scroll pump -> small manifold (V1) -> bottleneck tube
(d x L) -> chamber (V2).

Shows two things at once:
  * the tube conductance collapsing from viscous (C ~ d^4 * P / L, huge near
    atmosphere) to molecular (C ~ d^3 / L, fixed, tiny), so the bottleneck
    barely matters at high pressure and dominates as the system gets thin;
  * the pump not offering a constant speed either — a scroll pump holds its
    peak 3.17 L/s down to ~0.1 Torr, then rolls off to zero at ultimate as
    back-leakage past the tip seals overtakes the swept volume.

Every run starts at 760 Torr. Air at 20 C. Units: cm, L, s, Torr.

Run interactively:   python3 bottleneck_pumpdown.py
Numeric self-check:  python3 bottleneck_pumpdown.py --check
"""

import math
import sys

# ---------------- physics ----------------
P_ATM = 760.0    # every run starts at atmosphere — not a parameter
LAM = 5.0e-3     # mean-free-path * pressure, cm*Torr (air, 20 C)
TARGET = 1e-6    # high-vacuum target for the timing readout, Torr

# ================= the pump set =========================================
# ROUGHING PUMPS are positive displacement. They sweep a fixed volume per
# revolution, but back-leakage across the seals grows as the inlet falls until
# it cancels the swept volume - that is the ultimate:
#     S(P) = S_peak * (1 - Pu/P)
# flat from atmosphere until roughly a decade above ultimate, then a cliff.
#
# The TURBO is not displacement at all. Its blades throw molecules downstream,
# so speed is a capture number, flat wherever flow is molecular. What bends its
# curve is throughput: rotor and drag stage can only shift so much gas, so above
# Pmax = Qmax/S_rated it is throughput-limited and S falls as Qmax/P. It also
# cannot run alone - its exhaust must stay below a critical backing pressure,
# which is the roughing pump's job and is checked explicitly.
MBAR = 0.7500617          # Torr per mbar
SCCM = 0.0126656          # Torr*L/s per sccm

ROUGHERS = {
    "nxds10ic": dict(
        model="nXDS10iC", make="Edwards", kind="dry scroll",
        Speak=11.4 / 3.6,        # L/s - 11.4 m3/h (6.7 cfm) peak pumping speed
        disp=12.7 / 3.6,         # L/s - 12.7 m3/h (7.5 cfm) swept displacement
        rpm=1800,
        PuGB0=7e-3 * MBAR,       # Torr, ultimate, gas ballast closed (5.25e-3)
        PuGB1=4e-2 * MBAR,       # Torr, ultimate, gas ballast open   (3.00e-2)
    ),
    "acp15": dict(
        model="ACP 15", make="Adixen/Pfeiffer", kind="multi-stage Roots",
        Speak=15 / 3.6,          # L/s - 15 m3/h (8.2 cfm) nominal
        disp=15 / 3.6,
        rpm=None,
        PuGB0=5e-2 * MBAR,       # Torr, ultimate 37.5 mTorr (5e-2 mbar)
        PuGB1=None,              # no published ballast-open figure
    ),
}

TURBOS = {
    "next300d": dict(
        model="nEXT300D", make="Edwards", kind="compound turbo + drag stage",
        Sn2=300.0, She=340.0, Sh2=280.0,      # L/s
        Qmax=115 * SCCM,                      # Torr*L/s - 115 sccm, forced air
        QmaxWater=95 * SCCM,                  # Torr*L/s - 95 sccm, water cooled
        Pbackmax=9.5 * MBAR,                  # Torr - critical backing, N2 (7.13)
        Pu=6e-8 * MBAR,                       # Torr, ultimate on a dry backing pump
        rpm=60000,
    ),
}

DEF_RP, DEF_TP = "nxds10ic", "next300d"


def p_ult(rp, gb=False):
    """The selected rougher's ultimate, honouring gas ballast where published."""
    R = ROUGHERS[rp]
    return R["PuGB1"] if (gb and R["PuGB1"] is not None) else R["PuGB0"]


def s_rough(P, rp, gb=False):
    """Roughing-pump speed at its own inlet. One curve for both species - a
    displacement pump sweeps whatever is in front of it."""
    return max(0.0, ROUGHERS[rp]["Speak"] * (1 - p_ult(rp, gb) / max(P, 1e-12)))


def s_turbo(Pa, Pw, tp):
    """Turbo capture speeds for (air, water) plus the throttle factor.

    The throughput ceiling is a rotor/drag limit shared by everything in the
    gas, so it throttles both species alike. The ultimate is left out of S and
    enters as a back-leak in the integrator, so this stays the pump's real speed
    rather than collapsing to zero at base pressure.
    """
    T = TURBOS[tp]
    a0 = w0 = T["Sn2"]            # turbos pump H2O at about their N2 speed
    Q = a0 * Pa + w0 * Pw
    k = T["Qmax"] / Q if Q > T["Qmax"] else 1.0
    return a0 * k, w0 * k, k


def foreline(Q, rp, gb=False):
    """Foreline pressure: the rougher must swallow the turbo's throughput, and
    settles where its own speed curve delivers exactly that. Bisected because
    s_rough itself depends on pressure. None if the rougher cannot take it."""
    if Q <= 0:
        return p_ult(rp, gb)
    lo, hi = p_ult(rp, gb) * 1.0001, 800.0
    if s_rough(hi, rp, gb) * hi < Q:
        return None
    for _ in range(60):
        mid = math.sqrt(lo * hi)
        if s_rough(mid, rp, gb) * mid < Q:
            lo = mid
        else:
            hi = mid
    return math.sqrt(lo * hi)


def pump_speeds(crossed, Pa, Pw, rp, tp, gb=False):
    """Speed offered to the manifold now, whichever pump is valved in."""
    if crossed:
        sa, sw, _ = s_turbo(Pa, Pw, tp)
        return sa, sw
    s = s_rough(Pa + Pw, rp, gb)
    return s, s


def cross_now(P2tot, P1tot, Px, rp, gb=False):
    """Standard practice is to cross over on the chamber gauge; the second
    clause is the escape hatch - once the rougher sits at its own ultimate it
    will never get you lower, so you cross over anyway."""
    return P2tot <= Px or P1tot <= p_ult(rp, gb) * 1.2


def mfp(P):
    return LAM / P                                    # cm


def cond_mol(d, L):
    return 12.1 * d**3 / (L + 1.333 * d)              # L/s, end-corrected tube


def cond_vis(d, L, Pavg):
    return 180.0 * d**4 / L * Pavg                    # L/s, Poiseuille (Torr)


def cond(d, L, Pavg):
    return cond_vis(d, L, Pavg) + cond_mol(d, L)      # Knudsen-interp approximation


FW = math.sqrt(29.0 / 18.0)   # molecular-speed factor for H2O (M=18) vs air (M=29)
OG_A = 20.0                   # adhesive area, cm^2
OG_Q1H = 5e-5                 # H2O outgassing rate at 85 C after 1 h, Torr*L/s/cm^2


def q_og(t):
    return OG_A * OG_Q1H * 3600.0 / max(t, 60.0)      # total throughput, ~1/t desorption decay


def be_step(P1, P2, C, Q, S, Pu, V1, V2, dt):
    """One backward-Euler step for one gas species.

    S = pump speed for this species over the step; Pu = that pump's ultimate as
    a back-leak; Q = source into the chamber. Pu is 0 for the roughers because
    their ultimate already lives inside S (back-leakage past the seals is a real
    loss of swept volume); for the turbo it is a genuine back-leak through the
    blade stack.
    """
    a11 = 1 + dt * (C + S) / V1
    a12 = -dt * C / V1
    a21 = -dt * C / V2
    a22 = 1 + dt * C / V2
    b1 = P1 + dt * S * Pu / V1
    b2 = P2 + dt * Q / V2
    det = a11 * a22 - a12 * a21
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def simulate(d, L, V1, V2, Px=0.1, rp=DEF_RP, tp=DEF_TP, gb=False, og=False):
    """Two-volume, two-species (air + outgassed H2O) pumpdown, backward Euler.

    Rougher on the manifold to crossover, then the turbo - with the rougher
    moving to the foreline to back it.
    """
    P1a = P2a = P_ATM
    P1w = P2w = 0.0
    t, dt = 0.0, 1e-7
    crossed, t_x, s_x, fore_max = False, None, 0.0, 0.0
    T, A1, A2, W1, W2, SP, FL = [], [], [], [], [], [], []
    Tb = TURBOS[tp]

    def rec(s, f):
        T.append(max(t, 1e-7))
        A1.append(P1a + P1w); A2.append(P2a + P2w)
        W1.append(max(P1w, 1e-12)); W2.append(max(P2w, 1e-12))
        SP.append(max(s, 1e-6)); FL.append(1e-12 if f is None else max(f, 1e-12))

    rec(s_rough(P_ATM, rp, gb), None)
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e5
    while P2a + P2w > Tb["Pu"] * 1.02 and t < t_max and steps < 60000:
        steps += 1
        if not crossed and cross_now(P2a + P2w, P1a + P1w, Px, rp, gb):
            crossed = True
            t_x = max(t, 1e-7)
            s_x = s_turbo(P1a, P1w, tp)[0]
        cv = cond_vis(d, L, 0.5 * ((P1a + P1w) + (P2a + P2w)))
        cm = cond_mol(d, L)
        Q = q_og(t) if og else 0.0
        Sa, Sw = pump_speeds(crossed, P1a, P1w, rp, tp, gb)
        Pua = Tb["Pu"] if crossed else 0.0
        fore = None
        if crossed:
            fore = foreline(Sa * P1a + Sw * P1w, rp, gb)
            if fore is not None and fore > fore_max:
                fore_max = fore
        n1a, n2a = be_step(P1a, P2a, cv + cm, 0.0, Sa, Pua, V1, V2, dt)
        n1w, n2w = be_step(P1w, P2w, cv + cm * FW, Q, Sw, 0.0, V1, V2, dt)
        rel = max(abs(n1a + n1w - (P1a + P1w)) / max(P1a + P1w, 1e-10),
                  abs(n2a + n2w - (P2a + P2w)) / max(P2a + P2w, 1e-10))
        if rel > 0.25 and dt > 1e-8:
            dt *= 0.5
            continue
        t += dt
        P1a, P2a, P1w, P2w = n1a, n2a, n1w, n2w
        if t >= last_rec * 1.05:
            rec(Sa, fore)
            last_rec = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    rec(pump_speeds(crossed, P1a, P1w, rp, tp, gb)[0], None)
    return {"T": T, "P1": A1, "P2": A2, "W1": W1, "W2": W2, "S": SP, "F": FL,
            "t_x": t_x, "s_x": s_x, "fore_max": fore_max}


def simulate_ideal(V1, V2, Px=0.1, rp=DEF_RP, tp=DEF_TP, gb=False, og=False):
    """The same pump set bolted straight onto one lumped volume - no bottleneck."""
    V = V1 + V2
    Tb = TURBOS[tp]
    Pa, Pw = P_ATM, 0.0
    t, dt, crossed = 0.0, 1e-7, False
    X, Y = [], []

    def rec():
        X.append(max(t, 1e-7)); Y.append(max(Pa + Pw, 1e-12))

    rec()
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e5
    while Pa + Pw > Tb["Pu"] * 1.02 and t < t_max and steps < 60000:
        steps += 1
        if not crossed and cross_now(Pa + Pw, Pa + Pw, Px, rp, gb):
            crossed = True
        Sa, Sw = pump_speeds(crossed, Pa, Pw, rp, tp, gb)
        Pua = Tb["Pu"] if crossed else 0.0
        Q = q_og(t) if og else 0.0
        na = (Pa + dt * Sa * Pua / V) / (1 + dt * Sa / V)
        nw = (Pw + dt * Q / V) / (1 + dt * Sw / V)
        if abs(na + nw - (Pa + Pw)) / max(Pa + Pw, 1e-10) > 0.25 and dt > 1e-8:
            dt *= 0.5
            continue
        t += dt
        Pa, Pw = na, nw
        if t >= last_rec * 1.05:
            rec()
            last_rec = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    rec()
    return X, Y


def time_to_reach(T, P, tgt):
    for i in range(1, len(T)):
        if P[i] <= tgt:
            f = (math.log(tgt) - math.log(P[i - 1])) / (math.log(P[i]) - math.log(P[i - 1]))
            return math.exp(math.log(T[i - 1]) + f * (math.log(T[i]) - math.log(T[i - 1])))
    return None


def fmt_time(s):
    if s is None:
        return "n/a"
    if s < 1e-3:
        return f"{s*1e6:.0f} us"
    if s < 1:
        return f"{s*1e3:.0f} ms"
    if s < 120:
        return f"{s:.3g} s"
    if s < 7200:
        return f"{s/60:.3g} min"
    if s < 172800:
        return f"{s/3600:.3g} h"
    return f"{s/86400:.3g} days"


# ---------------- headless check ----------------
def check():
    d, L, V1, V2, Px = 1.0, 10.0, 2.0, 100.0, 0.1
    tp = DEF_TP
    Tb = TURBOS[tp]

    print("pump set - speed is read off each pump's own curve, never typed in")
    for k, R in ROUGHERS.items():
        print(f"  rough {R['make']} {R['model']:<9} {R['kind']:<19} "
              f"peak {R['Speak']:.2f} L/s ({R['Speak']*3.6:.1f} m3/h)  "
              f"ultimate {R['PuGB0']:.3g} Torr")
    print(f"  turbo {Tb['make']} {Tb['model']}  {Tb['Sn2']:.0f} L/s N2, "
          f"Qmax {Tb['Qmax']/SCCM:.0f} sccm = {Tb['Qmax']:.3g} Torr*L/s")
    print(f"        full speed only below Pmax = Qmax/S = "
          f"{Tb['Qmax']/Tb['Sn2']:.3g} Torr")
    print(f"        critical backing {Tb['Pbackmax']:.3g} Torr, "
          f"ultimate {Tb['Pu']:.3g} Torr")

    print("\nspeed vs pressure, as the model reads it:")
    print(f"  {'P (Torr)':>10}  {'nXDS10iC':>10}  {'ACP 15':>10}  {'nEXT300D':>10}")
    for P in (760, 1.0, 0.1, 0.05, 0.02, 5e-3, 1e-3, 1e-5, 1e-7):
        a = s_rough(P, "nxds10ic")
        b = s_rough(P, "acp15")
        c = s_turbo(P, 0.0, tp)[0]
        print(f"  {P:>10.3g}  {a:>10.2f}  {b:>10.2f}  {c:>10.1f}")

    cm = cond_mol(d, L)
    print(f"\ngeometry: manifold {V1:g} L, chamber {V2:g} L, tube {d*10:g} mm x {L:g} cm")
    print(f"C_mol = {cm:.3g} L/s   S_eff floor = {1/(1/Tb['Sn2'] + 1/cm):.3g} L/s")

    for rp in ROUGHERS:
        R = ROUGHERS[rp]
        sim = simulate(d, L, V1, V2, Px, rp, tp)
        ix, iy = simulate_ideal(V1, V2, Px, rp, tp)
        t_bn = time_to_reach(sim["T"], sim["P2"], TARGET)
        t_id = time_to_reach(ix, iy, TARGET)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        fm = sim["fore_max"]
        ok = "OK" if fm < Tb["Pbackmax"] else "EXCEEDS CRITICAL BACKING"
        print(f"\n-- {R['model']} + {Tb['model']} --")
        print(f"  crossover at      {fmt_time(sim['t_x'])}, rougher then at "
              f"{s_rough(Px, rp):.2f} L/s ({100*s_rough(Px, rp)/R['Speak']:.0f}% of peak)")
        print(f"  turbo at crossover {sim['s_x']:,.0f} L/s "
              f"(throughput-limited from {Tb['Sn2']:.0f})")
        print(f"  peak foreline     {fm:.3g} Torr = "
              f"{100*fm/Tb['Pbackmax']:.0f}% of critical backing  [{ok}]")
        print(f"  t to 1e-6 Torr    {fmt_time(t_bn)} through bottleneck "
              f"vs {fmt_time(t_id)} ideal -> slowdown {slow}")
        print(f"  chamber base      {sim['P2'][-1]:.3g} Torr")

    print("\n-- with adhesive H2O outgassing (85 C, 20 cm^2) --")
    sim = simulate(d, L, V1, V2, Px, DEF_RP, tp, og=True)
    print(f"  chamber end   {sim['P2'][-1]:.3g} Torr total, H2O {sim['W2'][-1]:.3g} Torr")
    print(f"  H2O at RGA    {sim['W1'][-1]:.3g} Torr "
          f"(attenuation x{sim['W2'][-1]/sim['W1'][-1]:,.0f})")


# ---------------- interactive figure ----------------
def interactive():
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, CheckButtons, RadioButtons

    C_BLUE, C_ORANGE, C_AQUA, C_MUT = "#2a78d6", "#eb6834", "#1baf7a", "#898781"

    fig = plt.figure(figsize=(13, 7.6))
    fig.canvas.manager.set_window_title("Bottleneck-limited pumpdown")
    ax1 = fig.add_axes([0.07, 0.44, 0.40, 0.50])
    ax2 = fig.add_axes([0.57, 0.44, 0.40, 0.50])
    stats = fig.text(0.07, 0.36, "", fontsize=9.5, va="top", family="monospace")

    sliders = []
    specs = [
        ("Crossover (Torr)", 0.01, 10, 0.1),
        ("Tube diameter (cm)", 0.2, 10, 1.0),
        ("Tube length (cm)", 2, 30, 10),
        ("Manifold volume (L)", 0.5, 20, 2),
        ("Chamber volume (L)", 5, 1000, 100),
    ]
    for i, (lab, lo, hi, d0) in enumerate(specs):
        ax = fig.add_axes([0.34, 0.215 - i * 0.032, 0.52, 0.021])
        sliders.append(Slider(ax, lab, math.log10(lo), math.log10(hi),
                              valinit=math.log10(d0), valfmt=""))

    rp_keys = list(ROUGHERS)
    ax_rp = fig.add_axes([0.045, 0.135, 0.16, 0.085], frameon=True)
    ax_rp.set_title("Roughing pump", fontsize=9, loc="left")
    radio = RadioButtons(ax_rp, [ROUGHERS[k]["model"] for k in rp_keys])

    ax_ck = fig.add_axes([0.045, 0.03, 0.20, 0.09], frameon=False)
    ck = CheckButtons(ax_ck, ["Gas ballast open", "Adhesive H2O, 85 C"], [False, False])

    (l_p2,) = ax1.plot([], [], color=C_BLUE, lw=2, label="chamber P2")
    (l_p1,) = ax1.plot([], [], color=C_ORANGE, lw=2, label="pump side P1")
    (l_w2,) = ax1.plot([], [], color=C_BLUE, lw=1.4, ls=":", label="chamber H2O")
    (l_w1,) = ax1.plot([], [], color=C_ORANGE, lw=1.4, ls=":", label="H2O at RGA")
    (l_id,) = ax1.plot([], [], color=C_AQUA, lw=2, ls="--", label="no bottleneck (ideal)")
    l_x1 = ax1.axvline(1.0, color=C_AQUA, lw=1.2, ls=":", label="crossover")
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("pressure (Torr)")
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.grid(alpha=0.25, lw=0.5); ax1.legend(fontsize=8, loc="lower left")

    (l_c,) = ax2.plot([], [], color=C_ORANGE, lw=2, label="tube conductance C")
    (l_s,) = ax2.plot([], [], color=C_MUT, lw=1.5, ls="--", label="pump speed S")
    (l_e,) = ax2.plot([], [], color=C_BLUE, lw=2, label="delivered S_eff")
    l_x2 = ax2.axvline(0.1, color=C_AQUA, lw=1.2, ls=":", label="crossover")
    ax2.set_xlabel("chamber pressure (Torr)  -  pumpdown proceeds <--")
    ax2.set_ylabel("speed / conductance (L/s)")
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.grid(alpha=0.25, lw=0.5); ax2.legend(fontsize=8, loc="upper left")

    def update(_=None):
        Px, d, L, V1, V2 = (10 ** s.val for s in sliders)
        gb, og = ck.get_status()
        rp = rp_keys[[ROUGHERS[k]["model"] for k in rp_keys].index(radio.value_selected)]
        tp = DEF_TP
        Tb = TURBOS[tp]
        R = ROUGHERS[rp]
        for s in sliders:
            s.valtext.set_text(f"{10**s.val:,.3g}")

        sim = simulate(d, L, V1, V2, Px, rp, tp, gb, og)
        T, P1, P2, W1, W2 = sim["T"], sim["P1"], sim["P2"], sim["W1"], sim["W2"]
        ix, iy = simulate_ideal(V1, V2, Px, rp, tp, gb, og)
        l_p2.set_data(T, P2); l_p1.set_data(T, P1); l_id.set_data(ix, iy)
        if og:
            l_w2.set_data(T, W2); l_w1.set_data(T, W1)
        else:
            l_w2.set_data([], []); l_w1.set_data([], [])
        if sim["t_x"]:
            l_x1.set_xdata([sim["t_x"], sim["t_x"]])
        ax1.set_xlim(max(1e-4, T[-1] * 1e-7), T[-1] * 1.2)
        ax1.set_ylim(Tb["Pu"] / 3, P_ATM * 3)

        x0 = Tb["Pu"] * 0.7
        Pg = [10 ** (math.log10(x0) + i / 320 * (math.log10(P_ATM) - math.log10(x0)))
              for i in range(321)]
        Cg = [cond(d, L, P) for P in Pg]
        Sg = [max(s_rough(P, rp, gb) if P > Px else s_turbo(P, 0.0, tp)[0], 1e-6)
              for P in Pg]
        Eg = [1 / (1 / s + 1 / c) for s, c in zip(Sg, Cg)]
        l_c.set_data(Pg, Cg); l_s.set_data(Pg, Sg); l_e.set_data(Pg, Eg)
        l_x2.set_xdata([Px, Px])
        cm = cond_mol(d, L)
        floor = 1 / (1 / Tb["Sn2"] + 1 / cm)
        ax2.set_xlim(x0, P_ATM)
        ax2.set_ylim(max(1e-3, min(floor, cm) / 30), max(Tb["Sn2"], cm) * 40)

        t_bn = time_to_reach(T, P2, TARGET)
        t_id = time_to_reach(ix, iy, TARGET)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        fm = sim["fore_max"]
        rga = (f"\nH2O at RGA {W1[-1]:.3g} Torr vs chamber {W2[-1]:.3g} Torr "
               f"(attenuation x{W2[-1]/W1[-1]:,.0f})") if og else ""
        stats.set_text(
            f"{R['model']} rough: peak {R['Speak']:.2f} L/s, ultimate "
            f"{p_ult(rp, gb):.3g} Torr -> {s_rough(Px, rp, gb):.2f} L/s at crossover "
            f"({100*s_rough(Px, rp, gb)/R['Speak']:.0f}% of peak)\n"
            f"{Tb['model']} turbo: {Tb['Sn2']:.0f} L/s rated, throughput-limited "
            f"above {Tb['Qmax']/Tb['Sn2']:.3g} Torr -> {sim['s_x']:,.0f} L/s at crossover\n"
            f"peak foreline {fm:.3g} Torr = {100*fm/Tb['Pbackmax']:.0f}% of the "
            f"{Tb['Pbackmax']:.3g} Torr critical backing\n"
            f"C_mol = {cm:,.3g} L/s   S_eff floor = {floor:,.3g} L/s\n"
            f"time to 1e-6 Torr: {fmt_time(t_bn)} through bottleneck "
            f"vs {fmt_time(t_id)} ideal  ->  slowdown {slow}" + rga
        )
        fig.canvas.draw_idle()

    for s in sliders:
        s.on_changed(update)
    ck.on_clicked(update)
    radio.on_clicked(update)
    update()
    plt.show()


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        interactive()
