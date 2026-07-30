"""Physical constants and unit conversions.

Unit conventions throughout the package:
    pressure   : torr   (1 torr = 133.322 Pa)
    gas amount : torr·L (at the stated accounting temperature, default 295 K)
    length     : cm inside outgassing code, m inside heat-transfer code (noted per function)
    time       : s      (helpers for day/year)
    energy     : eV for activation/binding energies, J for heat
"""

KB_EV = 8.617333e-5          # Boltzmann constant, eV/K
KB_J = 1.380649e-23          # Boltzmann constant, J/K
R_GAS = 8.314462             # molar gas constant, J/(mol K)
NA = 6.02214076e23           # Avogadro, 1/mol
SIGMA_SB = 5.670374e-8       # Stefan-Boltzmann, W/(m^2 K^4)
TORR_PA = 133.322            # Pa per torr
DAY = 86400.0                # s
YEAR = 3.156e7               # s
T_ACCOUNT = 295.0            # K, temperature at which torr·L amounts are accounted

M_H2O = 18.015e-3            # kg/mol
M_CU = 63.546e-3             # kg/mol
THETA_D_CU = 343.0           # K, Debye temperature of copper (Kittel, Intro. Solid State Physics)


def molecules_per_torrL(T=T_ACCOUNT):
    """Ideal-gas molecule count in 1 torr·L at temperature T."""
    return TORR_PA * 1e-3 / (KB_J * T)


# 1 monolayer of water ~ 1e15 molecules/cm^2  (Redhead-class assumption)
ML_TORRL_PER_CM2 = 1e15 / molecules_per_torrL()

# 1 mg of water expressed as torr·L at the accounting temperature
MG_H2O_TORRL = 1e-3 / (M_H2O * 1e3) * NA / molecules_per_torrL()  # ~1.02 torr·L/mg
