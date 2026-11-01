"""The frame solver against closed-form results and against itself (equilibrium)."""
import math

import numpy as np
import pytest

from vmu.frame import Model

E, G, A, IY, IZ, J = 210e6, 81e6, 2.0e-3, 8.0e-6, 3.0e-6, 5.0e-6      # kN, m
L = 4.0


def cantilever(load, vecxz=(0, 0, 1)):
    m = Model()
    m.node("a", (0, 0, 0))
    m.node("b", (L, 0, 0))
    m.support("a", [1] * 6)
    m.beam("e", "a", "b", E, G, A, IY, IZ, J, vecxz)
    m.load_node("c", "b", load)
    return m, m.solve("c")


def test_cantilever_tip_load_in_z_bends_about_y():
    P = 10.0
    m, r = cantilever([0, 0, -P, 0, 0, 0])
    assert r["u"]["b"][2] == pytest.approx(-P * L ** 3 / (3 * E * IY), rel=1e-12)
    assert r["u"]["b"][4] == pytest.approx(P * L ** 2 / (2 * E * IY), rel=1e-12)     # rotation about +y
    assert r["reactions"]["a"][2] == pytest.approx(P)
    assert r["reactions"]["a"][4] == pytest.approx(-P * L)                           # moment about +y


def test_cantilever_tip_load_in_y_bends_about_z():
    P = 7.0
    m, r = cantilever([0, P, 0, 0, 0, 0])
    assert r["u"]["b"][1] == pytest.approx(P * L ** 3 / (3 * E * IZ), rel=1e-12)
    assert r["reactions"]["a"][5] == pytest.approx(-P * L)


def test_cantilever_torque():
    T = 3.0
    m, r = cantilever([0, 0, 0, T, 0, 0])
    assert r["u"]["b"][3] == pytest.approx(T * L / (G * J), rel=1e-12)


def test_axial():
    N = 50.0
    m, r = cantilever([N, 0, 0, 0, 0, 0])
    assert r["u"]["b"][0] == pytest.approx(N * L / (E * A), rel=1e-12)
    s = m.internal(r, "e", "c", 3)
    assert all(row[1] == pytest.approx(N) for row in s)                                # tension +


def simply_supported(w, n_el=1, release=True):
    """Beam on pin supports: n_el elements; if release, the single element uses end releases
    instead of rotational freedom of the supports (both must give the same answer)."""
    m = Model()
    xs = np.linspace(0, L, n_el + 1)
    for k, x in enumerate(xs):
        m.node("n%d" % k, (x, 0, 0))
    m.support("n0", [1, 1, 1, 1, 0, 0])
    m.support("n%d" % n_el, [0, 1, 1, 0, 0, 0])
    for k in range(n_el):
        m.beam("e%d" % k, "n%d" % k, "n%d" % (k + 1), E, G, A, IY, IZ, J, (0, 0, 1))
        m.load_udl("c", "e%d" % k, (0, 0, -w))
    return m, m.solve("c")


def test_simply_supported_udl_midspan():
    w = 5.0
    m, r = simply_supported(w, n_el=2)
    assert r["u"]["n1"][2] == pytest.approx(-5 * w * L ** 4 / (384 * E * IY), rel=1e-12)
    assert r["reactions"]["n0"][2] == pytest.approx(w * L / 2)
    s = m.internal(r, "e0", "c", 5)
    # sagging moment at midspan = w L^2 / 8 (magnitude) and zero at the support
    assert abs(s[0][5]) == pytest.approx(0.0, abs=1e-9)
    assert abs(s[-1][5]) == pytest.approx(w * L ** 2 / 8, rel=1e-12)


def test_fixed_fixed_udl_end_moments():
    w = 6.0
    m = Model()
    m.node("a", (0, 0, 0))
    m.node("b", (L, 0, 0))
    m.support("a", [1] * 6)
    m.support("b", [1] * 6)
    m.beam("e", "a", "b", E, G, A, IY, IZ, J, (0, 0, 1))
    m.load_udl("c", "e", (0, 0, -w))
    r = m.solve("c")
    s = m.internal(r, "e", "c", 3)
    assert abs(s[0][5]) == pytest.approx(w * L ** 2 / 12, rel=1e-12)
    assert abs(s[1][5]) == pytest.approx(w * L ** 2 / 24, rel=1e-12)


def test_released_ends_carry_no_moment_and_match_pinned_supports():
    w = 4.0
    m = Model()
    for n, x in (("a", 0.0), ("b", L)):
        m.node(n, (x, 0, 0))
        m.support(n, [1] * 6)                     # clamped supports ...
    m.beam("e", "a", "b", E, G, A, IY, IZ, J, (0, 0, 1), release_i=(4, 5), release_j=(4, 5))
    m.load_udl("c", "e", (0, 0, -w))
    r = m.solve("c")
    f = r["forces"]["e"]
    assert f[4] == pytest.approx(0, abs=1e-9) and f[10] == pytest.approx(0, abs=1e-9)   # ... but pinned ends
    s = m.internal(r, "e", "c", 3)
    assert abs(s[1][5]) == pytest.approx(w * L ** 2 / 8, rel=1e-12)


def test_internal_forces_at_j_equal_the_j_end_forces():
    m = Model()
    m.node("a", (0, 0, 0))
    m.node("b", (3.0, 1.0, 2.0))
    m.support("a", [1] * 6)
    m.beam("e", "a", "b", E, G, A, IY, IZ, J, (0, 0, 1))
    m.load_node("c", "b", [1.0, -2.0, 3.0, 0.4, -0.5, 0.6])
    m.load_udl("c", "e", (0.3, -0.7, -1.1))
    r = m.solve("c")
    s = m.internal(r, "e", "c", 2)[-1]
    f = r["forces"]["e"]
    for k in range(6):
        assert s[1 + k] == pytest.approx(f[6 + k] if k == 0 else f[6 + k], abs=1e-9)


def test_truss_triangle():
    m = Model()
    m.node("a", (0, 0, 0))
    m.node("b", (4, 0, 0))
    m.node("c", (2, 0, 3))
    m.support("a", [1, 1, 1, 0, 0, 0])
    m.support("b", [0, 1, 1, 0, 0, 0])
    m.support("c", [0, 1, 0, 0, 0, 0])
    for n, (i, j) in {"ab": ("a", "b"), "ac": ("a", "c"), "bc": ("b", "c")}.items():
        m.truss(n, i, j, E, A)
    m.load_node("P", "c", [0, 0, -10, 0, 0, 0])
    r = m.solve("P")
    assert r["zero_stiffness_dofs"] == 9                  # every rotation: nothing resists them
    n_ac = m.internal(r, "ac", "P", 2)[0][1]
    assert n_ac == pytest.approx(-10 / 2 / (3 / math.hypot(2, 3)), rel=1e-12)   # compression


def test_reactions_balance_loads_on_a_space_frame():
    rng = np.random.default_rng(3)
    m = Model()
    pts = {"a": (0, 0, 0), "b": (4, 0, 0), "c": (4, 3, 0), "d": (0, 3, 0)}
    for k, p in pts.items():
        m.node(k, p)
        m.node(k + "t", (p[0], p[1], 3.5))
        m.support(k, [1] * 6)
        m.beam("col" + k, k, k + "t", E, G, A, IY, IZ, J, (1, 0, 0))
    ring = ["at", "bt", "ct", "dt"]
    for k in range(4):
        i, j = ring[k], ring[(k + 1) % 4]
        m.beam("bm%d" % k, i, j, E, G, A, IY, IZ, J, (0, 0, 1), release_i=(5,), release_j=(4, 5))
        m.load_udl("c", "bm%d" % k, rng.normal(size=3))
    m.truss("br", "a", "ct", E, A)
    for n in ring:
        m.load_node("c", n, rng.normal(size=6))
    r = m.solve("c")
    total = np.zeros(6)
    for n, f in m.cases["c"]["nodal"].items():
        total[:3] += f[:3]
        total[3:] += f[3:] + np.cross(m.nodes[n], f[:3])
    for e, w in m.cases["c"]["udl"].items():
        el = m.elements[e]
        _, Le = m.axes(el)
        mid = 0.5 * (m.nodes[el["i"]] + m.nodes[el["j"]])
        total[:3] += w * Le
        total[3:] += np.cross(mid, w * Le)
    reac = np.zeros(6)
    for n, f in r["reactions"].items():
        reac[:3] += f[:3]
        reac[3:] += f[3:] + np.cross(m.nodes[n], f[:3])
    assert np.allclose(total + reac, 0, atol=1e-9)
