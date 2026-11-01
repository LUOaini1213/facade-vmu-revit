"""The aluminium extrusions of the unitised frame, drawn from the numbers in config.

Every profile is of this project's own design (proportions typical of a capped unitised system,
not copied from any supplier or project). Section coordinates (a, b):
  b = depth, 0 at the outer face of the glass, positive into the building;
  a = across the member, measured from the joint centreline (mullions: along the facade,
      positive into the member's own unit; transoms: vertical, positive up).

Mullions are split at each vertical joint: the unit on the +a side of a joint carries the male
half (a tongue that crosses the joint), the unit on the -a side the female half (two slot legs
that take the tongue). Head and sill transoms interlock the same way across the stack joint.
The clearances around the tongue are INTERLOCK_CLEAR; tests measure them on the outlines.

Standard library only (imported inside Revit).
"""
import math

from . import config as C
from . import profiles as P

J = C.JOINT / 2.0                 # 7.5: joint face of every half member
TF = C.TUBE_FACE                  # 35: tube face behind the glass
W = C.WALL
CL = C.INTERLOCK_CLEAR
TONGUE_T = 6.0                    # tongue thickness
LEG_T = 5.0                       # slot leg thickness
REACH = J - CL                    # tongue tip / leg tip beyond the joint centreline: 4.5


def _tongue_band(depth):
    mid = TF + depth / 2.0
    return mid - TONGUE_T / 2.0, mid + TONGUE_T / 2.0


def _leg_bands(depth):
    t0, t1 = _tongue_band(depth)
    return (t0 - CL - LEG_T, t0 - CL), (t1 + CL, t1 + CL + LEG_T)


def _stem(width):
    """Stem position: centred between the joint face and the glass edge."""
    glass_edge = J + width - C.BITE
    mid = 0.5 * (J + glass_edge)
    return mid - C.STEM / 2.0, mid + C.STEM / 2.0


def male(width, depth):
    """Half member on the +a side of a joint, with the tongue. Tube a in [J, J+width]; the cap
    covers the tube face and the glass edge from outside, carried by the stem."""
    a1 = J + width
    b1 = TF + depth
    s0, s1 = _stem(width)
    t0, t1 = _tongue_band(depth)
    pts = [(J, -C.CAP), (a1, -C.CAP), (a1, 0.0), (s1, 0.0), (s1, TF), (a1, TF), (a1, b1), (J, b1),
           (J, t1), (-REACH, t1), (-REACH, t0), (J, t0), (J, TF), (s0, TF), (s0, 0.0), (J, 0.0)]
    outer = P.orient(P.polygon(pts), True)
    hole = P.orient(P.rect(J + W, TF + W, a1 - W, b1 - W), False)
    return [outer, hole]


def female(width, depth):
    """Half member on the -a side of a joint, with two slot legs. Tube a in [-J-width, -J]."""
    a0 = -J - width
    b1 = TF + depth
    s0, s1 = (-x for x in reversed(_stem(width)))
    (l0, l1), (l2, l3) = _leg_bands(depth)
    pts = [(a0, -C.CAP), (-J, -C.CAP), (-J, 0.0), (s1, 0.0), (s1, TF),
           (-J, TF), (-J, l0), (REACH, l0), (REACH, l1), (-J, l1), (-J, l2), (REACH, l2), (REACH, l3), (-J, l3),
           (-J, b1), (a0, b1), (a0, TF), (s0, TF), (s0, 0.0), (a0, 0.0)]
    outer = P.orient(P.polygon(pts), True)
    hole = P.orient(P.rect(a0 + W, TF + W, -J - W, b1 - W), False)
    return [outer, hole]


def jamb(width, depth, plate=2.5):
    """Edge member with no neighbour (at the corner post and at the free ends): the male tube and
    cap without a tongue, closed on the joint face (a = J, so the joint stays 15 mm) by a plate
    from the cap line to the tube; the space behind the cap becomes a pocket."""
    a1 = J + width
    b1 = TF + depth
    s0, s1 = _stem(width)
    outer = P.orient(P.polygon([(J, -C.CAP), (a1, -C.CAP), (a1, 0.0), (s1, 0.0), (s1, TF), (a1, TF),
                                (a1, b1), (J, b1)]), True)
    pocket = P.orient(P.rect(J + plate, 0.0, s0, TF), False)
    hole = P.orient(P.rect(J + W, TF + W, a1 - W, b1 - W), False)
    return [outer, pocket, hole]


def jamb_end(width, depth):
    """The jamb for the +u edge of a unit: the same extrusion turned end for end, which in the
    section is a mirror about the joint centreline."""
    return [P.mirror_a(loop) for loop in jamb(width, depth)]


def mid_transom(height, depth):
    h = height / 2.0
    b1 = TF + depth
    s = C.STEM / 2.0
    outer = P.orient(P.polygon([(-h, -C.CAP), (h, -C.CAP), (h, 0.0), (s, 0.0), (s, TF), (h, TF), (h, b1),
                                (-h, b1), (-h, TF), (-s, TF), (-s, 0.0), (-h, 0.0)]), True)
    hole = P.orient(P.rect(-h + W, TF + W, h - W, b1 - W), False)
    return [outer, hole]


def corner_post():
    """Square tube at the outside corner. Section axes: a = X, b = Y of the model (glass planes at
    X = 0 and Y = 0); outer faces flush with the caps, joint faces toward units A1 and B1, and a
    20 mm chamfer on the outside arris."""
    o = -C.CAP
    f = C.CORNER_JOINT_AT - J
    ch = C.CAP
    outer = P.orient(P.polygon([(o + ch, o), (f, o), (f, f), (o, f), (o, o + ch)]), True)
    i0, i1 = o + W, f - W
    c = 2 * o + ch + W * math.sqrt(2.0)      # inner chamfer line: a + b = c (outer line offset by W)
    hole = P.orient(P.polygon([(c - i0, i0), (i1, i0), (i1, i1), (i0, i1), (i0, c - i0)]), False)
    return [outer, hole]


def sash():
    """Top-hung vent sash: a plain tube behind a structurally bonded lite (no external cap)."""
    return [P.orient(P.rect(0.0, TF, C.SASH_W, TF + C.SASH_D), True),
            P.orient(P.rect(W, TF + W, C.SASH_W - W, TF + C.SASH_D - W), False)]


def fin():
    """Vertical fin centred on a joint, standing off the caps: a = across, b = depth."""
    r = C.FIN_W / 2.0
    b_nose = -C.CAP - C.FIN_D + r
    outer = [("A", (-r, b_nose), (r, b_nose), (0.0, b_nose), True),
             ("L", (r, b_nose), (r, -C.CAP)), ("L", (r, -C.CAP), (-r, -C.CAP)), ("L", (-r, -C.CAP), (-r, b_nose))]
    ri = r - W
    inner = [("A", (-ri, b_nose), (ri, b_nose), (0.0, b_nose), True),
             ("L", (ri, b_nose), (ri, -C.CAP - W)), ("L", (ri, -C.CAP - W), (-ri, -C.CAP - W)),
             ("L", (-ri, -C.CAP - W), (-ri, b_nose))]
    return [P.orient(outer, True), P.orient(inner, False)]


def starter():
    """Starter channel under the lowest units: the head profile, 60 high, with its cap."""
    return female(60.0, C.TRANSOM_D)


def closure(height=60.0, flashing=3.0, drip=20.0, back=200.0):
    """Closure over the top units: the sill profile (tongue down into the top heads), capped by a
    flashing that overhangs the caps by `drip` and runs back to b = `back`. One outline: the
    flashing closes the gap between cap and tube, which becomes a pocket (a second hole)."""
    a1 = J + height
    b1 = TF + C.TRANSOM_D
    s0, s1 = _stem(height)
    t0, t1 = _tongue_band(C.TRANSOM_D)
    top = a1 + flashing
    outer = P.orient(P.polygon([(J, -C.CAP), (a1, -C.CAP), (a1, -C.CAP - drip), (top, -C.CAP - drip), (top, back),
                                (a1, back), (a1, b1), (J, b1), (J, t1), (-REACH, t1), (-REACH, t0), (J, t0),
                                (J, TF), (s0, TF), (s0, 0.0), (J, 0.0)]), True)
    pocket = P.orient(P.rect(s1, 0.0, a1, TF), False)
    hole = P.orient(P.rect(J + W, TF + W, a1 - W, b1 - W), False)
    return [outer, pocket, hole]


# name -> (loops, orientation, description). "vertical": the extrusion runs along Z and the section
# lies in the horizontal plane; "horizontal": the extrusion runs along the facade.
def catalogue():
    return {
        "MUL-M": (male(C.MULLION_W, C.MULLION_D), "vertical", "Mullion, male half"),
        "MUL-F": (female(C.MULLION_W, C.MULLION_D), "vertical", "Mullion, female half"),
        "MUL-J": (jamb(C.MULLION_W, C.MULLION_D), "vertical", "Jamb mullion, -u edge of a unit"),
        "MUL-JE": (jamb_end(C.MULLION_W, C.MULLION_D), "vertical", "Jamb mullion, +u edge of a unit"),
        "CORNER": (corner_post(), "vertical", "Corner post"),
        "FIN": (fin(), "vertical", "Vertical fin"),
        "TR-SILL": (male(C.SILL_H, C.TRANSOM_D), "horizontal", "Sill transom (tongue down)"),
        "TR-HEAD": (female(C.HEAD_H, C.TRANSOM_D), "horizontal", "Head transom (slot legs up)"),
        "TR-MID": (mid_transom(C.MID_H, C.TRANSOM_D), "horizontal", "Vision/spandrel transom"),
        "SASH": (sash(), "horizontal", "Vent sash member, horizontal"),
        "SASH-V": (sash(), "vertical", "Vent sash member, vertical"),
        "STARTER": (starter(), "horizontal", "Starter channel"),
        "CLOSURE": (closure(), "horizontal", "Top closure with flashing"),
    }
