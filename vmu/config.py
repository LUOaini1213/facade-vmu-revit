"""Every number the mock-up is built from, in one place.

Tags on each value:
  [geometry]    a design decision of this fictional mock-up; change it and the model follows
  [assumption]  a value a real project would take from a supplier, survey or specification
  [code]        a value taken from a standard; the clause is named

Units: millimetres for lengths, kN, kPa (= kN/m2), MPa, kg/m3, unless the name says otherwise.
Standard library only: the Revit jobs import this module inside Dynamo (CPython 3), the
structural checks import it outside Revit, and both must see the same numbers.

Axes: origin at the outside corner where the two glass planes meet, at ground level.
+X runs along face A (the long face), +Y into the mock-up, +Z up. Face A faces south
(outward normal -Y), face B faces west (outward normal -X). The building behind the
facade is fictional; nothing here is taken from a real project.
"""

# --- levels [geometry] ------------------------------------------------------------------
GL = 0.0                      # top of hardstanding = top of footings
LEVELS = {"L1": 1000.0, "L2": 5000.0, "L3": 9000.0}   # top of steel of the slab-edge beams
STOREYS = [("S1", "L1", "L2"), ("S2", "L2", "L3")]     # storey, bottom level, top level

# --- facade grid [geometry] --------------------------------------------------------------
MODULE = 1500.0               # unit module along both faces
JOINT = 15.0                  # every unit joint, vertical and horizontal (stack)
STACK_ABOVE_FL = 150.0        # stack-joint centreline above floor level
FACE_A_MODULES = 6            # face A: 6 x 1500 = 9000 mm
FACE_B_MODULES = 2            # face B (the return): 2 x 1500 = 3000 mm
CORNER_JOINT_AT = 150.0       # corner-post joint centreline, measured from each glass plane

# --- unitised frame (all members are aluminium extrusions of this project's own design) --
IGU = (8.0, 16.0, 8.0)        # [assumption] outer lite, cavity, inner lite: 8 HS / 16 / 8 HS
SPANDREL_GLASS = 8.0          # [assumption] single 8 mm heat-strengthened, ceramic frit
SOLID_PANEL = 3.0             # [assumption] 3 mm solid aluminium panel face
BACKPAN = 1.5                 # [assumption] aluminium back-pan behind spandrel and solid zones
INSULATION = 50.0             # [assumption] mineral wool in front of the back-pan
TUBE_FACE = 35.0              # glass inner face at 32 + 3 mm structural gasket
WALL = 3.0                    # wall thickness of every extrusion
MULLION_W = 50.0              # half-mullion width in elevation (= cap width)
MULLION_D = 150.0             # tube depth of mullions (w 35..185)
TRANSOM_D = 120.0             # tube depth of transoms (w 35..155)
CAP = 20.0                    # external caps project 20 mm outside the glass plane
BITE = 15.0                   # glass edge cover on the frame
STEM = 6.0                    # stem that carries each cap through the glass line
SILL_H = 90.0                 # sill and head transoms, height in elevation
HEAD_H = 90.0
MID_H = 70.0                  # vision / spandrel transom
MID_AT = 2850.0               # its centreline above the unit bottom
VENT_AT = 1650.0              # extra transom under the top-hung vent (unit type VO)
VENT_GAP = 5.0                # clearance between vent sash and its opening
SASH_W = 60.0                 # vent sash face width
SASH_D = 80.0                 # vent sash depth
INTERLOCK_CLEAR = 3.0         # clearance around tongues and slot legs
FIN_D = 250.0                 # vertical fins: projection beyond the caps
FIN_W = 50.0
EDGE_BEAM_FACE = 250.0        # slab-edge (steel edge beam) front face behind the glass plane

# unit type of each position; faces run from the corner (index 1) to the free end
UNIT_TYPES = {
    "S1": {"A": ["CV", "V", "VO", "V", "V", "S"], "B": ["CV", "S"]},
    "S2": {"A": ["CV", "V", "V", "V", "V", "S"], "B": ["CV", "S"]},
}
TYPE_NAMES = {"CV": "Corner vision unit", "V": "Vision unit", "VO": "Vision unit with top-hung vent",
              "S": "Solid aluminium unit"}

# --- anchors [geometry] --------------------------------------------------------------------
# One steel weldment per mullion line, bolted on top of the edge beam. Depth w is measured from the
# glass plane, heights from floor level (top of the edge beam).
BRACKET_PLATE = (150.0, 140.0, 12.0)   # base plate: along facade x depth x thickness, from w = 200
BRACKET_PLATE_W0 = 200.0
BRACKET_FIN = (10.0, 100.0, 100.0)     # upstand: thickness x depth (from w = 200) x height above the plate
BRACKET_HOOK = (150.0, 10.0, 52.0)     # hook bar: length x thickness x height
BRACKET_HOOK_W0 = 195.0                # hook bar front face: 10 mm behind the mullion back (185)
BRACKET_HOOK_Z0 = 60.0                 # hook bar bottom above floor level
BRACKET_BOLTS = (2, "M12", 8.8)        # [assumption] bolts to a cleat welded on the edge beam
BRACKET_FRONT = BRACKET_HOOK_W0
BRACKET_ADJUST = 25.0                  # [assumption] +- slotted adjustment in each direction
STEEL_TOLERANCE = 10.0                 # [assumption] erection deviation allowed for the frame
FACADE_TOLERANCE = 5.0                 # [assumption] unit setting-out tolerance

# --- steel frame [geometry] ---------------------------------------------------------------
COLUMN_X = [425.0, 3000.0, 6000.0, 8575.0]   # column centrelines along X
COLUMN_Y = [425.0, 3000.0]                   # front row, rear row
EDGE_AXIS = 300.0                            # edge-beam centreline behind each glass plane
EDGE_END = 50.0                              # edge beams run 50 mm past the last anchor
PLAN_BRACED_BAYS = [(0, 1), (2, 3)]          # column-index pairs along X with plan bracing
REAR_BRACED_BAYS = [(0, 1), (2, 3)]          # bays of the rear frame with vertical bracing
SECTIONS = {                                 # member group -> section designation
    "column": "SHS 150x150x6.3",
    "edge_beam": "RHS 200x100x6.3",          # 200 deep, 100 wide
    "cross_beam": "SHS 100x100x5",
    "rear_beam": "SHS 100x100x5",
    "brace": "CHS 76.1x3.2",
    "plan_brace": "CHS 60.3x3.2",
}
BASE_PLATE = (300.0, 300.0, 20.0)            # [geometry] per column
HD_BOLTS = (4, "M20", 8.8)                   # [assumption] holding-down bolts per base, grade
FOOTING = {"width": 1200.0, "overhang": 600.0, "depth": 700.0}   # strip under each Y-Z frame

# --- materials ----------------------------------------------------------------------------
STEEL = {"grade": "S355J2H", "fy": 355.0, "fu": 470.0, "E": 210000.0, "G": 81000.0,
         "density": 7850.0}                  # [code] EN 1993-1-1 3.2.6 and Table 3.1 (t <= 40 mm)
ALUMINIUM = {"alloy": "EN AW-6063 T6", "E": 70000.0, "G": 27000.0, "density": 2700.0}
GLASS_DENSITY = 2500.0                       # [code] EN 572-1
INSULATION_DENSITY = 100.0                   # [assumption]
CONCRETE_UNIT_WEIGHT = 25.0                  # [code] kN/m3, EN 1991-1-1 Table A.1 (reinforced)
BEARING_ALLOWABLE = 100.0                    # [assumption] kPa on the compacted hardstanding
FRICTION = 0.5                               # [assumption] concrete on hardstanding

# --- serviceability criteria of this project [assumption] ---------------------------------
EDGE_BEAM_DEFL = (500.0, 8.0)       # vertical, facade dead load: span / 500 and <= 8 mm
EDGE_BEAM_DEFL_H = (250.0, 15.0)    # horizontal, wind: span / 250 and <= 15 mm
SWAY_LIMIT = 300.0                  # top of frame, wind: height / 300
MULLION_DEFL = (175.0, 19.0)        # mullion, wind: span / 175 and <= 19 mm
STACK_MIN_GAP = 5.0                 # the 15 mm stack joint must stay open by at least this

# --- site ---------------------------------------------------------------------------------
SITE_ORIGIN = (1000.000, 2000.000)  # [geometry] E, N of the model origin on a local site grid (m)
TRUE_NORTH = 0.0                    # [geometry] degrees from project north to true north
