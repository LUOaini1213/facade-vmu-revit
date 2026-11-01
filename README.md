# facade-vmu-revit

Python code for a **fictional** two-storey facade visual mock-up (VMU): a unitised curtain wall on a
free-standing steel frame. The building behind the facade is invented; nothing here is taken from a real
project. Every number lives in `vmu/config.py`, tagged as a geometry decision, an assumption a real project
would take from a supplier or survey, or a value taken from a named standard clause.

**Status: early.** The geometry, load and analysis library is written and tested. The Revit jobs that would
build the model through Dynamo are not written yet (`revit/jobs/` is empty), so there is no model, IFC or
drawing output.

## What is here

| Path | What it does |
|---|---|
| `vmu/config.py` | Every number the mock-up is built from, in one place |
| `vmu/geometry.py` | Where each unit and its parts, the anchors, the steel and the footings go |
| `vmu/extrusions.py`, `vmu/profiles.py` | The aluminium extrusions of the unitised frame and their exact section outlines and properties |
| `vmu/sections.py` | Cold-formed structural hollow sections (EN 10219) |
| `vmu/loads.py` | Weights of the facade parts and what each anchor receives |
| `vmu/wind.py` | EN 1991-1-4 peak velocity pressure and free-standing-wall net pressures |
| `vmu/frame.py` | A small linear-elastic 3D frame solver (direct stiffness method), written to be read |
| `vmu/rvt.py`, `revit/bridge/`, `tools/` | Helpers for running Python jobs inside Revit 2027 through a Dynamo bridge |

## Tests

```bash
python -m pytest -q
```

`tests/test_frame.py` checks the frame solver against closed-form results and against equilibrium
(10 tests). The structural numbers are illustrative, not a design.
