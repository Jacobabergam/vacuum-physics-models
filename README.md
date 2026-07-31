# Vacuum Physics Models

Interactive and scripted physics models of vacuum systems.

## Contents

- **[bottleneck_pumpdown.html](bottleneck_pumpdown.html)** — interactive, self-contained teaching model of pumping down a chamber through a conductance bottleneck (open in any browser). Python twin: [bottleneck_pumpdown.py](bottleneck_pumpdown.py) (`--check` for a headless numeric report).

  Fixed hardware, so neither is a slider: every run starts at **760 Torr**, and the pump set is a **10iC cryopump** (3,000 L/s air, 9,000 L/s H₂O, 5,000 L/s H₂; 19 Torr·L/s max throughput; 300 Torr·L crossover rating; 10⁻⁹ Torr ultimate) behind a **10 cfm / 4.7 L/s rough pump** with a 20 mTorr blank-off. Both pumps have pressure-dependent speed and the model leans on that: the rougher chokes off approaching blank-off, and the cryo is heat-load throttled to `S = 19/P` until the chamber falls below `Q_max/S_max = 6.3 mTorr`. At a standard 100 mTorr crossover the 10iC therefore delivers roughly 190 L/s at its inlet — about 6 % of its rating — and only reaches 3,000 L/s in the low 10⁻³ decade.

  Remaining knobs: crossover pressure (default 100 mTorr; industry practice is 50–150 mTorr), tube bore and length, manifold and chamber volume, and an optional adhesive-H₂O outgassing source.
- **[dewar_vacuum_model/](dewar_vacuum_model/)** — Python model of vacuum bakeout, sealed vacuum life, and cooldown for an infrared detector dewar. See its [README](dewar_vacuum_model/README.md) for usage.
