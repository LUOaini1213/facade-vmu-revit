# Code of the Python node inside bridge.dyn (Dynamo 4.x, PythonNet3 engine).
#
# The graph is: String (path of job.py) -> File From Path -> this node.
# "File From Path" watches job.py, so with the graph in Automatic mode every
# save of job.py re-runs this node. The node runs the job once per distinct
# file content (SHA-1), inside Revit, and records the outcome next to the job
# in bridge_state.json so the result can be read from outside Revit.
import clr
import datetime
import hashlib
import io
import json
import os
import traceback

clr.AddReference("RevitAPI")
clr.AddReference("RevitServices")
from RevitServices.Persistence import DocumentManager
from RevitServices.Transactions import TransactionManager


def _now():
    return datetime.datetime.now().isoformat(timespec="seconds")


fi = IN[0]
path = str(fi.FullName) if hasattr(fi, "FullName") else str(fi)
folder = os.path.dirname(path)
state_path = os.path.join(folder, "bridge_state.json")

try:
    with io.open(path, encoding="utf-8") as f:
        src = f.read()
except Exception as e:
    src = None
    OUT = "cannot read %s: %s" % (path, e)

if src is not None:
    sha = hashlib.sha1(src.encode("utf-8")).hexdigest()
    try:
        with io.open(state_path, encoding="utf-8") as f:
            last = json.load(f).get("sha1")
    except Exception:
        last = None
    if sha == last:
        OUT = "skip: job %s already ran" % sha[:8]
    else:
        # Jobs manage their own Revit transactions so that a failing job can
        # roll back; Dynamo's own transaction must be closed first.
        TransactionManager.Instance.ForceCloseTransaction()
        ns = {
            "__name__": "__cf_job__",
            "JOB_PATH": path,
            "BRIDGE_DIR": folder,
            "doc": DocumentManager.Instance.CurrentDBDocument,
            "uiapp": DocumentManager.Instance.CurrentUIApplication,
        }
        rec = {"sha1": sha, "started": _now()}
        try:
            exec(compile(src, path, "exec"), ns)
            rec["status"] = "ok"
            rec["result"] = ns.get("RESULT")
        except Exception:
            rec["status"] = "error"
            rec["error"] = traceback.format_exc()
        rec["finished"] = _now()
        with io.open(state_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False, indent=2, default=str))
        OUT = "%s %s" % (rec["status"], sha[:8])
