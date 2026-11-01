"""Cross-section geometry: exact outlines (lines and circular arcs) and their section properties.

One outline serves two purposes. The Revit jobs turn it into the sketch of an extrusion
(arcs stay true arcs), and the checks integrate it for area, centroid, second moments and
plastic moduli. So the stiffness a check uses is the stiffness of the solid that is modelled.

A profile is a list of closed loops; the first is the outer boundary (counter-clockwise), the
rest are holes (clockwise). A loop is a list of segments that join end to start:
    ("L", p0, p1)                    straight line
    ("A", p0, p1, centre, ccw)       circular arc from p0 to p1 about centre
Coordinates are (a, b) in mm in the plane of the section.

Standard library only (imported inside Revit).
"""
import math

ARC_STEPS = 256          # chords per full turn when an arc is integrated or drawn as a polyline


# --- building loops -----------------------------------------------------------------------------
def polygon(points):
    pts = [(float(a), float(b)) for a, b in points]
    return [("L", pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]


def rect(a0, b0, a1, b1):
    return polygon([(a0, b0), (a1, b0), (a1, b1), (a0, b1)])


def rounded_rect(a0, b0, a1, b1, r):
    """Rectangle with all four corners rounded to radius r (r = 0: sharp corners)."""
    if r <= 0:
        return rect(a0, b0, a1, b1)
    if 2 * r > min(a1 - a0, b1 - b0) + 1e-9:
        raise ValueError("corner radius %.3f too large for %.3f x %.3f" % (r, a1 - a0, b1 - b0))
    segs = []
    corners = [((a1 - r, b0 + r), -90.0), ((a1 - r, b1 - r), 0.0), ((a0 + r, b1 - r), 90.0), ((a0 + r, b0 + r), 180.0)]
    for (c, start) in corners:
        p0 = (c[0] + r * math.cos(math.radians(start)), c[1] + r * math.sin(math.radians(start)))
        p1 = (c[0] + r * math.cos(math.radians(start + 90)), c[1] + r * math.sin(math.radians(start + 90)))
        segs.append(("A", p0, p1, c, True))
    loop = []
    for i, arc in enumerate(segs):
        loop.append(arc)
        nxt = segs[(i + 1) % 4]
        if _dist(arc[2], nxt[1]) > 1e-9:
            loop.append(("L", arc[2], nxt[1]))
    return loop


def circle(ca, cb, r):
    """Full circle as two semicircular arcs (counter-clockwise)."""
    p0, p1 = (ca + r, cb), (ca - r, cb)
    return [("A", p0, p1, (ca, cb), True), ("A", p1, p0, (ca, cb), True)]


def reverse(loop):
    out = []
    for seg in reversed(loop):
        if seg[0] == "L":
            out.append(("L", seg[2], seg[1]))
        else:
            out.append(("A", seg[2], seg[1], seg[3], not seg[4]))
    return out


def transform(loop, fn):
    """Map every point through fn((a, b)) -> (a, b). fn must be a rigid motion or a mirror;
    a mirror flips orientation, so callers re-orient with orient()."""
    out = []
    for seg in loop:
        if seg[0] == "L":
            out.append(("L", fn(seg[1]), fn(seg[2])))
        else:
            p0, p1, c = fn(seg[1]), fn(seg[2]), fn(seg[3])
            out.append(("A", p0, p1, c, seg[4]))
    # arc direction must be recomputed after a mirror: keep the arc's mid-point on the same side
    fixed = []
    for new, old in zip(out, loop):
        if new[0] == "A":
            mid_old = fn(_arc_mid(old))
            ccw = new[4]
            if _dist(_arc_mid(("A", new[1], new[2], new[3], ccw)), mid_old) > 1e-6:
                ccw = not ccw
            fixed.append(("A", new[1], new[2], new[3], ccw))
        else:
            fixed.append(new)
    return fixed


def mirror_a(loop):
    """Mirror about the b axis (a -> -a) and restore the loop's orientation."""
    m = transform(loop, lambda p: (-p[0], p[1]))
    return reverse(m)


def mirror_b(loop):
    """Mirror about the a axis (b -> -b) and restore the loop's orientation."""
    m = transform(loop, lambda p: (p[0], -p[1]))
    return reverse(m)


def orient(loop, ccw=True):
    return loop if (signed_area(loop) > 0) == ccw else reverse(loop)


# --- geometry of segments -------------------------------------------------------------------------
def _dist(p, q):
    return math.hypot(p[0] - q[0], p[1] - q[1])


def _arc_angles(seg):
    _, p0, p1, c, ccw = seg
    a0 = math.atan2(p0[1] - c[1], p0[0] - c[0])
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0])
    if ccw:
        while a1 <= a0 + 1e-12:
            a1 += 2 * math.pi
    else:
        while a1 >= a0 - 1e-12:
            a1 -= 2 * math.pi
    return a0, a1


def _arc_mid(seg):
    a0, a1 = _arc_angles(seg)
    c = seg[3]
    r = _dist(seg[1], c)
    am = 0.5 * (a0 + a1)
    return (c[0] + r * math.cos(am), c[1] + r * math.sin(am))


def arc_radius(seg):
    return _dist(seg[1], seg[3])


def points(loop, steps=ARC_STEPS):
    """The loop as a closed polyline (last point not repeated); arcs split into chords."""
    pts = []
    for seg in loop:
        if seg[0] == "L":
            pts.append(seg[1])
        else:
            a0, a1 = _arc_angles(seg)
            n = max(2, int(math.ceil(abs(a1 - a0) / (2 * math.pi) * steps)))
            c, r = seg[3], arc_radius(seg)
            for i in range(n):
                t = a0 + (a1 - a0) * i / n
                pts.append((c[0] + r * math.cos(t), c[1] + r * math.sin(t)))
    return pts


def signed_area(loop):
    pts = points(loop)
    s = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s += x0 * y1 - x1 * y0
    return 0.5 * s


def check_closed(loop, tol=1e-6):
    for s0, s1 in zip(loop, loop[1:] + loop[:1]):
        if _dist(s0[2], s1[1]) > tol:
            raise ValueError("loop not closed at %s -> %s" % (s0[2], s1[1]))
    for seg in loop:
        if seg[0] == "A" and abs(_dist(seg[1], seg[3]) - _dist(seg[2], seg[3])) > tol:
            raise ValueError("arc end points not on one circle: %s" % (seg,))


def shortest_segment(loop):
    """Length of the shortest segment (Revit refuses sketch curves shorter than ~0.8 mm)."""
    best = float("inf")
    for seg in loop:
        if seg[0] == "L":
            best = min(best, _dist(seg[1], seg[2]))
        else:
            a0, a1 = _arc_angles(seg)
            best = min(best, abs(a1 - a0) * arc_radius(seg))
    return best


# --- section properties ------------------------------------------------------------------------------
def props(loops, steps=4096):
    """Area, centroid and centroidal second moments of a profile (outer loop + holes).

    Green's theorem over each loop's polyline (arcs split finely: 4096 chords per turn keeps the
    error on a 6 mm corner radius below 1e-6 of the area). Holes must be clockwise.
    Returns A, ca, cb, Iaa (about the axis through the centroid parallel to a, i.e. the integral
    of (b - cb)^2), Ibb, Iab.
    """
    A = Sa = Sb = Iaa0 = Ibb0 = Iab0 = 0.0
    for loop in loops:
        pts = points(loop, steps)
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            cr = x0 * y1 - x1 * y0
            A += cr / 2.0
            Sa += (x0 + x1) * cr / 6.0            # integral of a dA
            Sb += (y0 + y1) * cr / 6.0            # integral of b dA
            Iaa0 += (y0 * y0 + y0 * y1 + y1 * y1) * cr / 12.0     # integral of b^2 dA
            Ibb0 += (x0 * x0 + x0 * x1 + x1 * x1) * cr / 12.0     # integral of a^2 dA
            Iab0 += (x0 * y1 + 2 * x0 * y0 + 2 * x1 * y1 + x1 * y0) * cr / 24.0
    ca, cb = Sa / A, Sb / A
    return {"A": A, "ca": ca, "cb": cb,
            "Iaa": Iaa0 - A * cb * cb, "Ibb": Ibb0 - A * ca * ca, "Iab": Iab0 - A * ca * cb}


def bounds(loops, steps=ARC_STEPS):
    pts = [p for loop in loops for p in points(loop, steps)]
    return (min(p[0] for p in pts), min(p[1] for p in pts), max(p[0] for p in pts), max(p[1] for p in pts))


def _clip_half(loop_pts, axis, value, keep_above):
    """Sutherland-Hodgman clip of a closed polyline against the line coordinate[axis] = value."""
    def inside(p):
        return (p[axis] >= value) if keep_above else (p[axis] <= value)
    out = []
    n = len(loop_pts)
    for i in range(n):
        cur, prev = loop_pts[i], loop_pts[i - 1]
        if inside(cur):
            if not inside(prev):
                out.append(_cross(prev, cur, axis, value))
            out.append(cur)
        elif inside(prev):
            out.append(_cross(prev, cur, axis, value))
    return out


def _cross(p, q, axis, value):
    t = (value - p[axis]) / (q[axis] - p[axis])
    return (p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1]))


def _first_moment_above(loops, axis, value, steps):
    """Area and first moment (about coordinate[axis] = value) of the part with coordinate >= value."""
    A = S = 0.0
    for loop in loops:
        pts = _clip_half(points(loop, steps), axis, value, True)
        if len(pts) < 3:
            continue
        for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
            cr = x0 * y1 - x1 * y0
            A += cr / 2.0
            if axis == 1:
                S += (y0 + y1) * cr / 6.0
            else:
                S += (x0 + x1) * cr / 6.0
    return A, S - A * value


def plastic_modulus(loops, axis, steps=4096):
    """Plastic section modulus for bending that puts the axis coordinate in tension/compression.

    axis = 1: bending about an axis parallel to a (stress varies with b); axis = 0: about b.
    The plastic neutral axis splits the area in half (found by bisection); W_pl is the sum of
    the first moments of the two halves about it.
    """
    p = props(loops, steps)
    lo, hi = bounds(loops)[axis], bounds(loops)[axis + 2]
    half = p["A"] / 2.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        a_up, _ = _first_moment_above(loops, axis, mid, steps)
        if a_up > half:
            lo = mid
        else:
            hi = mid
    pna = 0.5 * (lo + hi)
    a_up, s_up = _first_moment_above(loops, axis, pna, steps)
    total_first = (p["cb"] if axis == 1 else p["ca"]) * p["A"] - pna * p["A"]   # = S_above + S_below
    s_down = total_first - s_up
    return s_up - s_down
