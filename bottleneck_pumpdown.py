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

# ---- Edwards pump station (defaults; anchors from catalog, roll-offs digitized) ----
# Roughing: nXDS10iC dry scroll — peak 11.4 m3/h = 3.17 L/s, ultimate 7e-3 mbar (5.3e-3 Torr).
# High-vac: nEXT85 (DN63) turbo — 84 L/s N2 plateau, critical backing 18 mbar.
# Station speed at the manifold: S(P) = max(turbo, scroll). Units [Torr, L/s].
SCROLL_PTS = [(5.25e-3, 1e-4), (0.01, 0.5), (0.03, 1.4), (0.1, 2.3), (0.3, 2.8),
              (1.0, 3.1), (10.0, 3.17), (100.0, 3.0), (760.0, 2.6)]
TURBO_PTS = [(1e-9, 84.0), (7.5e-4, 84.0), (2.5e-3, 80.0), (7.5e-3, 68.0), (2.5e-2, 47.0),
             (7.5e-2, 26.0), (0.25, 11.0), (0.75, 3.5), (2.5, 1.0), (7.5, 0.25), (13.5, 0.05)]
S_TURBO0 = 84.0


def _interp_table(pts, P):
    if P <= pts[0][0]:
        return pts[0][1]
    if P >= pts[-1][0]:
        return pts[-1][1]
    for i in range(1, len(pts)):
        if P <= pts[i][0]:
            f = (math.log(P) - math.log(pts[i-1][0])) / (math.log(pts[i][0]) - math.log(pts[i-1][0]))
            return math.exp(math.log(pts[i-1][1]) + f * (math.log(pts[i][1]) - math.log(pts[i-1][1])))
    return pts[-1][1]


def pump_s(P, scale=1.0):
    """Station pumping speed at manifold pressure P [Torr] -> L/s."""
    return max(_interp_table(TURBO_PTS, P) * scale, _interp_table(SCROLL_PTS, P))

# Adhesive H2O source at 85 C — depleting Fickian reservoir (mirrors the HTML app).
#   q(t) = c0 * sqrt(D/(pi t)) * exp(-t/tau1) per cm^2 exposed;  tau1 = 4 L^2/(pi^2 D),  L = V/A.
#   c0 = 1 wt% x 1.15 g/cm^3 = 11.7 Torr*L/cm^3; D(85 C) = 4.53e-8 cm^2/s (epoxy-class,
#   Arrhenius from D(295 K)=2e-9 cm^2/s, Ea=0.45 eV). q(1 h) = 2.4e-5 Torr*L/s/cm^2 — the old
#   hard-coded 5e-5 was this rounded up ~x2, with an (incorrect for bulk diffusion) 1/t decay.
#   Refs: Chiggiato, CERN Yellow Rep. arXiv:2006.07124; Crank, The Mathematics of Diffusion.
OG_C0 = 11.7                  # Torr*L per cm^3 of adhesive (1 wt% H2O, rho 1.15 g/cm^3)
OG_D85 = 4.53e-8              # cm^2/s, water in epoxy at 85 C
OG_A0, OG_V0 = 20.0, 0.5      # default exposed area cm^2, volume cm^3

# Wall-water sources (both H2O; different kinetics and injection points):
#  hot chamber walls (85 C): ~3 ML on A_DW draining as a 30-min pool;
#  unheated manifold (22 C): unbaked 1/t law into V1 — the RGA's water background.
A_DW, A_MAN = 300.0, 600.0
DW_I0, DW_TAU = 3 * 3.05e-5 * A_DW, 1800.0


def q_dw(t):
    return DW_I0 / DW_TAU * math.exp(-t / DW_TAU)


def q_man(t):
    return A_MAN * 2.2e-9 * 3600.0 / max(t, 60.0)


def og_tau1(A, V):
    Lc = V / A
    return 4.0 * Lc * Lc / (math.pi ** 2 * OG_D85)


def q_og(t, A=OG_A0, V=OG_V0):
    tt = max(t, 60.0)
    return A * OG_C0 * math.sqrt(OG_D85 / (math.pi * tt)) * math.exp(-tt / og_tau1(A, V))


def be_step(P1, P2, C, Q1, Q2, Pu, S, V1, V2, dt):
    """One backward-Euler step for one species (Q1 -> manifold, Q2 -> chamber)."""
    a11 = 1 + dt * (C + S) / V1
    a12 = -dt * C / V1
    a21 = -dt * C / V2
    a22 = 1 + dt * C / V2
    b1 = P1 + dt * (S * Pu + Q1) / V1
    b2 = P2 + dt * Q2 / V2
    det = a11 * a22 - a12 * a21
    return (b1 * a22 - a12 * b2) / det, (a11 * b2 - a21 * b1) / det


def simulate(P0, St, d, L, V1, V2, og=False, ogA=OG_A0, ogV=OG_V0, lk=False, Ql=1e-6, ww=True):
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
        Q = q_og(t, ogA, ogV) if og else 0.0
        Sp = pump_s(P1a + P1w, St / S_TURBO0)   # station speed at manifold pressure
        qw2 = Q + (q_dw(t) if ww else 0.0)      # chamber-side water: glue + hot walls
        qw1 = q_man(t) if ww else 0.0           # manifold-side water: unheated plumbing
        n1a, n2a = be_step(P1a, P2a, cv + cm, 0.0, (Ql if lk else 0.0), PU, Sp, V1, V2, dt)
        n1w, n2w = be_step(P1w, P2w, cv + cm * FW, qw1, qw2, 0.0, Sp, V1, V2, dt)
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


def ideal_sim(P0, St, V, og=False, ogA=OG_A0, ogV=OG_V0, lk=False, Ql=1e-6, ww=True):
    """Single lumped volume (no bottleneck) pumped by the same S(P) station curve."""
    P, t, dt, last = P0, 0.0, 1e-7, 0.0
    X, Y = [1e-7], [P0]
    t_max = 1e7 if og else (1e5 if lk else 1e9)
    while P > 2e-9 and t < t_max and len(X) < 5000:
        S = pump_s(P, St / S_TURBO0)
        Q = (q_og(t, ogA, ogV) if og else 0.0) + (Ql if lk else 0.0) + ((q_dw(t) + q_man(t)) if ww else 0.0)
        P = (P + dt * (S * PU + Q) / V) / (1 + dt * S / V)
        t += dt
        if t >= last * 1.05:
            X.append(t); Y.append(max(P, 1e-12)); last = t
        dt = min(dt * 1.2, 0.02 * t + 1e-7)
    X.append(max(t, 1e-6)); Y.append(max(P, 1e-12))
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
    P0, St, d, L, V1, V2 = 760.0, 84.0, 1.0, 10.0, 2.0, 100.0
    T, P1, P2, _, _ = simulate(P0, St, d, L, V1, V2)
    t_bn = time_to_reach(T, P2, TARGET)
    Xi, Yi = ideal_sim(P0, St, V1 + V2)
    t_id = time_to_reach(Xi, Yi, TARGET)
    cm = cond_mol(d, L)
    print(f"station: nXDS10iC scroll + nEXT {St:g} L/s turbo; "
          f"S(760 Torr)={pump_s(760):.2f}, S(1 Torr)={pump_s(1.0):.2f}, S(1e-5 Torr)={pump_s(1e-5):.1f} L/s")
    print(f"V1 manifold      = {V1:g} L")
    print(f"C_mol            = {cm:.3g} L/s")
    print(f"S_eff floor      = {1/(1/St + 1/cm):.3g} L/s (turbo plateau {St:g})")
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (through bottleneck)")
    print(f"t ideal          = {fmt_time(t_id)}  (pump direct on V1+V2)")
    print(f"slowdown         = x{t_bn/t_id:,.0f}")
    print(f"sim points       = {len(T)}, t_end = {fmt_time(T[-1])}")
    print(f"-- with adhesive H2O outgassing (85 C, A={OG_A0:g} cm^2, V={OG_V0:g} cm^3) --")
    print(f"q(1 h): pre-depletion {OG_C0*math.sqrt(OG_D85/(math.pi*3600.0)):.2e}, effective {q_og(3600.0)/OG_A0:.2e} Torr*L/s/cm^2; reservoir {OG_V0*OG_C0:.1f} Torr*L; "
          f"tau1 = {og_tau1(OG_A0, OG_V0)/3600:.2f} h (L = {OG_V0/OG_A0*10:.2f} mm)")
    T, P1, P2, W1, W2 = simulate(P0, St, d, L, V1, V2, og=True)
    t_bn = time_to_reach(T, P2, TARGET)
    print(f"t to 1e-6 Torr   = {fmt_time(t_bn)}  (None = not reached by {fmt_time(T[-1])})")
    print(f"chamber end      = {P2[-1]:.3g} Torr total, H2O {W2[-1]:.3g} Torr")
    print(f"H2O at RGA       = {W1[-1]:.3g} Torr  (attenuation x{W2[-1]/W1[-1]:,.0f})")
    print("-- wall/manifold water always on: hot-wall pool "
          f"{DW_I0:.2e} Torr*L (tau 30 min); manifold q(1 h) = {q_man(3600.0):.2e} Torr*L/s --")
    print("-- with 1e-6 Torr*L/s air leak --")
    T, P1, P2, _, _ = simulate(P0, St, d, L, V1, V2, lk=True, Ql=1e-6)
    cm = cond_mol(d, L)
    print(f"floor P2 = {P2[-1]:.3g} Torr vs predicted Q/S_eff = {1e-6*(1/St + 1/cm):.3g} Torr "
          f"(He-test equivalent {1e-6*2.69/0.76:.2e} atm cc/s)")


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
        ("Turbo plateau (L/s)", 5, 2000, 84),
        ("Tube diameter (cm)", 0.2, 10, 1.0),
        ("Tube length (cm)", 2, 30, 10),
        ("Manifold volume (L)", 0.5, 20, 2),
        ("Chamber volume (L)", 5, 1000, 100),
        ("Adhesive exposed area (cm²)", 1, 100, 20),
        ("Adhesive volume (cm³)", 0.02, 2, 0.5),
    ]
    for i, (lab, lo, hi, d0) in enumerate(specs):
        ax = fig.add_axes([0.30, 0.245 - i * 0.030, 0.55, 0.020])
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
    ck = CheckButtons(ax_ck, ["Adhesive H2O, 85 C\n(area/volume sliders)"], [False])

    def update(_=None):
        P0, St, d, L, V1, V2, ogA, ogV = (10 ** s.val for s in sliders)
        og = ck.get_status()[0]
        for s, (lab, *_r) in zip(sliders, specs):
            s.valtext.set_text(f"{10**s.val:,.3g}")
        T, P1, P2, W1, W2 = simulate(P0, St, d, L, V1, V2, og, ogA, ogV)
        Xi, Yi = ideal_sim(P0, St, V1 + V2, og, ogA, ogV)
        t_id_curve = [max(Yi[min(range(len(Xi)), key=lambda i: abs(math.log(Xi[i]) - math.log(max(t, 1e-7))))], 1e-12)
                      for t in T]
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
