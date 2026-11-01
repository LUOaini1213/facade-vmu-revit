"""Where every element of the mock-up goes: units and their parts, anchors, steel, footings.

The single source of geometry. The Revit jobs place exactly these elements (by id), the IFC and
schedule checks read them back against this list, and the structural model is built from them.

Face frames. Each face has a right-handed frame (d, n, z): d runs along the face, n = z x d
points into the mock-up, and the section coordinates of every extrusion map a -> d, b -> n.
  face A: d = +X, n = +Y, u = X        (units A1..A6 from the corner to the free end)
  face B: d = -Y, n = +X, u = -Y       (units B1, B2 from the corner to the free end)
So a placement is an origin plus a rotation about Z (0 deg for A, -90 deg for B), never a mirror.
Along u, each unit has its male half-mullion at the joint on its -u side and its female half at
the joint on its +u side; next to the corner post and at free ends it has a jamb instead.

Every placed element is a dict with a stable "id"; lengths are mm, angles degrees.
Standard library only (imported inside Revit).
"""
import math

from . import config as C

J = C.JOINT / 2.0

FACES = {
    "A": {"angle": 0.0, "n_modules": C.FACE_A_MODULES},
    "B": {"angle": -90.0, "n_modules": C.FACE_B_MODULES},
}


def face_point(face, u, w, z):
    """World (x, y, z) of face coordinates (u along the face, w into the mock-up, z)."""
    if face == "A":
        return (u, w, z)
    return (w, -u, z)


def unit_edges(face, index):
    """Joint centrelines (u) bounding unit `index` (1 = at the corner) and what is at each edge."""
    n = FACES[face]["n_modules"]
    if face == "A":
        lo, hi = (index - 1) * C.MODULE, index * C.MODULE
        if index == 1:
            lo = C.CORNER_JOINT_AT
        lo_kind = "corner" if index == 1 else "joint"
        hi_kind = "end" if index == n else "joint"
    else:                                   # u = -Y: unit 1 sits at u in [-1500, 0]
        lo, hi = -index * C.MODULE, -(index - 1) * C.MODULE
        if index == 1:
            hi = -C.CORNER_JOINT_AT
        lo_kind = "end" if index == n else "joint"
        hi_kind = "corner" if index == 1 else "joint"
    return lo, hi, lo_kind, hi_kind


def storey_z(storey):
    s = next(s for s in C.STOREYS if s[0] == storey)
    fl0, fl1 = C.LEVELS[s[1]], C.LEVELS[s[2]]
    return fl0, fl1, fl0 + C.STACK_ABOVE_FL + J, fl1 + C.STACK_ABOVE_FL - J


def _member(eid, profile, face, u, w, z, length, horizontal, role, unit=None):
    """Placement of a profile extrusion. Vertical: section in the plan at (u, w=0) origin, extruded
    up from z. Horizontal: section in the vertical plane, extruded along +d from u."""
    x, y, zz = face_point(face, u, w, z)
    return {"id": eid, "kind": "extrusion", "profile": profile, "face": face, "unit": unit, "role": role,
            "origin": (round(x, 4), round(y, 4), round(zz, 4)), "angle": FACES[face]["angle"],
            "length": round(length, 4), "horizontal": horizontal}


def _panel(eid, kind, face, u0, z0, width, height, w0, thickness, material, unit, role):
    x, y, z = face_point(face, u0, w0, z0)
    return {"id": eid, "kind": kind, "face": face, "unit": unit, "role": role,
            "origin": (round(x, 4), round(y, 4), round(z, 4)), "angle": FACES[face]["angle"],
            "width": round(width, 4), "height": round(height, 4), "thickness": round(thickness, 4),
            "w0": round(w0, 4), "material": material}


def _infill(uid, face, zone, u0, z0, dlo_w, dlo_h, opaque, unit, parts):
    """Glass or panel in one daylight opening (dlo), plus insulation and back-pan if opaque."""
    gw, gh = dlo_w + 2 * C.BITE, dlo_h + 2 * C.BITE
    gu, gz = u0 - C.BITE, z0 - C.BITE
    if opaque == "vision":
        parts.append(_panel("%s-%s-IGU" % (uid, zone), "igu", face, gu, gz, gw, gh, 0.0, sum(C.IGU),
                            "Glass IGU", unit, zone))
        return
    if opaque == "spandrel":
        parts.append(_panel("%s-%s-GLS" % (uid, zone), "glass", face, gu, gz, gw, gh, 0.0, C.SPANDREL_GLASS,
                            "Glass spandrel", unit, zone))
    else:
        parts.append(_panel("%s-%s-PNL" % (uid, zone), "panel", face, gu, gz, gw, gh, 0.0, C.SOLID_PANEL,
                            "Aluminium panel", unit, zone))
    back = C.TUBE_FACE + C.TRANSOM_D - 3.5          # back-pan 3.5 mm in front of the transom back
    parts.append(_panel("%s-%s-INS" % (uid, zone), "insulation", face, u0, z0, dlo_w, dlo_h,
                        back - C.BACKPAN - C.INSULATION, C.INSULATION, "Mineral wool", unit, zone))
    parts.append(_panel("%s-%s-BKP" % (uid, zone), "backpan", face, u0, z0, dlo_w, dlo_h,
                        back - C.BACKPAN, C.BACKPAN, "Aluminium back-pan", unit, zone))


def units():
    """All units with their parts. Each unit: id, storey, face, index, type, frame extents."""
    out = []
    for storey, _, _ in C.STOREYS:
        fl0, fl1, zb, zt = storey_z(storey)
        for face in ("A", "B"):
            for i, utype in enumerate(C.UNIT_TYPES[storey][face], start=1):
                uid = "%s-%s%d" % (storey, face, i)
                lo, hi, lo_kind, hi_kind = unit_edges(face, i)
                f0, f1 = lo + J, hi - J
                height = zt - zb
                parts = []
                prof_lo = "MUL-M" if lo_kind == "joint" else "MUL-J"
                prof_hi = "MUL-F" if hi_kind == "joint" else "MUL-JE"
                parts.append(_member(uid + "-MUL-L", prof_lo, face, lo, 0.0, zb, height, False, "mullion", uid))
                parts.append(_member(uid + "-MUL-R", prof_hi, face, hi, 0.0, zb, height, False, "mullion", uid))
                t0, t1 = f0 + C.MULLION_W, f1 - C.MULLION_W          # between mullion tubes
                tl = t1 - t0
                parts.append(_member(uid + "-TR-SILL", "TR-SILL", face, t0, 0.0, zb - J, tl, True, "sill", uid))
                parts.append(_member(uid + "-TR-HEAD", "TR-HEAD", face, t0, 0.0, zt + J, tl, True, "head", uid))
                zm = zb + C.MID_AT
                parts.append(_member(uid + "-TR-MID", "TR-MID", face, t0, 0.0, zm, tl, True, "transom", uid))
                vis0, vis1 = zb + C.SILL_H, zm - C.MID_H / 2.0
                spa0, spa1 = zm + C.MID_H / 2.0, zt - C.HEAD_H
                upper = "spandrel" if utype != "S" else "panel"
                lower = "vision" if utype != "S" else "panel"
                if utype == "VO":
                    zv = zb + C.VENT_AT
                    parts.append(_member(uid + "-TR-VENT", "TR-MID", face, t0, 0.0, zv, tl, True, "transom", uid))
                    _infill(uid, face, "VIS", t0, vis0, tl, zv - C.MID_H / 2.0 - vis0, "vision", uid, parts)
                    _vent(uid, face, t0, zv + C.MID_H / 2.0, tl, vis1 - (zv + C.MID_H / 2.0), parts)
                else:
                    _infill(uid, face, "VIS", t0, vis0, tl, vis1 - vis0, lower, uid, parts)
                _infill(uid, face, "SPA", t0, spa0, tl, spa1 - spa0, upper, uid, parts)
                if lo_kind == "joint":                       # fin on the male side of each joint
                    parts.append(_member(uid + "-FIN", "FIN", face, lo, 0.0, zb, height, False, "fin", uid))
                out.append({"id": uid, "storey": storey, "face": face, "index": i, "type": utype,
                            "u0": f0, "u1": f1, "z0": zb, "z1": zt, "width": f1 - f0, "height": height,
                            "lo_kind": lo_kind, "hi_kind": hi_kind, "hung_from": next(
                                s[2] for s in C.STOREYS if s[0] == storey), "parts": parts})
    return out


def _vent(uid, face, u0, z0, dlo_w, dlo_h, parts):
    """Top-hung vent: sash of four members inside the opening, bonded IGU in front of it."""
    g = C.VENT_GAP
    sw, sh = dlo_w - 2 * g, dlo_h - 2 * g
    su, sz = u0 + g, z0 + g
    parts.append(_member(uid + "-SASH-B", "SASH", face, su, 0.0, sz, sw, True, "sash", uid))
    parts.append(_member(uid + "-SASH-T", "SASH", face, su, 0.0, sz + sh - C.SASH_W, sw, True, "sash", uid))
    parts.append(_member(uid + "-SASH-L", "SASH-V", face, su, 0.0, sz + C.SASH_W, sh - 2 * C.SASH_W, False,
                         "sash", uid))
    parts.append(_member(uid + "-SASH-R", "SASH-V", face, su + sw - C.SASH_W, 0.0, sz + C.SASH_W,
                         sh - 2 * C.SASH_W, False, "sash", uid))
    parts.append(_panel(uid + "-VENT-IGU", "igu", face, su + C.SASH_W - C.BITE, sz + C.SASH_W - C.BITE,
                        sw - 2 * C.SASH_W + 2 * C.BITE, sh - 2 * C.SASH_W + 2 * C.BITE, 0.0, sum(C.IGU),
                        "Glass IGU", uid, "VENT"))


def perimeter():
    """Corner posts, starter channels and top closures (not part of any unit)."""
    out = []
    for storey, _, _ in C.STOREYS:
        _, _, zb, zt = storey_z(storey)
        out.append({"id": "%s-CORNER" % storey, "kind": "extrusion", "profile": "CORNER", "face": None,
                    "unit": None, "role": "corner post", "origin": (0.0, 0.0, round(zb, 4)), "angle": 0.0,
                    "length": round(zt - zb, 4), "horizontal": False})
    z_start = C.LEVELS["L1"] + C.STACK_ABOVE_FL
    z_close = C.LEVELS["L3"] + C.STACK_ABOVE_FL
    for face in ("A", "B"):
        n = FACES[face]["n_modules"]
        lo = unit_edges(face, 1 if face == "A" else n)[0] + J
        hi = unit_edges(face, n if face == "A" else 1)[1] - J
        out.append(_member("STARTER-%s" % face, "STARTER", face, lo, 0.0, z_start, hi - lo, True, "starter"))
        out.append(_member("CLOSURE-%s" % face, "CLOSURE", face, lo, 0.0, z_close, hi - lo, True, "closure"))
    return out


# --- anchors ------------------------------------------------------------------------------------
END_INSET = J + C.BRACKET_PLATE[0] / 2.0 + 10.0   # end anchor centre, measured in from the end line


def face_end(face):
    """u of the free-end joint line of a face (the facade stops 7.5 mm short of it)."""
    n = FACES[face]["n_modules"]
    lo, hi, lo_kind, hi_kind = unit_edges(face, n if face == "A" else n)
    return hi if face == "A" else lo


def anchor_lines():
    """Every mullion line that needs an anchor, as (face, u of the anchor centre, what it carries).
    Joints carry two half-units. A free-end anchor carries one jamb; it sits 92.5 mm in from the
    end line so that its plate stays on the edge beam and its hook bar still overlaps the jamb by
    40 mm. The corner anchor takes the corner post and the two jambs next to it."""
    lines = []
    for face in ("A", "B"):
        n = FACES[face]["n_modules"]
        for i in range(1, n + 1):
            lo, hi, lo_kind, hi_kind = unit_edges(face, i)
            if lo_kind == "joint":
                lines.append((face, lo, "joint"))
            if lo_kind == "end":
                lines.append((face, lo + END_INSET, "end"))
            if hi_kind == "end":
                lines.append((face, hi - END_INSET, "end"))
    lines.append((None, None, "corner"))
    return lines


def brackets():
    out = []
    for level in ("L1", "L2", "L3"):
        fl = C.LEVELS[level]
        kind = "starter" if level == "L1" else "main"
        for face, u, carries in anchor_lines():
            if carries == "corner":
                eid = "BRK-%s-CORNER" % level
                out.append({"id": eid, "kind": "bracket", "type": "corner-" + kind, "level": level,
                            "face": None, "u": None, "carries": carries,
                            "origin": (C.EDGE_AXIS, C.EDGE_AXIS, fl), "angle": 45.0})
                continue
            eid = "BRK-%s-%s%+06.0f" % (level, face, u)
            x, y, z = face_point(face, u, 0.0, fl)
            out.append({"id": eid, "kind": "bracket", "type": kind, "level": level, "face": face,
                        "u": round(u, 4), "carries": carries, "origin": (round(x, 4), round(y, 4), fl),
                        "angle": FACES[face]["angle"]})
    return out


# --- steel ------------------------------------------------------------------------------------------
def _pt(x, y, z):
    return (round(x, 4), round(y, 4), round(z, 4))


def steel():
    """Physical steel members as centre lines. Beams carry their top-of-steel level; the Revit
    job offsets them down by half their depth. Returns a list of dicts."""
    out = []
    xs, ys = C.COLUMN_X, C.COLUMN_Y
    top = C.LEVELS["L3"]
    base = C.GL + C.BASE_PLATE[2]
    for j, y in enumerate(ys):
        for i, x in enumerate(xs):
            out.append({"id": "COL-%s%d" % ("FR"[j], i + 1), "kind": "column", "group": "column",
                        "start": _pt(x, y, base), "end": _pt(x, y, top)})
    a0 = C.EDGE_AXIS
    end_a = face_end("A")                         # edge beams stop at the free-end joint lines
    end_b = -face_end("B")
    half = 50.0                                   # half the width of the edge beams (RHS 100 wide)
    for level, fl in C.LEVELS.items():
        # face B's beam runs through the corner; face A's butts against its back face
        out.append({"id": "EB-A-%s" % level, "kind": "beam", "group": "edge_beam", "level": level,
                    "start": _pt(a0 + half, a0, fl), "end": _pt(end_a, a0, fl)})
        out.append({"id": "EB-B-%s" % level, "kind": "beam", "group": "edge_beam", "level": level,
                    "start": _pt(a0, a0 - half, fl), "end": _pt(a0, end_b, fl)})
        for i, x in enumerate(xs[1:], start=2):
            out.append({"id": "XB-%d-%s" % (i, level), "kind": "beam", "group": "cross_beam", "level": level,
                        "start": _pt(x, ys[0], fl), "end": _pt(x, ys[1], fl)})
        for i in range(len(xs) - 1):
            out.append({"id": "RB-%d%d-%s" % (i + 1, i + 2, level), "kind": "beam", "group": "rear_beam",
                        "level": level, "start": _pt(xs[i], ys[1], fl), "end": _pt(xs[i + 1], ys[1], fl)})
    zs = [C.GL] + [C.LEVELS[k] for k in ("L1", "L2", "L3")]
    names = ["GL", "L1", "L2", "L3"]
    for i, x in enumerate(xs, start=1):                       # vertical bracing in every Y-Z frame
        for k in range(3):
            z0, z1 = zs[k], zs[k + 1]
            tag = "%s%s" % (names[k], names[k + 1])
            out.append({"id": "VB-X%d-%s-1" % (i, tag), "kind": "brace", "group": "brace",
                        "start": _pt(x, ys[0], z0), "end": _pt(x, ys[1], z1)})
            out.append({"id": "VB-X%d-%s-2" % (i, tag), "kind": "brace", "group": "brace",
                        "start": _pt(x, ys[1], z0), "end": _pt(x, ys[0], z1)})
    for (i0, i1) in C.REAR_BRACED_BAYS:                        # rear frame
        for k in range(3):
            z0, z1 = zs[k], zs[k + 1]
            tag = "%s%s" % (names[k], names[k + 1])
            out.append({"id": "VB-R%d%d-%s-1" % (i0 + 1, i1 + 1, tag), "kind": "brace", "group": "brace",
                        "start": _pt(xs[i0], ys[1], z0), "end": _pt(xs[i1], ys[1], z1)})
            out.append({"id": "VB-R%d%d-%s-2" % (i0 + 1, i1 + 1, tag), "kind": "brace", "group": "brace",
                        "start": _pt(xs[i1], ys[1], z0), "end": _pt(xs[i0], ys[1], z1)})
    for level, fl in C.LEVELS.items():                          # plan bracing
        for (i0, i1) in C.PLAN_BRACED_BAYS:
            out.append({"id": "PB-%d%d-%s-1" % (i0 + 1, i1 + 1, level), "kind": "brace", "group": "plan_brace",
                        "level": level, "start": _pt(xs[i0], ys[0], fl), "end": _pt(xs[i1], ys[1], fl)})
            out.append({"id": "PB-%d%d-%s-2" % (i0 + 1, i1 + 1, level), "kind": "brace", "group": "plan_brace",
                        "level": level, "start": _pt(xs[i1], ys[0], fl), "end": _pt(xs[i0], ys[1], fl)})
    return out


def base_plates():
    b, d, t = C.BASE_PLATE
    return [{"id": "BP-%s%d" % ("FR"[j], i + 1), "kind": "base_plate", "centre": _pt(x, y, C.GL),
             "size": (b, d, t)} for j, y in enumerate(C.COLUMN_Y) for i, x in enumerate(C.COLUMN_X)]


def footings():
    f = C.FOOTING
    y0, y1 = C.COLUMN_Y[0] - f["overhang"], C.COLUMN_Y[1] + f["overhang"]
    return [{"id": "FTG-%d" % (i + 1), "kind": "footing", "x0": x - f["width"] / 2.0, "x1": x + f["width"] / 2.0,
             "y0": y0, "y1": y1, "z0": C.GL - f["depth"], "z1": C.GL} for i, x in enumerate(C.COLUMN_X)]


def all_elements():
    """Flat list of every placed element (unit parts expanded)."""
    els = []
    for u in units():
        els.extend(u["parts"])
    els.extend(perimeter())
    els.extend(brackets())
    els.extend(steel())
    els.extend(base_plates())
    els.extend(footings())
    return els


def length(member):
    s, e = member["start"], member["end"]
    return math.sqrt(sum((a - b) ** 2 for a, b in zip(s, e)))
