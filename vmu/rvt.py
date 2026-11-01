"""Helpers for the jobs that run inside Revit (Dynamo PythonNet3). Not importable outside Revit."""
import io
import json
import os

import clr

clr.AddReference("RevitAPI")
from Autodesk.Revit.DB import (BuiltInParameter, FilteredElementCollector, Transaction,
                               UnitTypeId, UnitUtils, XYZ)


def ft(mm):
    return UnitUtils.ConvertToInternalUnits(float(mm), UnitTypeId.Millimeters)


def mm(feet):
    return UnitUtils.ConvertFromInternalUnits(float(feet), UnitTypeId.Millimeters)


def xyz(x_mm, y_mm, z_mm=0.0):
    return XYZ(ft(x_mm), ft(y_mm), ft(z_mm))


def name_of(e):
    try:
        return e.Name
    except Exception:
        p = e.get_Parameter(BuiltInParameter.ALL_MODEL_TYPE_NAME)
        return p.AsString() if p else None


def of_class(doc, cls):
    return list(FilteredElementCollector(doc).OfClass(cls))


def find(doc, cls, name, family=None):
    for e in FilteredElementCollector(doc).OfClass(cls):
        if name_of(e) == name and (family is None or getattr(e, "FamilyName", None) == family):
            return e
    return None


class Tx(object):
    """Revit transaction that rolls back if the block raises."""

    def __init__(self, doc, name):
        self.t = Transaction(doc, name)

    def __enter__(self):
        self.t.Start()
        return self.t

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.t.Commit()
        else:
            self.t.RollBack()
        return False


def step_off(doc, uiapp, doomed_ids, fallback):
    """Revit cannot delete the active view, nor a sheet whose viewport is activated for editing.
    If the job is about to delete either, ask Revit to open `fallback` (it does so once the job
    has returned) and stop: the next run goes through."""
    from Autodesk.Revit.DB import Viewport
    doomed = {i.Value for i in doomed_ids}
    v = doc.ActiveView
    if v is None:
        return
    hosts = {vp.SheetId.Value for vp in FilteredElementCollector(doc).OfClass(Viewport)
             if vp.ViewId.Value == v.Id.Value}
    if v.Id.Value in doomed or hosts & doomed:
        uiapp.ActiveUIDocument.RequestViewChange(fallback)
        raise RuntimeError("%s is open and this job deletes it; Revit now switches to %s - run the job again"
                           % (v.Name, fallback.Name))


def write_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(obj, ensure_ascii=False, indent=2, default=str))
