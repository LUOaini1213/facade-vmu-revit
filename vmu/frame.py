"""A small linear-elastic 3D frame solver (direct stiffness method), written out so it can be read.

Elements are 2-node Euler-Bernoulli beam-columns (12 DOF) with optional end releases, or truss
bars (axial only). Local axes follow the OpenSees convention: x runs from node i to node j, the
user gives a vector `vecxz` lying in the local x-z plane, y = vecxz x x, z = x x y. Iy is the
second moment about local y (bending that deflects along local z), Iz about local z.

Loads: nodal forces/moments, and uniformly distributed forces on elements given in global axes
(self-weight, wind on a member). Released DOFs are condensed out of each element (stiffness and
fixed-end forces), so a pinned end carries exactly zero moment.

Units are whatever the caller uses consistently; the structure model uses kN and m.
"""
import numpy as np

DOF = 6


class Model:
    def __init__(self):
        self.nodes = {}            # name -> np.array([x, y, z])
        self.elements = {}         # name -> dict
        self.fix = {}              # name -> 6 booleans (True = restrained)
        self.cases = {}            # case -> {"nodal": {node: 6-vector}, "udl": {element: 3-vector global}}

    # --- building ---------------------------------------------------------------------------------
    def node(self, name, xyz):
        self.nodes[name] = np.asarray(xyz, dtype=float)

    def support(self, name, fixity):
        self.fix[name] = tuple(bool(f) for f in fixity)

    def beam(self, name, i, j, E, G, A, Iy, Iz, J, vecxz, release_i=(), release_j=(), group=None, section=None):
        """release_i / release_j: iterable of local DOF indices released at that end
        (0 N, 1 Vy, 2 Vz, 3 T, 4 My, 5 Mz)."""
        self.elements[name] = {"type": "beam", "i": i, "j": j, "E": E, "G": G, "A": A, "Iy": Iy, "Iz": Iz,
                               "J": J, "vecxz": np.asarray(vecxz, dtype=float),
                               "rel": sorted(set(release_i)) + [6 + k for k in sorted(set(release_j))],
                               "group": group, "section": section}

    def truss(self, name, i, j, E, A, group=None, section=None):
        self.elements[name] = {"type": "truss", "i": i, "j": j, "E": E, "A": A, "group": group,
                               "section": section}

    def load_node(self, case, name, f):
        c = self.cases.setdefault(case, {"nodal": {}, "udl": {}})
        c["nodal"][name] = c["nodal"].get(name, np.zeros(6)) + np.asarray(f, dtype=float)

    def load_udl(self, case, element, w_global):
        c = self.cases.setdefault(case, {"nodal": {}, "udl": {}})
        c["udl"][element] = c["udl"].get(element, np.zeros(3)) + np.asarray(w_global, dtype=float)

    # --- element matrices -----------------------------------------------------------------------------
    def axes(self, e):
        """3x3 rotation, rows = local x, y, z in global components; and the length."""
        xi, xj = self.nodes[e["i"]], self.nodes[e["j"]]
        d = xj - xi
        L = float(np.linalg.norm(d))
        ex = d / L
        v = e.get("vecxz")
        if v is None:                                   # truss: any orthonormal completion
            v = np.array([0.0, 0.0, 1.0]) if abs(ex[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
        ey = np.cross(v, ex)
        n = np.linalg.norm(ey)
        if n < 1e-9:
            raise ValueError("vecxz parallel to element %s-%s" % (e["i"], e["j"]))
        ey /= n
        ez = np.cross(ex, ey)
        return np.vstack([ex, ey, ez]), L

    @staticmethod
    def k_local(e, L):
        k = np.zeros((12, 12))
        if e["type"] == "truss":
            a = e["E"] * e["A"] / L
            k[0, 0] = k[6, 6] = a
            k[0, 6] = k[6, 0] = -a
            return k
        E, G, A, Iy, Iz, J = e["E"], e["G"], e["A"], e["Iy"], e["Iz"], e["J"]
        a = E * A / L
        t = G * J / L
        k[0, 0] = k[6, 6] = a
        k[0, 6] = k[6, 0] = -a
        k[3, 3] = k[9, 9] = t
        k[3, 9] = k[9, 3] = -t
        # bending in the local x-y plane (about z): v = DOF 1/7, rz = DOF 5/11
        c1, c2, c3, c4 = 12 * E * Iz / L ** 3, 6 * E * Iz / L ** 2, 4 * E * Iz / L, 2 * E * Iz / L
        for (p, q, val) in ((1, 1, c1), (1, 5, c2), (1, 7, -c1), (1, 11, c2), (5, 5, c3), (5, 7, -c2), (5, 11, c4),
                            (7, 7, c1), (7, 11, -c2), (11, 11, c3)):
            k[p, q] = k[q, p] = val
        # bending in the local x-z plane (about y): w = DOF 2/8, ry = DOF 4/10 (sign convention flips)
        d1, d2, d3, d4 = 12 * E * Iy / L ** 3, 6 * E * Iy / L ** 2, 4 * E * Iy / L, 2 * E * Iy / L
        for (p, q, val) in ((2, 2, d1), (2, 4, -d2), (2, 8, -d1), (2, 10, -d2), (4, 4, d3), (4, 8, d2), (4, 10, d4),
                            (8, 8, d1), (8, 10, d2), (10, 10, d3)):
            k[p, q] = k[q, p] = val
        return k

    @staticmethod
    def fef_local(w_local, L):
        """Fixed-end forces (the element's end forces with both ends clamped) for a uniform load
        w_local = (wx, wy, wz) per unit length in local axes. Returned as element end forces."""
        wx, wy, wz = w_local
        f = np.zeros(12)
        f[0] = f[6] = -wx * L / 2.0
        f[1] = f[7] = -wy * L / 2.0
        f[5] = -wy * L * L / 12.0
        f[11] = wy * L * L / 12.0
        f[2] = f[8] = -wz * L / 2.0
        f[4] = wz * L * L / 12.0
        f[10] = -wz * L * L / 12.0
        return f

    def _condensed(self, e, k, fef):
        rel = e.get("rel", []) if e["type"] == "beam" else []
        if not rel:
            return k, fef, None
        keep = [i for i in range(12) if i not in rel]
        krr = k[np.ix_(rel, rel)]
        krk = k[np.ix_(rel, keep)]
        inv = np.linalg.inv(krr)
        kc = np.zeros((12, 12))
        kc[np.ix_(keep, keep)] = k[np.ix_(keep, keep)] - krk.T @ inv @ krk
        fc = np.zeros(12)
        fc[keep] = fef[keep] - krk.T @ inv @ fef[rel]
        return kc, fc, (rel, keep, inv, krk)

    # --- solving -------------------------------------------------------------------------------------------
    def solve(self, case):
        names = list(self.nodes)
        index = {n: i for i, n in enumerate(names)}
        ndof = DOF * len(names)
        K = np.zeros((ndof, ndof))
        F = np.zeros(ndof)
        cache = {}
        c = self.cases.get(case, {"nodal": {}, "udl": {}})
        for name, e in self.elements.items():
            R3, L = self.axes(e)
            T = np.zeros((12, 12))
            for b in range(4):
                T[3 * b:3 * b + 3, 3 * b:3 * b + 3] = R3
            k = self.k_local(e, L)
            w = c["udl"].get(name)
            fef = self.fef_local(R3 @ w, L) if w is not None else np.zeros(12)
            kc, fc, cond = self._condensed(e, k, fef)
            cache[name] = (T, kc, fc, cond, k, fef, L)
            dofs = np.r_[DOF * index[e["i"]]:DOF * index[e["i"]] + 6, DOF * index[e["j"]]:DOF * index[e["j"]] + 6]
            K[np.ix_(dofs, dofs)] += T.T @ kc @ T
            F[dofs] -= T.T @ fc
        for n, f in c["nodal"].items():
            F[DOF * index[n]:DOF * index[n] + 6] += f
        fixed = np.zeros(ndof, dtype=bool)
        for n, fx in self.fix.items():
            fixed[DOF * index[n]:DOF * index[n] + 6] = fx
        # DOFs no element stiffens (rotations of nodes that only trusses reach) are restrained too;
        # any load put on one would be lost, so that is an error.
        diag = np.abs(np.diag(K))
        free_zero = (~fixed) & (diag < 1e-9 * max(diag.max(), 1.0))
        if np.any(np.abs(F[free_zero]) > 1e-12):
            raise ValueError("load on a DOF that nothing resists")
        fixed |= free_zero
        free = ~fixed
        U = np.zeros(ndof)
        U[free] = np.linalg.solve(K[np.ix_(free, free)], F[free])
        R = K @ U - F                                         # reactions (plus equivalent loads) at fixed DOFs
        res = {"u": {n: U[DOF * index[n]:DOF * index[n] + 6].copy() for n in names},
               "reactions": {n: R[DOF * index[n]:DOF * index[n] + 6].copy() for n in self.fix},
               "forces": {}, "zero_stiffness_dofs": int(free_zero.sum())}
        for name, e in self.elements.items():
            T, kc, fc, cond, k, fef, L = cache[name]
            dofs = np.r_[DOF * index[e["i"]]:DOF * index[e["i"]] + 6, DOF * index[e["j"]]:DOF * index[e["j"]] + 6]
            ul = T @ U[dofs]
            if cond is not None:                              # recover the released displacements
                rel, keep, inv, krk = cond
                ul = ul.copy()
                ul[rel] = -inv @ (krk @ ul[keep] + fef[rel])
            f_end = k @ ul + fef                              # element end forces, local axes
            res["forces"][name] = f_end
        res["_cache"] = cache
        return res

    def internal(self, res, name, case, stations=11):
        """Internal forces along an element at `stations` points, as the forces the part beyond the
        cut exerts on the part from node i to the cut (local axes): N (tension +), Vy, Vz, T, My, Mz.
        At the j end they equal the element's j-end forces; tests check that."""
        e = self.elements[name]
        R3, L = self.axes(e)
        f = res["forces"][name]
        w = self.cases.get(case, {"udl": {}})["udl"].get(name)
        wx, wy, wz = R3 @ w if w is not None else np.zeros(3)
        out = []
        for s in np.linspace(0.0, L, stations):
            N = -f[0] - wx * s
            Vy = -f[1] - wy * s
            Vz = -f[2] - wz * s
            T_ = -f[3]
            My = -f[4] - f[2] * s - wz * s * s / 2.0
            Mz = -f[5] + f[1] * s + wy * s * s / 2.0
            out.append((s, N, Vy, Vz, T_, My, Mz))
        return out
