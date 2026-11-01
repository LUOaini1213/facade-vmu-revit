"""Weights of every facade part, and what each anchor receives from the units.

Weights come from the geometry: an extrusion weighs its profile area x length x density, glass and
panels their volume x density. So the dead load the frame carries is the dead load of the parts that
are modelled, and it changes when a profile or a glass make-up changes. After the Revit model exists,
tests compare these weights with the material volumes Revit reports for the same elements.

Anchor loads are given per (level, anchor id) as characteristic forces in face axes:
  G   vertical dead load (kN, downward positive)
  Hg  horizontal force from the unit's weight hanging eccentrically (kN, + into the mock-up)
  and wind reactions per wind direction (kN, + into the mock-up).
Standard library only.
"""
import math

from . import config as C
from . import extrusions as X
from . import geometry as G
from . import profiles as P

GRAV = 9.81e-3                 # kN per kg
ALLOWANCE = 1.05               # [assumption] gaskets, sealant, setting blocks, fixings: +5 %

_PROFILE_AREA = {}


def profile_area(name):
    if name not in _PROFILE_AREA:
        _PROFILE_AREA[name] = P.props(X.catalogue()[name][0])["A"]
    return _PROFILE_AREA[name]


def _panel_mass(part):
    area = part["width"] * part["height"] * 1e-6                  # m2
    k = part["kind"]
    if k == "igu":
        return area * (C.IGU[0] + C.IGU[2]) * 1e-3 * C.GLASS_DENSITY
    if k == "glass":
        return area * part["thickness"] * 1e-3 * C.GLASS_DENSITY
    if k in ("panel", "backpan"):
        return area * part["thickness"] * 1e-3 * C.ALUMINIUM["density"]
    if k == "insulation":
        return area * part["thickness"] * 1e-3 * C.INSULATION_DENSITY
    raise ValueError(k)


def _section_centroid(name):
    pr = P.props(X.catalogue()[name][0])
    return pr["ca"], pr["cb"]


def part_mass_and_centre(part):
    """Mass (kg) and centre of mass in face coordinates (u, w, z) of one unit part."""
    face = part["face"]
    if part["kind"] == "extrusion":
        m = profile_area(part["profile"]) * 1e-6 * part["length"] * 1e-3 * C.ALUMINIUM["density"]
        ca, cb = _section_centroid(part["profile"])
        u0, w0, z0 = _to_face(face, part["origin"])
        if part["horizontal"]:        # section: a vertical, b depth; extruded along +u
            return m, (u0 + part["length"] / 2.0, w0 + cb, z0 + ca)
        return m, (u0 + ca, w0 + cb, z0 + part["length"] / 2.0)
    m = _panel_mass(part)
    u0, w0, z0 = _to_face(face, part["origin"])
    return m, (u0 + part["width"] / 2.0, part["w0"] + part["thickness"] / 2.0, z0 + part["height"] / 2.0)


def _to_face(face, xyz):
    x, y, z = xyz
    if face == "A":
        return x, y, z
    return -y, x, z


def unit_mass(unit):
    """Total mass (kg, with the allowance) and centre (u, w, z) of a unit."""
    tot = 0.0
    mu = mw = mz = 0.0
    for part in unit["parts"]:
        m, (u, w, z) = part_mass_and_centre(part)
        tot += m
        mu += m * u
        mw += m * w
        mz += m * z
    return tot * ALLOWANCE, (mu / tot, mw / tot, mz / tot)


def anchor_id(level, face, u, kind):
    if kind == "corner":
        return "BRK-%s-CORNER" % level
    return "BRK-%s-%s%+06.0f" % (level, face, u)


HOOK_Z = C.BRACKET_HOOK_Z0 + C.BRACKET_HOOK[2] / 2.0          # hook bar centre above floor level: 86
HOOK_W = C.BRACKET_HOOK_W0 + C.BRACKET_HOOK[1] / 2.0          # hook bar centre behind the glass plane: 200


def _support_levels(storey):
    s = next(s for s in C.STOREYS if s[0] == storey)
    return s[1], s[2]


def _edge_anchor(face, u_edge, kind):
    """(kind, u of the hook) that carries one unit edge: the joint itself; at a free end the end
    anchor, inset as in geometry.anchor_lines (face A ends at +u, face B at -u); next to the corner
    post the jamb's tube centre, whose load goes to the corner anchor."""
    if kind == "joint":
        return "joint", u_edge
    if kind == "end":
        return "end", (u_edge - G.END_INSET) if face == "A" else (u_edge + G.END_INSET)
    sign = 1.0 if face == "A" else -1.0
    return "corner", u_edge + sign * (G.J + C.MULLION_W / 2.0)


def unit_anchor_loads(unit, wind_pressure=None):
    """Loads one unit puts on anchors, as a list of (level, anchor id, face, G, Hg, W).

    Dead load: the unit hangs from the anchors at its top level, shared between its two edges by the
    lever rule on its centre of mass. Its weight acts in front of the hook line, so the unit leans:
    the top hooks pull out and the bottom (the stack joint, carried by the anchors at the bottom
    level) pushes in, by G * (hook_w - cg_w) / (hook_z - stack_z).
    Wind: `wind_pressure(u) -> kPa` (+ into the mock-up) over the unit's module; the mullions span
    from the stack joint at the bottom to the hook at the top, so the reactions follow statics."""
    lo, hi, lo_kind, hi_kind = G.unit_edges(unit["face"], unit["index"])
    kl, ul = _edge_anchor(unit["face"], lo, lo_kind)
    kh, uh = _edge_anchor(unit["face"], hi, hi_kind)
    bot, top = _support_levels(unit["storey"])
    mass, (ucg, wcg, zcg) = unit_mass(unit)
    Gk = mass * GRAV
    share_hi = (ucg - ul) / (uh - ul)
    share = {"lo": 1.0 - share_hi, "hi": share_hi}
    z_hook = C.LEVELS[top] + HOOK_Z
    z_stack = C.LEVELS[bot] + C.STACK_ABOVE_FL
    lean = Gk * (HOOK_W - wcg) / (z_hook - z_stack)
    out = []
    for side, kind, u in (("lo", kl, ul), ("hi", kh, uh)):
        out.append((top, anchor_id(top, unit["face"], u, kind), unit["face"], Gk * share[side], -lean * share[side], 0.0))
        out.append((bot, anchor_id(bot, unit["face"], u, kind), unit["face"], 0.0, lean * share[side], 0.0))
    if wind_pressure is not None:
        # tributary strip: joint line to joint line (the module), stack joint to stack joint (4.0 m)
        z0 = C.LEVELS[bot] + C.STACK_ABOVE_FL
        h = C.LEVELS[top] - C.LEVELS[bot]
        n = 40
        du = (hi - lo) / n
        F = Fu = 0.0
        for k in range(n):
            u = lo + (k + 0.5) * du
            f = wind_pressure(u) * du * 1e-3 * h * 1e-3
            F += f
            Fu += f * u
        uc = Fu / F if F else 0.5 * (lo + hi)
        top_frac = (h / 2.0) / (z_hook - z0)                         # moment about the stack joint
        s_hi = (uc - ul) / (uh - ul)
        for side, kind, u, sh in (("lo", kl, ul, 1.0 - s_hi), ("hi", kh, uh, s_hi)):
            out.append((top, anchor_id(top, unit["face"], u, kind), unit["face"], 0.0, 0.0, F * top_frac * sh))
            out.append((bot, anchor_id(bot, unit["face"], u, kind), unit["face"], 0.0, 0.0, F * (1 - top_frac) * sh))
    return out
