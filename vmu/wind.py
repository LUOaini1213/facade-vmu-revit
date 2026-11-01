"""Wind on the mock-up: EN 1991-1-4 peak velocity pressure and free-standing-wall net pressures.

The mock-up is an open steel frame with an L-shaped facade on it: wind reaches both faces of the
cladding, so the facade is treated as a free-standing wall with a return corner (EN 1991-1-4 7.4.1)
and the frame members as individual members with force coefficients (7.6, 7.9).

Every value that comes from the standard or a national annex is in PARAMS with its clause; the
ones a designer chooses are marked as choices. Standard library only.
"""
import math

from . import config as C

PARAMS = {
    # [code] SS EN 1991-1-4 NA (Singapore): fundamental basic wind velocity, 10-min mean at 10 m, terrain II
    "vb0": 20.0,
    "rho": 1.25,            # [code] EN 1991-1-4 4.5(1) Note 2, recommended air density (kg/m3)
    "c_dir": 1.0,           # [code] 4.2(2) Note 2 recommended; [choice] all directions
    "c_season": 1.0,        # [code] recommended
    "c_prob": 1.0,          # [choice] no reduction for the mock-up's short life (conservative)
    "z0": 0.05,             # [code] Table 4.1, terrain category II (m)
    "z0_II": 0.05,          # [code] 4.3.2
    "zmin": 2.0,            # [code] Table 4.1, category II (m)
    "k_I": 1.0,             # [code] 4.4(1) Note 2 recommended
    "c_o": 1.0,             # [choice] flat site, no orography
    "cf_square": 2.0,       # [code] 7.6, Figure 7.23 for d/b = 1 with sharp-ish corners, psi_lambda = 1
    "cf_circle": 1.2,       # [code] 7.9, cylinders at subcritical Reynolds numbers
}

# EN 1991-1-4 Table 7.9, solidity 1: zone coefficients for l/h <= 3, 5, >= 10 (no return corners)
# and with return corners of length >= h. [code] -- verified against the standard's text (see README).
TABLE_7_9 = {
    3.0: {"A": 2.3, "B": 1.4, "C": 1.2, "D": 1.2},
    5.0: {"A": 2.9, "B": 1.8, "C": 1.4, "D": 1.2},
    10.0: {"A": 3.4, "B": 2.1, "C": 1.7, "D": 1.2},
    "return": {"A": 2.1, "B": 1.8, "C": 1.4, "D": 1.2},
}
ZONES = [("A", 0.3), ("B", 2.0), ("C", 4.0), ("D", float("inf"))]   # zone ends, multiples of h from the free end


def peak_pressure(z, p=PARAMS):
    """q_p(z) in kPa (EN 1991-1-4 4.5, with 4.3 and 4.4)."""
    vb = p["c_dir"] * p["c_season"] * p["c_prob"] * p["vb0"]
    zz = max(z, p["zmin"])
    kr = 0.19 * (p["z0"] / p["z0_II"]) ** 0.07
    cr = kr * math.log(zz / p["z0"])
    vm = cr * p["c_o"] * vb
    Iv = p["k_I"] / (p["c_o"] * math.log(zz / p["z0"]))
    return (1 + 7 * Iv) * 0.5 * p["rho"] * vm * vm / 1000.0


def _no_return(lh):
    keys = [3.0, 5.0, 10.0]
    if lh <= 3.0:
        return dict(TABLE_7_9[3.0])
    if lh >= 10.0:
        return dict(TABLE_7_9[10.0])
    lo = max(k for k in keys if k <= lh)
    hi = min(k for k in keys if k >= lh)
    if lo == hi:
        return dict(TABLE_7_9[lo])
    t = (lh - lo) / (hi - lo)
    return {z: TABLE_7_9[lo][z] + t * (TABLE_7_9[hi][z] - TABLE_7_9[lo][z]) for z in "ABCD"}


def zone_coefficients(length, height, return_length):
    """c_p,net per zone for a solid wall of `length` and `height` whose far end has a return corner
    of `return_length` (0 = free end). Between 0 and h the note to Table 7.9 allows linear
    interpolation between the rows without and with return corners."""
    base = _no_return(length / height)
    if return_length <= 0:
        return base
    t = min(return_length / height, 1.0)
    ret = TABLE_7_9["return"]
    return {z: base[z] + t * (ret[z] - base[z]) for z in "ABCD"}


def cp_net_along(s, height, coeffs):
    """Coefficient at distance s from the free end."""
    for zone, end in ZONES:
        if s < end * height:
            return coeffs[zone], zone
    return coeffs["D"], "D"
