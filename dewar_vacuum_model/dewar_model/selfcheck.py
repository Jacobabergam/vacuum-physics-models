"""Physics self-checks. Run:  python3 -m dewar_model.selfcheck
Asserts the model reproduces known anchors; prints PASS/FAIL per check."""
import numpy as np
from .constants import MG_H2O_TORRL, DAY
from .gas import SPECIES
from .outgassing import SurfaceWater, Adhesive, slab_remaining_frac
from .cooldown import cp_cu, enthalpy_cu_J

checks = []


def check(name, ok, detail=""):
    checks.append(ok)
    print(f"  [{'PASS' if ok else 'FAIL'}] {name} {detail}")


def main():
    print("dewar_model self-checks")

    # 1. free-molecular coefficient for air (Corruccini): ~1.17-1.18 W/m2/K/Pa at 295 K
    lam = SPECIES["air"].lambda0()
    check("Lambda0(air, 295K) ~ 1.18", abs(lam - 1.18) < 0.02, f"(got {lam:.3f})")

    # 2. surface model reproduces empirical 1/t water law (CERN: ~2.2e-9 torr·L/s/cm2 at 1 h)
    sw = SurfaceWater(area_cm2=1.0, monolayers=3.0)
    q1 = sw.rate_torrL_s(3600.0, 295.0)
    q10 = sw.rate_torrL_s(36000.0, 295.0)
    check("q_H2O(1 h) within x3 of 2.2e-9 torr·L/s/cm2", 0.7e-9 < q1 < 6.6e-9, f"(got {q1:.2e})")
    check("1/t slope: q(1h)/q(10h) ~ 10", 8.0 < q1 / q10 < 12.5, f"(got {q1/q10:.1f})")

    # 3. unit anchor: 1 mg water ~ 1.02 torr·L at 295 K
    check("1 mg H2O ~ 1.02 torr·L", abs(MG_H2O_TORRL - 1.02) < 0.02, f"(got {MG_H2O_TORRL:.3f})")

    # 4. slab kinetics: bounds, monotonicity, composite two-stage consistency
    X = np.array([0.0, 0.1, 1.0, 5.0])
    f = slab_remaining_frac(X)
    check("slab f(0)=1, decreasing", abs(f[0] - 1) < 1e-6 and np.all(np.diff(f) < 0))
    a = Adhesive("t", volume_cm3=0.1, exposed_area_cm2=2.0)
    r_all = a.released_after_seal_mg(2 * DAY, 358.15, 1e9, 295.0)[0]
    m_left = a.remaining_mg(2 * DAY, 358.15)
    check("two-stage release converges to post-bake inventory",
          abs(r_all - m_left) / m_left < 1e-3, f"(rel {r_all:.4f} vs left {m_left:.4f} mg)")

    # 5. L_eff = V/A
    check("L_eff = volume/exposed_area", abs(a.L_eff - 0.05) < 1e-9, f"(got {a.L_eff} cm)")

    # 6. Debye copper cp: 300 K within 5% of 385, 80 K within 12% of 205 J/kg/K
    check("cp_Cu(300 K) ~ 385 J/kg/K (Debye -3%)", abs(cp_cu(300) - 385) / 385 < 0.05,
          f"(got {cp_cu(300):.0f})")
    check("cp_Cu(80 K) ~ 205 J/kg/K (±12%)", abs(cp_cu(80) - 205) / 205 < 0.12,
          f"(got {cp_cu(80):.0f})")

    # 7. cooldown energy sanity: 15 g Cu 293->80 K enthalpy ~ 1 kJ (0.7-1.3)
    H = enthalpy_cu_J(0.015, 80, 293)
    check("enthalpy 15 g Cu 293->80 K ~ 1 kJ", 700 < H < 1300, f"(got {H:.0f} J)")

    n = sum(checks)
    print(f"\n{n}/{len(checks)} checks passed")
    if n != len(checks):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
