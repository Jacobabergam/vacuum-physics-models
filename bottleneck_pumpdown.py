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

# --- the pump: Edwards nXDS10iC dry scroll -------------------------------
# A positive-displacement machine, not a capture pump. It sweeps a fixed volume
# per revolution (12.7 m3/h displacement at 1800 rpm), but the speed you
# actually get is the peak 11.4 m3/h = 3.17 L/s, and that falls away as the
# inlet approaches ultimate: the tip seals leak gas back across the scroll
# flanks faster and faster relative to the shrinking amount swept forward.
# Net speed S = S_peak*(1 - Pu/P) - genuinely zero at ultimate.
# "C" is the corrosion-resistant build (Chemraz valve pads, stainless
# fittings); its speed and ultimate are identical to the plain nXDS10i.
MBAR = 0.7500617          # Torr per mbar
PUMP_MODEL = "nXDS10iC"
S_PEAK = 11.4 / 3.6       # L/s - 11.4 m3/h (6.7 cfm) peak pumping speed
S_DISP = 12.7 / 3.6       # L/s - 12.7 m3/h (7.5 cfm) swept displacement
PUMP_RPM = 1800
PU_GB0 = 7e-3 * MBAR      # Torr, ultimate, gas ballast closed  (5.25e-3)
PU_GB1 = 4e-2 * MBAR      # Torr, ultimate, gas ballast open    (3.00e-2)


def p_ult(gb):
    return PU_GB1 if gb else PU_GB0


def s_pump(P, gb):
    """Net speed at the pump inlet. One curve, both species - a displacement
    pump sweeps whatever is in front of it, so air and water get the same L/s.
    """
    return max(0.0, S_PEAK * (1 - p_ult(gb) / max(P, 1e-12)))


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


def be_step(P1, P2, C, Q, S, V1, V2, dt):
    """One backward-Euler step for one gas species.

    S = pump speed for this species, held over the step; Q = source into the
    chamber. The ultimate is already inside S (back-leakage past the tip seals
    is a real loss of swept volume), so there is no separate back-leak term.
    """
    a11 = 1 + dt * (C + S) / V1
    a12 = -dt * C / V1
    a21 = -dt * C / V2
    a22 = 1 + dt * C / V2
    b1 = P1
    b2 = P2 + dt * Q / V2
    det = a11 * a22 - a12 * a21
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def simulate(d, L, V1, V2, gb=False, og=False):
    """Two-volume, two-species (air + outgassed H2O) pumpdown, backward Euler.

    One nXDS10iC on the manifold, running from atmosphere all the way down.

    Returns dict with T, P1, P2 (totals), W1 (H2O at the pump inlet), W2 (H2O
    in the chamber) and S (pump speed).
    """
    P1a = P2a = P_ATM
    P1w = P2w = 0.0
    t, dt = 0.0, 1e-7
    Pu = p_ult(gb)
    T, A1, A2, W1, W2, SP = [], [], [], [], [], []

    def rec(s):
        T.append(max(t, 1e-7))
        A1.append(P1a + P1w); A2.append(P2a + P2w)
        W1.append(max(P1w, 1e-12)); W2.append(max(P2w, 1e-12))
        SP.append(max(s, 1e-6))

    rec(s_pump(P_ATM, gb))
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e5   # with 1/t outgassing the decay never ends
    while P2a + P2w > Pu * 1.02 and t < t_max and steps < 60000:
        steps += 1
        cv = cond_vis(d, L, 0.5 * ((P1a + P1w) + (P2a + P2w)))
        cm = cond_mol(d, L)
        Q = q_og(t) if og else 0.0
        S = s_pump(P1a + P1w, gb)      # one speed, set by total inlet pressure
        n1a, n2a = be_step(P1a, P2a, cv + cm, 0.0, S, V1, V2, dt)
        n1w, n2w = be_step(P1w, P2w, cv + cm * FW, Q, S, V1, V2, dt)
        rel = max(abs(n1a + n1w - (P1a + P1w)) / max(P1a + P1w, 1e-10),
                  abs(n2a + n2w - (P2a + P2w)) / max(P2a + P2w, 1e-10))
        if rel > 0.25 and dt > 1e-8:
            dt *= 0.5
            continue
        t += dt
        P1a, P2a, P1w, P2w = n1a, n2a, n1w, n2w
        if t >= last_rec * 1.05:
            rec(S)
            last_rec = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    rec(s_pump(P1a + P1w, gb))
    return {"T": T, "P1": A1, "P2": A2, "W1": W1, "W2": W2, "S": SP}


def simulate_ideal(V1, V2, gb=False, og=False):
    """The same pump bolted straight onto one lumped volume - no bottleneck."""
    V = V1 + V2
    Pu = p_ult(gb)
    Pa, Pw = P_ATM, 0.0
    t, dt = 0.0, 1e-7
    X, Y = [], []

    def rec():
        X.append(max(t, 1e-7)); Y.append(max(Pa + Pw, 1e-12))

    rec()
    last_rec, steps = 0.0, 0
    t_max = 1e6 if og else 1e5
    while Pa + Pw > Pu * 1.02 and t < t_max and steps < 60000:
        steps += 1
        S = s_pump(Pa + Pw, gb)
        Q = q_og(t) if og else 0.0
        na = Pa / (1 + dt * S / V)
        nw = (Pw + dt * Q / V) / (1 + dt * S / V)
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

    print(f"pump: Edwards {PUMP_MODEL} dry scroll")
    print(f"  peak speed   = {S_PEAK*3.6:.1f} m3/h = {S_PEAK*3.6/1.699:.1f} cfm = {S_PEAK:.2f} L/s")
    print(f"  displacement = {S_DISP*3.6:.1f} m3/h at {PUMP_RPM} rpm")
    print(f"  ultimate     = {PU_GB0:.3g} Torr ballast closed / {PU_GB1:.3g} Torr open")
    print(f"  start        = {P_ATM:g} Torr, always")
    print("  speed vs inlet pressure (ballast closed):")
    for P in (760, 10, 1.0, 0.1, 0.05, 0.02, 0.01, 0.006):
        S = s_pump(P, False)
        print(f"    {P:>8.3g} Torr  {S:>6.2f} L/s  ({100*S/S_PEAK:>3.0f}% of peak)")

    cm = cond_mol(d, L)
    print(f"\ngeometry: manifold {V1:g} L, chamber {V2:g} L, tube {d*10:g} mm x {L:g} cm")
    print(f"C_mol            = {cm:.3g} L/s")
    print(f"S_eff floor      = {1/(1/S_PEAK + 1/cm):.3g} L/s (pump peaks at {S_PEAK:.2f})")

    for gb in (False, True):
        sim = simulate(d, L, V1, V2, gb)
        ix, iy = simulate_ideal(V1, V2, gb)
        t_bn = time_to_reach(sim["T"], sim["P2"], Px)
        t_id = time_to_reach(ix, iy, Px)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        tag = "ballast open " if gb else "ballast closed"
        print(f"\n-- {tag} (ultimate {p_ult(gb):.3g} Torr) --")
        print(f"t to {Px:g} Torr    = {fmt_time(t_bn)} through bottleneck "
              f"vs {fmt_time(t_id)} ideal -> slowdown {slow}")
        print(f"speed at {Px:g} Torr = {s_pump(Px, gb):.2f} L/s "
              f"({100*s_pump(Px, gb)/S_PEAK:.0f}% of peak)")
        print(f"chamber base     = {sim['P2'][-1]:.3g} Torr after {fmt_time(sim['T'][-1])}")

    print("\n-- bottleneck sweep (ballast closed, target 0.1 Torr) --")
    for dd in (1.0, 0.5, 0.3, 0.2):
        sim = simulate(dd, L, V1, V2)
        ix, iy = simulate_ideal(V1, V2)
        t_bn = time_to_reach(sim["T"], sim["P2"], Px)
        t_id = time_to_reach(ix, iy, Px)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        print(f"  bore {dd*10:>4.1f} mm  C_mol {cond_mol(dd, L):>7.4f} L/s  "
              f"t {fmt_time(t_bn):>9}  slowdown {slow}")

    print("\n-- with adhesive H2O outgassing (85 C, 20 cm^2), ballast closed --")
    sim = simulate(d, L, V1, V2, og=True)
    print(f"chamber end      = {sim['P2'][-1]:.3g} Torr total, H2O {sim['W2'][-1]:.3g} Torr")
    print(f"H2O at inlet     = {sim['W1'][-1]:.3g} Torr  "
          f"(attenuation x{sim['W2'][-1]/sim['W1'][-1]:,.1f})")
    print("  note: an RGA needs <1e-4 Torr, so it would sit downstream of a")
    print("  high-vacuum pump, not on this manifold.")


# ---------------- interactive figure ----------------
def interactive():
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, CheckButtons

    C_BLUE, C_ORANGE, C_AQUA, C_MUT = "#2a78d6", "#eb6834", "#1baf7a", "#898781"

    fig = plt.figure(figsize=(12.5, 7.2))
    fig.canvas.manager.set_window_title(
        f"Bottleneck-limited pumpdown - Edwards {PUMP_MODEL}")
    ax1 = fig.add_axes([0.07, 0.42, 0.40, 0.50])
    ax2 = fig.add_axes([0.57, 0.42, 0.40, 0.50])
    stats = fig.text(0.07, 0.34, "", fontsize=9.5, va="top", family="monospace")

    sliders = []
    specs = [  # label, lo, hi, default (log-mapped)
        ("Target (Torr)", 0.01, 10, 0.1),
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
    (l_w1,) = ax1.plot([], [], color=C_ORANGE, lw=1.4, ls=":", label="H2O at pump inlet")
    (l_id,) = ax1.plot([], [], color=C_AQUA, lw=2, ls="--", label="no bottleneck (ideal)")
    l_u1 = ax1.axhline(PU_GB0, color=C_AQUA, lw=1.2, ls=":", label="pump ultimate")
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("pressure (Torr)")
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.grid(alpha=0.25, lw=0.5); ax1.legend(fontsize=9, loc="lower left")

    (l_c,) = ax2.plot([], [], color=C_ORANGE, lw=2, label="tube conductance C")
    (l_s,) = ax2.plot([], [], color=C_MUT, lw=1.5, ls="--", label=f"{PUMP_MODEL} speed S")
    (l_e,) = ax2.plot([], [], color=C_BLUE, lw=2, label="delivered S_eff")
    l_u2 = ax2.axvline(PU_GB0, color=C_AQUA, lw=1.2, ls=":", label="ultimate")
    ax2.set_xlabel("chamber pressure (Torr)  -  pumpdown proceeds <--")
    ax2.set_ylabel("speed / conductance (L/s)")
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.grid(alpha=0.25, lw=0.5); ax2.legend(fontsize=9, loc="upper left")

    ax_ck = fig.add_axes([0.045, 0.04, 0.20, 0.11], frameon=False)
    ck = CheckButtons(ax_ck, ["Gas ballast open", "Adhesive H2O, 85 C"], [False, False])

    def update(_=None):
        Px, d, L, V1, V2 = (10 ** s.val for s in sliders)
        gb, og = ck.get_status()
        for s in sliders:
            s.valtext.set_text(f"{10**s.val:,.3g}")
        Pu = p_ult(gb)
        sim = simulate(d, L, V1, V2, gb, og)
        T, P1, P2, W1, W2 = sim["T"], sim["P1"], sim["P2"], sim["W1"], sim["W2"]
        ix, iy = simulate_ideal(V1, V2, gb, og)
        l_p2.set_data(T, P2); l_p1.set_data(T, P1); l_id.set_data(ix, iy)
        if og:
            l_w2.set_data(T, W2); l_w1.set_data(T, W1)
        else:
            l_w2.set_data([], []); l_w1.set_data([], [])
        l_u1.set_ydata([Pu, Pu])
        ax1.set_xlim(max(1e-4, T[-1] * 1e-7), T[-1] * 1.2)
        ax1.set_ylim(min(Pu, Px) / 4, P_ATM * 3)

        x0 = Pu * 0.7
        Pg = [10 ** (math.log10(x0) + i / 300 * (math.log10(P_ATM) - math.log10(x0)))
              for i in range(301)]
        Cg = [cond(d, L, P) for P in Pg]
        Sg = [max(s_pump(P, gb), 1e-6) for P in Pg]
        Eg = [1 / (1 / s + 1 / c) for s, c in zip(Sg, Cg)]
        l_c.set_data(Pg, Cg); l_s.set_data(Pg, Sg); l_e.set_data(Pg, Eg)
        l_u2.set_xdata([Pu, Pu])
        cm = cond_mol(d, L)
        floor = 1 / (1 / S_PEAK + 1 / cm)
        ax2.set_xlim(x0, P_ATM)
        ax2.set_ylim(max(1e-3, min(floor, cm) / 30), max(S_PEAK, cm) * 300)

        t_bn = time_to_reach(T, P2, Px)
        t_id = time_to_reach(ix, iy, Px)
        slow = f"x{t_bn/t_id:,.1f}" if (t_bn and t_id) else "n/a"
        rga = (f"\nH2O at inlet {W1[-1]:.3g} Torr vs chamber {W2[-1]:.3g} Torr "
               f"(attenuation x{W2[-1]/W1[-1]:,.1f})") if og else ""
        stats.set_text(
            f"{PUMP_MODEL}: peak {S_PEAK:.2f} L/s ({S_PEAK*3.6:.1f} m3/h), "
            f"ultimate {Pu:.3g} Torr (ballast {'open' if gb else 'closed'})\n"
            f"speed at target {s_pump(Px, gb):.2f} L/s "
            f"({100*s_pump(Px, gb)/S_PEAK:.0f}% of peak); chamber base "
            f"{P2[-1]:.3g} Torr\n"
            f"C_mol = {cm:,.3g} L/s   S_eff floor = {floor:,.3g} L/s\n"
            f"time to {Px:.3g} Torr: {fmt_time(t_bn)} through bottleneck "
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
