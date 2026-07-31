# Vacuum Physics Models

Interactive and scripted physics models of vacuum systems.

## Contents

- **[bottleneck_pumpdown.html](bottleneck_pumpdown.html)** — interactive, self-contained teaching model of pumping down a chamber through a conductance bottleneck (open in any browser). Python twin: [bottleneck_pumpdown.py](bottleneck_pumpdown.py) (`--check` for a headless numeric report).

  **There is no pump-speed input anywhere.** You pick the hardware from a dropdown and the model reads the speed off that pump's own published curve at whatever pressure it currently sees. Starting pressure is likewise fixed at **760 Torr**.

  | | Rough | Turbo |
  |---|---|---|
  | Options | Edwards **nXDS10iC** (dry scroll) or Adixen/Pfeiffer **ACP 15** (multi-stage Roots) | Edwards **nEXT300D** |
  | Peak speed | 11.4 m³/h = 3.17 L/s · 15 m³/h = 4.17 L/s | 300 L/s N₂ (340 He, 280 H₂) |
  | Ultimate | 7×10⁻³ mbar (4×10⁻² ballast open) · 5×10⁻² mbar | 6×10⁻⁸ mbar |
  | Limit that bends the curve | back-leakage past the seals: `S = S_peak·(1 − P_ult/P)` | throughput: `S = min(S_rated, Q_max/P)`, Q_max = 115 sccm |

  Because the two curves have different shapes, the pump set behaves differently at each end. The rougher is flat from atmosphere until about a decade above its ultimate, then falls off a cliff — at a 100 mTorr crossover the nXDS10iC is still at 95 % of peak but the ACP 15, whose ultimate is much closer, is down to 62 %. The turbo is the mirror image: throughput-limited to `Q_max/P` at crossover (about 33 L/s of its 300), reaching full speed only below `Q_max/S_rated = 4.9 mTorr`.

  The two stages are coupled, not independent. The rougher has to swallow the turbo's exhaust, so the model solves the foreline pressure where `S_rough(P_fore)·P_fore = Q_turbo` and checks it against the nEXT300D's 9.5 mbar critical backing pressure. At default geometry the peak foreline is ~0.47 Torr, about 7 % of budget — the nXDS10iC backs the turbo comfortably.

  Knobs: crossover pressure (default 100 mTorr; standard practice 50–150 mTorr), tube bore and length, manifold and chamber volume, gas ballast, and an optional adhesive-H₂O outgassing source.

- **[dewar_vacuum_model/](dewar_vacuum_model/)** — Python model of vacuum bakeout, sealed vacuum life, and cooldown for an infrared detector dewar. See its [README](dewar_vacuum_model/README.md) for usage.
