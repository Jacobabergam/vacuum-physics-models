#!/usr/bin/env python3
"""Bottleneck-limited pumpdown: viscous vs. molecular flow.

10iC cryopump -> small manifold (V1) -> bottleneck tube (d x L) -> chamber (V2),
with a 10 cfm rough pump on the manifold that hands off at crossover.

Shows two things at once:
  * the tube conductance collapsing from viscous (C ~ d^4 * P / L, huge near
    atmosphere) to molecular (C ~ d^3 / L, fixed, tiny), so the bottleneck
    barely matters at high pressure and completely dominates at high vacuum;
  * neither pump offering a constant speed — the rougher chokes off near its
    blank-off, and the cryo is heat-load throttled to Qmax/P until the chamber
    drops below Qmax/Smax.

Every run starts at 760 Torr. Air at 20 C. Units: cm, L, s, Torr.

Run interactively:   python3 bottleneck_pumpdown.py
Numeric self-check:  python3 bottleneck_pumpdown.py --check
"""

import math
import sys

# ---------------- physics ----------------
P_ATM = 760.0    # every run starts at atmosphere — not a parameter
LAM = 5.0e-3     # mean-free-path * pressure, cm*Torr (air, 20 C)
TARGET = 1e-6    # target pressure for the timing readout, Torr

# --- the fixed pump set --------------------------------------------------
# CRYO: 10iC, the 10-inch On-Board class. Rated speeds are molecular-flow
# values; the pump is a cold surface with a fixed capture area, so its speed is
# flat wherever gas arrives molecularly. What bends the curve is the
# refrigerator — condensing gas dumps heat on the 15 K array, and past a
# maximum throughput Qmax the array can no longer hold temperature. Above
# Pmax = Qmax/Smax the pump is heat-load limited and S falls as Qmax/P.
# ROUGH: 10 cfm dry pump, the capacity CTI specifies per On-Board cryopump.
CRYO_MODEL = "10iC"
CRYO_SAIR = 3000.0   # L/s, air / N2   (molecular-flow rated speed)
CRYO_SW = 9000.0     # L/s, water vapour — the 80 K frontal array
CRYO_SH2 = 5000.0    # L/s, hydrogen (not modelled, quoted for reference)
CRYO_QMAX = 19.0     # Torr*L/s, max continuous throughput (1500 sccm Ar)
CRYO_XMAX = 300.0    # Torr*L, crossover gas-burst rating
CRYO_PU = 1e-9       # Torr, ultimate
CRYO_PMAX = CRYO_QMAX / CRYO_SAIR   # 6.3e-3 Torr — above this the cryo throttles

ROUGH_CFM = 10.0
ROUGH_S = 4.72       # L/s (10 cfm)
ROUGH_PB = 0.02      # Torr, blank-off


def mfp(P):
    return LAM / P                                    # cm


def cond_mol(d, L):
    return 12.1 * d**3 / (L + 1.333 * d)              # L/s, end-corrected tube


def cond_vis(d, L, Pavg):
    return 180.0 * d**4 / L * Pavg                    # L/s, Poiseuille (Torr)


def cond(d, L, Pavg):
    return cond_vis(d, L, Pavg) + cond_mol(d, L)      # Knudsen-interp approximation


def s_rough(P):
    """Rough-pump speed: flat displacement, rolling off as back-leakage across
    the vanes eats the swept volume — a genuine loss of volumetric rate, so it
    belongs in S. Zero at blank-off.
    """
    return max(0.0, ROUGH_S * (1 - ROUGH_PB / max(P, 1e-12)))


def s_cryo(Pa, Pw):
    """Cryo capture speeds for (air, water) at inlet partials, plus the throttle.

    The throughput ceiling is a heat-load limit, so it is shared: total load
    throttles every species alike. The ultimate is NOT folded in here: for a
    cryopump it is re-evaporation off the array, a back-leak, and enters as the
    Pu term in the integrator. Keeping them apart means this stays the pump's
    real speed — a 10iC at base pressure is still a 3,000 L/s pump.
    """
    a0, w0 = CRYO_SAIR, CRYO_SW
    Q = a0 * Pa + w0 * Pw
    k = CRYO_QMAX / Q if Q > CRYO_QMAX else 1.0
    return a0 * k, w0 * k, k


def pump_speeds(crossed, Pa, Pw):
    """Speed offered to the manifold now, whichever pump is valved in."""
    if crossed:
        sa, sw, _ = s_cryo(Pa, Pw)
        return sa, sw
    s = s_rough(Pa + Pw)
    return s, s


def cross_now(P2tot, P1tot, Px):
    """Standard practice is to cross over on the chamber gauge; the second
    clause is the real-world escape hatch — once the rougher sits at blank-off
    it will never get you lower, so you cross over anyway."""
    return P2tot <= Px or P1tot <= ROUGH_PB * 1.2


FW = math.sqrt(29.0 / 18.0)   # molecular-speed factor for H2O (M=18) vs air (M=29)
OG_A = 20.0                   # adhesive area, cm^2
OG_Q1H = 5e-5                 # H2O outgassing rate at 85 C after 1 h, Torr*L/s/cm^2


def q_og(t):
    return OG_A * OG_Q1H * 3600.0 / max(t, 60.0)      # total throughput, ~1/t desorption decay


def be_step(P1, P2, C, Q, S, Pu, V1, V2, dt):
    """One backward-Euler step for one gas species.

    S = capture speed for this species, held over the step; Pu = the pump's
    ultimate for it (back-leak); Q = source into the chamber.
    """
    a11 = 1 + dt * (C + S) / V1
    a12 = -dt * C / V1
    a21 = -dt * C / V2
    a22 = 1 + dt * C / V2
    b1 = P1 + dt * S * Pu / V1
    b2 = P2 + dt * Q / V2
    det = a11 * a22 - a12 * a21
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def simulate(d, L, V1, V2, Px=0.1, og=False):
    """Two-volume, two-species (air + outgassed H2O) pumpdown, backward Euler.

    Rough pump valved to the manifold until crossover, then the 10iC.

    Returns dict with T, P1, P2 (totals), W1 (H2O at manifold/RGA), W2 (H2O in
    chamber), S (pump speed for air), and the crossover facts t_x, q_x, s_x.
    """
    P1a = P2a = P_ATM
    P1w = P2w = 0.0
    t, dt = 0.0, 1e-7
    crossed, t_x, q_x, s_x = False, None, 0.0, 0.0
    T, A1, A2, W1, W2, SP = [], [], [], [], [], []

    def rec(s):
        T.append(max(t, 1e-7))
        A1.append(P1a + P1w); A2.append(P2a + P2w)
        W1.append(max(P1w, 1e-12)); W2.append(max(P2w, 1e-12))
        SP.append(max(s, 1e-6))

    rec(s_rough(P_ATM))
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e9   # 1/t outgassing never ends; cap at ~11 days
    while P2a + P2w > 2e-9 and t < t_max and steps < 60000:
        steps += 1
        if not crossed and cross_now(P2a + P2w, P1a + P1w, Px):
            crossed = True
            t_x = max(t, 1e-7)
            q_x = (P1a + P1w) * V1 + (P2a + P2w) * V2   # Torr*L handed to the cryo
            s_x = s_cryo(P1a, P1w)[0]
        cv = cond_vis(d, L, 0.5 * ((P1a + P1w) + (P2a + P2w)))
        cm = cond_mol(d, L)
        Q = q_og(t) if og else 0.0
        Sa, Sw = pump_speeds(crossed, P1a, P1w)
        Pua = CRYO_PU if crossed else 0.0   # rougher's blank-off already lives in its S
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
            rec(Sa)
            last_rec = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    rec(pump_speeds(crossed, P1a, P1w)[0])
    return {"T": T, "P1": A1, "P2": A2, "W1": W1, "W2": W2, "S": SP,
            "t_x": t_x, "q_x": q_x, "s_x": s_x}


def simulate_ideal(V1, V2, Px=0.1, og=False):
    """The same pump set bolted straight onto one lumped volume — no bottleneck."""
    V = V1 + V2
    Pa, Pw = P_ATM, 0.0
    t, dt, crossed = 0.0, 1e-7, False
    X, Y = [], []

    def rec():
        X.append(max(t, 1e-7)); Y.append(max(Pa + Pw, 1e-12))

    rec()
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e9
    while Pa + Pw > 2e-9 and t < t_max and steps < 60000:
        steps += 1
        if not crossed and cross_now(Pa + Pw, Pa + Pw, Px):
            crossed = True
        Sa, Sw = pump_speeds(crossed, Pa, Pw)
        Pua = CRYO_PU if crossed else 0.0
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

    print(f"pump set: {CRYO_MODEL} cryopump behind a {ROUGH_CFM:g} cfm rougher")
    print(f"  10iC rated  = {CRYO_SAIR:,.0f} L/s air | {CRYO_SW:,.0f} L/s H2O | "
          f"{CRYO_SH2:,.0f} L/s H2")
    print(f"  Qmax        = {CRYO_QMAX:g} Torr*L/s -> full speed only below "
          f"Pmax = {CRYO_PMAX:.3g} Torr")
    print(f"  crossover   = {CRYO_XMAX:g} Torr*L rating; ultimate {CRYO_PU:g} Torr")
    print(f"  rougher     = {ROUGH_S:g} L/s from {P_ATM:g} Torr, blank-off {ROUGH_PB:g} Torr")
    print("  speed actually delivered by the pump at its own inlet:")
    for P in (760, 1.0, 0.2, 0.1, 0.02, 6.3e-3, 1e-4, 1e-8):
        which = "rough" if P > Px else "10iC "
        S = s_rough(P) if P > Px else s_cryo(P, 0.0)[0]
        print(f"    {P:>9.3g} Torr  {which}  {S:>9,.1f} L/s")

    sim = simulate(d, L, V1, V2, Px)
    ideal_x, ideal_y = simulate_ideal(V1, V2, Px)
    t_bn = time_to_reach(sim["T"], sim["P2"], TARGET)
    t_id = time_to_reach(ideal_x, ideal_y, TARGET)
    cm = cond_mol(d, L)
    print(f"\ngeometry: manifold {V1:g} L, chamber {V2:g} L, tube {d*10:g} mm x {L:g} cm")
    print(f"C_mol            = {cm:.3g} L/s")
    print(f"S_eff floor      = {1/(1/CRYO_SAIR + 1/cm):.3g} L/s (10iC offers {CRYO_SAIR:,.0f})")
    print(f"crossover at     = {fmt_time(sim['t_x'])}, {sim['q_x']:.3g} Torr*L handed over "
          f"({100*sim['q_x']/CRYO_XMAX:.0f}% of the {CRYO_XMAX:g} Torr*L rating)")
    print(f"  max crossover pressure for this {V1+V2:g} L system = "
          f"{CRYO_XMAX/(V1+V2):.3g} Torr")
    print(f"  10iC speed at handover = {sim['s_x']:,.0f} L/s "
          f"(throttled from {CRYO_SAIR:,.0f})")
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (through bottleneck)")
    print(f"t ideal          = {fmt_time(t_id)}  (pump set direct on V1+V2)")
    print(f"slowdown         = x{t_bn/t_id:,.1f}")
    print(f"sim points       = {len(sim['T'])}, t_end = {fmt_time(sim['T'][-1])}")

    print("\n-- with adhesive H2O outgassing (85 C, 20 cm^2) --")
    sim = simulate(d, L, V1, V2, Px, og=True)
    t_bn = time_to_reach(sim["T"], sim["P2"], TARGET)
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (n/a = not reached by "
          f"{fmt_time(sim['T'][-1])})")
    print(f"chamber end      = {sim['P2'][-1]:.3g} Torr total, H2O {sim['W2'][-1]:.3g} Torr")
    print(f"H2O at RGA       = {sim['W1'][-1]:.3g} Torr  "
          f"(attenuation x{sim['W2'][-1]/sim['W1'][-1]:,.0f})")


# ---------------- interactive figure ----------------
def interactive():
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, CheckButtons

    C_BLUE, C_ORANGE, C_AQUA, C_MUT = "#2a78d6", "#eb6834", "#1baf7a", "#898781"

    fig = plt.figure(figsize=(12.5, 7.2))
    fig.canvas.manager.set_window_title(
        f"Bottleneck-limited pumpdown — {CRYO_MODEL} cryopump")
    ax1 = fig.add_axes([0.07, 0.42, 0.40, 0.50])
    ax2 = fig.add_axes([0.57, 0.42, 0.40, 0.50])
    stats = fig.text(0.07, 0.34, "", fontsize=9.5, va="top", family="monospace")

    sliders = []
    specs = [  # label, lo, hi, default (log-mapped)
        ("Crossover (Torr)", 0.03, 10, 0.1),
        ("Tube diameter (cm)", 0.2, 10, 1.0),
        ("Tube length (cm)", 2, 30, 10),
        ("Manifold volume (L)", 0.5, 20, 2),
        ("Chamber volume (L)", 5, 1000, 100),
    ]
    for i, (lab, lo, hi, d0) in enumerate(specs):
        ax = fig.add_axes([0.30, 0.205 - i * 0.033, 0.55, 0.022])
        s = Slider(ax, lab, math.log10(lo), math.log10(hi),
                   valinit=math.log10(d0), valfmt="")
        sliders.append(s)

    (l_p2,) = ax1.plot([], [], color=C_BLUE, lw=2, label="chamber P2")
    (l_p1,) = ax1.plot([], [], color=C_ORANGE, lw=2, label="pump side P1")
    (l_w2,) = ax1.plot([], [], color=C_BLUE, lw=1.4, ls=":", label="chamber H2O")
    (l_w1,) = ax1.plot([], [], color=C_ORANGE, lw=1.4, ls=":", label="H2O at RGA (manifold)")
    (l_id,) = ax1.plot([], [], color=C_AQUA, lw=2, ls="--", label="no bottleneck (ideal)")
    l_x1 = ax1.axvline(1.0, color=C_AQUA, lw=1.2, ls=":", label="crossover")
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("pressure (Torr)")
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.grid(alpha=0.25, lw=0.5); ax1.legend(fontsize=9, loc="lower left")

    (l_c,) = ax2.plot([], [], color=C_ORANGE, lw=2, label="tube conductance C")
    (l_s,) = ax2.plot([], [], color=C_MUT, lw=1.5, ls="--",
                      label="pump speed S (rougher, then 10iC)")
    (l_e,) = ax2.plot([], [], color=C_BLUE, lw=2, label="delivered S_eff")
    l_x2 = ax2.axvline(0.1, color=C_AQUA, lw=1.2, ls=":", label="crossover")
    ax2.set_xlabel("chamber pressure (Torr)  —  pumpdown proceeds <--")
    ax2.set_ylabel("speed / conductance (L/s)")
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.grid(alpha=0.25, lw=0.5); ax2.legend(fontsize=9, loc="upper left")

    ax_ck = fig.add_axes([0.045, 0.05, 0.17, 0.09], frameon=False)
    ck = CheckButtons(ax_ck, ["Adhesive H2O, 85 C"], [False])

    def update(_=None):
        Px, d, L, V1, V2 = (10 ** s.val for s in sliders)
        og = ck.get_status()[0]
        for s in sliders:
            s.valtext.set_text(f"{10**s.val:,.3g}")
        sim = simulate(d, L, V1, V2, Px, og)
        T, P1, P2, W1, W2 = sim["T"], sim["P1"], sim["P2"], sim["W1"], sim["W2"]
        ideal_x, ideal_y = simulate_ideal(V1, V2, Px, og)
        l_p2.set_data(T, P2); l_p1.set_data(T, P1); l_id.set_data(ideal_x, ideal_y)
        if og:
            l_w2.set_data(T, W2); l_w1.set_data(T, W1)
        else:
            l_w2.set_data([], []); l_w1.set_data([], [])
        if sim["t_x"]:
            l_x1.set_xdata([sim["t_x"], sim["t_x"]])
        ax1.set_xlim(max(1e-4, T[-1] * 1e-7), T[-1] * 1.2)
        ax1.set_ylim(6e-10, P_ATM * 3)

        Pg = [10 ** (-9 + i / 300 * (math.log10(P_ATM) + 9)) for i in range(301)]
        Cg = [cond(d, L, P) for P in Pg]
        Sg = [max(s_rough(P) if P > Px else s_cryo(P, 0.0)[0], 1e-6) for P in Pg]
        Eg = [1 / (1 / s + 1 / c) for s, c in zip(Sg, Cg)]
        l_c.set_data(Pg, Cg); l_s.set_data(Pg, Sg); l_e.set_data(Pg, Eg)
        l_x2.set_xdata([Px, Px])
        cm = cond_mol(d, L)
        floor = 1 / (1 / CRYO_SAIR + 1 / cm)
        ax2.set_xlim(1e-9, P_ATM)
        ax2.set_ylim(max(1e-2, min(floor, ROUGH_S) / 10), max(CRYO_SAIR, cm) * 40)

        t_bn = time_to_reach(T, P2, TARGET)
        t_id = time_to_reach(ideal_x, ideal_y, TARGET)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        rga = (f"\nH2O at RGA {W1[-1]:.3g} Torr vs chamber {W2[-1]:.3g} Torr "
               f"(attenuation x{W2[-1]/W1[-1]:,.0f})") if og else ""
        stats.set_text(
            f"{CRYO_MODEL} cryopump: {CRYO_SAIR:,.0f} L/s air, {CRYO_SW:,.0f} L/s H2O, "
            f"Qmax {CRYO_QMAX:g} Torr*L/s (full speed below {CRYO_PMAX:.2g} Torr)\n"
            f"crossover {fmt_time(sim['t_x'])} in, {sim['q_x']:.3g} Torr*L handed over "
            f"({100*sim['q_x']/CRYO_XMAX:.0f}% of {CRYO_XMAX:g}), "
            f"10iC delivering {sim['s_x']:,.0f} L/s at handover\n"
            f"C_mol = {cm:,.3g} L/s   S_eff floor = {floor:,.3g} L/s\n"
            f"time to 1e-6 Torr: {fmt_time(t_bn)} through bottleneck "
            f"vs {fmt_time(t_id)} ideal  ->  slowdown {slow}\n"
            f"regime boundaries (Kn=0.01 / 0.5): viscous above {LAM/(0.01*d):.3g} Torr, "
            f"molecular below {LAM/(0.5*d):.3g} Torr" + rga
        )
        fig.canvas.draw_idle()

    for s in sliders:
        s.on_changed(update)
    ck.on_clicked(update)
    update()
    plt.show()


if __name__ == "__main__":
    if "--check" in sys.argv:
        check()
    else:
        interactive()
