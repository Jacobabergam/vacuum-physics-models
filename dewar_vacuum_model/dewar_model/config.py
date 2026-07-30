"""Config loading and validation. Configs are YAML files — see configs/ for
commented examples."""
import yaml

REQUIRED = [
    "shell_temp_K", "cold_temp_K", "cold_area_cm2", "gap_mm",
    "steel_area_cm2", "free_volume_L", "p_crit_torr",
    "surface_water", "adhesives", "fixed_gases", "getter",
    "cooler", "thermal", "bake",
]


import re

_FLOATISH = re.compile(r"^[-+]?(\d+\.?\d*|\.\d+)([eE][-+]?\d+)?$")


def _coerce(obj):
    """PyYAML parses '1.0e13' (unsigned exponent) as a string; coerce such
    numeric-looking strings back to float, recursively."""
    if isinstance(obj, dict):
        return {k: _coerce(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_coerce(v) for v in obj]
    if isinstance(obj, str) and _FLOATISH.match(obj.strip()):
        return float(obj)
    return obj


def load_config(path):
    with open(path) as f:
        cfg = _coerce(yaml.safe_load(f))
    missing = [k for k in REQUIRED if k not in cfg]
    if missing:
        raise KeyError(f"config {path} missing keys: {missing}")
    for i, a in enumerate(cfg["adhesives"]):
        for k in ("name", "volume_cm3", "exposed_area_cm2"):
            if k not in a:
                raise KeyError(f"adhesives[{i}] missing '{k}'")
    return cfg
