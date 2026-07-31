#!/usr/bin/env python3
"""Bottleneck-limited pumpdown: viscous vs. molecular flow.

Turbopump -> small manifold (V1) -> bottleneck tube (d x L) -> chamber (V2).
Shows how the tube conductance collapses from viscous (C ~ d^4 * P / L, huge near
atmosphere) to molecular (C ~ d^3 / L, fixed, tiny) — so the bottleneck barely
matters at high pressure and completely dominates at high vacuum.

Air at 20 C. Units: cm, L, s, Torr.

Run interactively:   python3 bottleneck_pumpdown.py
Numeric self-check:  python3 bottleneck_pumpdown.py --check
"""

import math
import sys

# ---------------- physics ----------------
PU = 1e-9        # turbopump ultimate pressure, Torr
LAM = 5.0e-3     # mean-free-path * pressure, cm*Torr (air, 20 C)
TARGET = 1e-6    # target pressure for the timing readout, Torr

# Fixed timeline: every run spans the same 0.1 ms -> 20 days window so the time
# axis never rescales when parameters change.
T_START = 1e-4
T_END = 20 * 86400


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


def be_step(P1, P2, C, Q, Pu, S, V1, V2, dt):
    """One backward-Euler step for one gas species (Q = source into chamber)."""
    a11 = 1 + dt * (C + S) / V1
    a12 = -dt * C / V1
    a21 = -dt * C / V2
    a22 = 1 + dt * C / V2
    b1 = P1 + dt * S * Pu / V1
    b2 = P2 + dt * Q / V2
    det = a11 * a22 - a12 * a21
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def simulate(P0, S, d, L, V1, V2, og=False):
    """Two-volume, two-species (air + outgassed H2O) pumpdown, backward Euler.

    Returns T, P1_total, P2_total, W1 (H2O at manifold/RGA), W2 (H2O in chamber).
    """
    P1a = P2a = P0
    P1w = P2w = 0.0
    t, dt = 0.0, 1e-7
    T, A1, A2, W1, W2 = [], [], [], [], []

    def rec():
        T.append(max(t, 1e-7))
        A1.append(P1a + P1w); A2.append(P2a + P2w)
        W1.append(max(P1w, 1e-12)); W2.append(max(P2w, 1e-12))

    rec()
    last_rec, steps = 0.0, 0
    while P2a + P2w > 2e-9 and t < T_END and steps < 60000:
        steps += 1
        cv = cond_vis(d, L, 0.5 * ((P1a + P1w) + (P2a + P2w)))
        cm = cond_mol(d, L)
        Q = q_og(t) if og else 0.0
        n1a, n2a = be_step(P1a, P2a, cv + cm, 0.0, PU, S, V1, V2, dt)
        n1w, n2w = be_step(P1w, P2w, cv + cm * FW, Q, 0.0, S, V1, V2, dt)
        rel = max(abs(n1a + n1w - (P1a + P1w)) / max(P1a + P1w, 1e-10),
                  abs(n2a + n2w - (P2a + P2w)) / max(P2a + P2w, 1e-10))
        if rel > 0.25 and dt > 1e-8:
            dt *= 0.5
            continue
        t += dt
        P1a, P2a, P1w, P2w = n1a, n2a, n1w, n2w
        if t >= last_rec * 1.05:
            rec()
            last_rec = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    rec()
    # Land the curve exactly on the window edge: hold the last state out to 20 days
    # if the run bottomed out at the ultimate early, else trim the final overshoot.
    if t < T_END:
        t = T_END
        rec()
    else:
        T[-1] = T_END
    return T, A1, A2, W1, W2


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
    P0, S, d, L, V1, V2 = 760.0, 1500.0, 1.0, 10.0, 2.0, 100.0
    T, P1, P2, _, _ = simulate(P0, S, d, L, V1, V2)
    t_bn = time_to_reach(T, P2, TARGET)
    t_id = (V1 + V2) / S * math.log((P0 - PU) / (TARGET - PU))
    cm = cond_mol(d, L)
    print(f"V1 manifold      = {V1:g} L")
    print(f"C_mol            = {cm:.3g} L/s")
    print(f"S_eff floor      = {1/(1/S + 1/cm):.3g} L/s (pump offers {S:g})")
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (through bottleneck)")
    print(f"t ideal          = {fmt_time(t_id)}  (pump direct on V1+V2)")
    print(f"slowdown         = x{t_bn/t_id:,.0f}")
    print(f"sim points       = {len(T)}, t_end = {fmt_time(T[-1])}")
    print("-- with adhesive H2O outgassing (85 C, 20 cm^2) --")
    T, P1, P2, W1, W2 = simulate(P0, S, d, L, V1, V2, og=True)
    t_bn = time_to_reach(T, P2, TARGET)
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (None = not reached by {fmt_time(T[-1])})")
    print(f"chamber end      = {P2[-1]:.3g} Torr total, H2O {W2[-1]:.3g} Torr")
    print(f"H2O at RGA       = {W1[-1]:.3g} Torr  (attenuation x{W2[-1]/W1[-1]:,.0f})")


# ---------------- interactive figure ----------------
def interactive():
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Slider, CheckButtons

    C_BLUE, C_ORANGE, C_AQUA, C_MUT = "#2a78d6", "#eb6834", "#1baf7a", "#898781"

    fig = plt.figure(figsize=(12.5, 7.2))
    fig.canvas.manager.set_window_title("Bottleneck-limited pumpdown")
    ax1 = fig.add_axes([0.07, 0.42, 0.40, 0.50])
    ax2 = fig.add_axes([0.57, 0.42, 0.40, 0.50])
    stats = fig.text(0.07, 0.34, "", fontsize=10, va="top", family="monospace")

    sliders = []
    specs = [  # label, lo, hi, default (log-mapped)
        ("Start pressure (Torr)", 0.01, 760, 760),
        ("Pump speed (L/s)", 50, 20000, 1500),
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
    ax1.set_xlabel("time (s)"); ax1.set_ylabel("pressure (Torr)")
    ax1.set_xscale("log"); ax1.set_yscale("log")
    ax1.grid(alpha=0.25, lw=0.5); ax1.legend(fontsize=9, loc="lower left")

    (l_c,) = ax2.plot([], [], color=C_ORANGE, lw=2, label="tube conductance C")
    (l_s,) = ax2.plot([], [], color=C_MUT, lw=1.5, ls="--", label="pump speed S")
    (l_e,) = ax2.plot([], [], color=C_BLUE, lw=2, label="delivered S_eff")
    ax2.set_xlabel("chamber pressure (Torr)  —  pumpdown proceeds <--")
    ax2.set_ylabel("speed / conductance (L/s)")
    ax2.set_xscale("log"); ax2.set_yscale("log")
    ax2.grid(alpha=0.25, lw=0.5); ax2.legend(fontsize=9, loc="upper left")

    ax_ck = fig.add_axes([0.045, 0.05, 0.17, 0.09], frameon=False)
    ck = CheckButtons(ax_ck, ["Adhesive H2O, 85 C"], [False])

    def update(_=None):
        P0, S, d, L, V1, V2 = (10 ** s.val for s in sliders)
        og = ck.get_status()[0]
        for s, (lab, *_r) in zip(sliders, specs):
            s.valtext.set_text(f"{10**s.val:,.3g}")
        T, P1, P2, W1, W2 = simulate(P0, S, d, L, V1, V2, og)
        t_id_curve = [PU + (P0 - PU) * math.exp(-S * t / (V1 + V2))
                      + (q_og(t) / S if og else 0.0) for t in T]
        l_p2.set_data(T, P2); l_p1.set_data(T, P1); l_id.set_data(T, t_id_curve)
        if og:
            l_w2.set_data(T, W2); l_w1.set_data(T, W1)
        else:
            l_w2.set_data([], []); l_w1.set_data([], [])
        ax1.set_xlim(T_START, T_END)
        ax1.set_ylim(6e-10, P0 * 3)

        Pg = [10 ** (-9 + i / 220 * (math.log10(P0) + 9)) for i in range(221)]
        Cg = [cond(d, L, P) for P in Pg]
        Eg = [1 / (1 / S + 1 / c) for c in Cg]
        l_c.set_data(Pg, Cg); l_s.set_data([Pg[0], Pg[-1]], [S, S]); l_e.set_data(Pg, Eg)
        cm = cond_mol(d, L)
        ax2.set_xlim(1e-9, P0); ax2.set_ylim(max(1e-3, Eg[0] / 8), max(S, cm) * 40)

        t_bn = time_to_reach(T, P2, TARGET)
        if og:
            t_id = time_to_reach(T, t_id_curve, TARGET)
        else:
            t_id = (V1 + V2) / S * math.log((P0 - PU) / (TARGET - PU)) if P0 > TARGET else None
        slow = f"x{t_bn/t_id:,.0f}" if (t_bn and t_id) else "n/a"
        rga = (f"\nH2O at RGA {W1[-1]:.3g} Torr vs chamber {W2[-1]:.3g} Torr "
               f"(attenuation x{W2[-1]/W1[-1]:,.0f})") if og else ""
        stats.set_text(
            f"C_mol = {cm:,.3g} L/s   S_eff floor = {1/(1/S+1/cm):,.3g} L/s "
            f"(of {S:,.0f} L/s pump)\n"
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
