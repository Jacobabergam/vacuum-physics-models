# Vacuum Physics Models

Interactive and scripted physics models of vacuum systems.

## Contents

- **[bottleneck_pumpdown.html](bottleneck_pumpdown.html)** — interactive, self-contained teaching model of pumping down a chamber through a conductance bottleneck (open in any browser). Python twin: [bottleneck_pumpdown.py](bottleneck_pumpdown.py) (`--check` for a headless numeric report).

  Fixed hardware, so neither is a slider: every run starts at **760 Torr**, and the pump is an **Edwards nXDS10iC** dry scroll — peak speed **11.4 m³/h (6.7 cfm, 3.17 L/s)**, displacement 12.7 m³/h at 1,800 rpm, ultimate **7×10⁻³ mbar** with gas ballast closed and **4×10⁻² mbar** open. The "C" is the corrosion-resistant build; its speed and ultimate match the plain nXDS10i.

  Speed is not constant, and the model leans on that: back-leakage past the tip seals grows as the inlet falls, so `S = 3.17·(1 − P_ult/P)` — flat from atmosphere to about 0.1 Torr (95 % of peak), then off a cliff: 74 % at 20 mTorr, 47 % at 10 mTorr, zero at ultimate.

  This pump alone does not reach high vacuum, so the model targets the pressure where you would valve in a turbo or cryo — 50–150 mTorr is standard crossover practice. Knobs: target pressure (default 100 mTorr), tube bore and length, manifold and chamber volume, gas ballast, and an optional adhesive-H₂O outgassing source.
- **[dewar_vacuum_model/](dewar_vacuum_model/)** — Python model of vacuum bakeout, sealed vacuum life, and cooldown for an infrared detector dewar. See its [README](dewar_vacuum_model/README.md) for usage.
