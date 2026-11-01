"""Structural hollow sections (cold-formed, EN 10219) and their properties.

Every property is integrated from the exact outline (profiles.py) with the corner radii that
EN 10219-2 uses for calculating properties; closed-form formulas are used only for the torsion
constants, where they are the definition. The same outline is what the Revit families extrude.

Designations: "SHS b x b x t", "RHS h x b x t" (h = depth, in the plane of the major axis y-y),
"CHS d x t". Local axes as in EN 1993: y-y major axis (bending about y deflects along the depth h),
z-z minor axis.

Standard library only.
"""
import math
import re

from . import config as C
from . import profiles as P

STEEL_DENSITY = C.STEEL["density"]


def radii(t):
    """(outer, inner) corner radius EN 10219-2 assumes for section properties of cold-formed
    square/rectangular hollow sections (Annex B, by wall thickness band)."""
    if t <= 6.0:
        return 2.0 * t, 1.0 * t
    if t <= 10.0:
        return 2.5 * t, 1.5 * t
    return 3.0 * t, 2.0 * t


def parse(designation):
    m = re.match(r"^(SHS|RHS|CHS)\s+([\d.]+)x([\d.]+)(?:x([\d.]+))?$", designation.strip())
    if not m:
        raise ValueError("unknown section %r" % designation)
    kind = m.group(1)
    nums = [float(g) for g in m.groups()[1:] if g is not None]
    if kind == "CHS":
        d, t = nums
        return {"kind": kind, "d": d, "t": t}
    if kind == "SHS":
        if len(nums) == 3:
            h, b, t = nums
        else:
            h, t = nums
            b = h
        if abs(h - b) > 1e-9:
            raise ValueError("SHS must be square: %r" % designation)
        return {"kind": kind, "h": h, "b": b, "t": t}
    h, b, t = nums
    return {"kind": kind, "h": h, "b": b, "t": t}


def outline(designation):
    """Loops (outer CCW, inner CW) in section axes: a = z direction (width b), b = y direction
    (depth h), centred on the origin. For CHS the circle of diameter d."""
    s = parse(designation)
    if s["kind"] == "CHS":
        r, t = s["d"] / 2.0, s["t"]
        return [P.orient(P.circle(0.0, 0.0, r), True), P.orient(P.circle(0.0, 0.0, r - t), False)]
    h, b, t = s["h"], s["b"], s["t"]
    ro, ri = radii(t)
    return [P.orient(P.rounded_rect(-b / 2, -h / 2, b / 2, h / 2, ro), True),
            P.orient(P.rounded_rect(-b / 2 + t, -h / 2 + t, b / 2 - t, h / 2 - t, ri), False)]


def _rhs_torsion(h, b, t, ro, ri):
    """Torsion constant I_t and torsional modulus W_t of a closed rectangular hollow section
    (EN 10219-2 Annex B): median-line enclosed area A_h and perimeter p with the mean radius
    r_m = (ro + ri) / 2; I_t = t^3 p / 3 + 2 k A_h, k = 2 A_h t / p, W_t = I_t / (t + k / t)."""
    rm = (ro + ri) / 2.0
    p = 2 * ((b - t) + (h - t)) - 2 * rm * (4 - math.pi)
    Ah = (b - t) * (h - t) - rm * rm * (4 - math.pi)
    k = 2 * Ah * t / p
    It = t ** 3 * p / 3.0 + 2 * k * Ah
    Wt = It / (t + k / t)
    return It, Wt


def properties(designation):
    """Properties in mm units: A (mm2), mass (kg/m), Iy, Iz (mm4), Wel_y, Wel_z, Wpl_y, Wpl_z (mm3),
    It (mm4), Wt (mm3), iy, iz (mm), Av_y/Av_z (shear areas, mm2), plus the input dimensions."""
    s = parse(designation)
    loops = outline(designation)
    pr = P.props(loops)
    A = pr["A"]
    if s["kind"] == "CHS":
        d, t = s["d"], s["t"]
        I = pr["Iaa"]
        Wel = I / (d / 2.0)
        Wpl = (d ** 3 - (d - 2 * t) ** 3) / 6.0
        It, Wt = 2 * I, 2 * Wel
        out = {"Iy": I, "Iz": I, "Wel_y": Wel, "Wel_z": Wel, "Wpl_y": Wpl, "Wpl_z": Wpl, "It": It, "Wt": Wt,
               "Av_y": 2 * A / math.pi, "Av_z": 2 * A / math.pi}
    else:
        h, b, t = s["h"], s["b"], s["t"]
        ro, ri = radii(t)
        Iy, Iz = pr["Iaa"], pr["Ibb"]          # a = width direction, b = depth: Iaa integrates depth^2
        It, Wt = _rhs_torsion(h, b, t, ro, ri)
        out = {"Iy": Iy, "Iz": Iz, "Wel_y": Iy / (h / 2.0), "Wel_z": Iz / (b / 2.0),
               "Wpl_y": P.plastic_modulus(loops, 1), "Wpl_z": P.plastic_modulus(loops, 0),
               "It": It, "Wt": Wt,
               # EN 1993-1-1 6.2.6(3)(c): shear parallel to the depth A h / (b + h), to the width A b / (b + h)
               "Av_z": A * h / (b + h), "Av_y": A * b / (b + h)}
    out.update({"designation": designation, "kind": s["kind"], "A": A, "mass": A * 1e-6 * STEEL_DENSITY,
                "iy": math.sqrt(out["Iy"] / A), "iz": math.sqrt(out["Iz"] / A)})
    out.update({k: s[k] for k in s if k != "kind"})
    return out


def epsilon(fy):
    return math.sqrt(235.0 / fy)


def classify(designation, fy, mode):
    """Cross-section class (1..4) of a hollow section in pure compression ("N") or pure bending
    about y ("My") / z ("Mz"), EN 1993-1-1 Table 5.2. RHS flat widths c = h - 3t, b - 3t."""
    s = parse(designation)
    eps = epsilon(fy)
    if s["kind"] == "CHS":
        r = s["d"] / s["t"]
        limits = (50 * eps ** 2, 70 * eps ** 2, 90 * eps ** 2)
    else:
        h, b, t = s["h"], s["b"], s["t"]
        if mode == "N":
            r = max(h, b) / t - 3.0
            limits = (33 * eps, 38 * eps, 42 * eps)
        else:
            # the compression flange is internal and in compression; the webs are in bending
            flange = (b if mode == "My" else h) / t - 3.0
            web = (h if mode == "My" else b) / t - 3.0
            cls_f = next((k + 1 for k, lim in enumerate((33 * eps, 38 * eps, 42 * eps)) if flange <= lim), 4)
            cls_w = next((k + 1 for k, lim in enumerate((72 * eps, 83 * eps, 124 * eps)) if web <= lim), 4)
            return max(cls_f, cls_w)
    return next((k + 1 for k, lim in enumerate(limits) if r <= lim), 4)
