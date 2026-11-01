"""Run a job inside Revit through the Dynamo bridge and wait for its result.

Usage: python tools/run_job.py <job name> [timeout seconds] [--set NAME=VALUE ...]

Copies revit/jobs/<job name>.py to the bridge's job.py with a small header
(repo path, job name, run time, and one string variable per --set), then
waits until bridge_state.json reports that exact file content as finished.
Needs Revit open with bridge.dyn loaded in Dynamo (Automatic run mode).

The v1 clash run, for example:
  python tools/run_job.py 06_structure --set CORNER_MODE=grid
  python tools/run_job.py 08_checks --set CLASH_FILE=clash_v1.csv
"""
import datetime
import hashlib
import json
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BRIDGE = Path(r"C:\Users\LW\revit_bridge")


def main():
    args = sys.argv[1:]
    settings = []
    while "--set" in args:
        i = args.index("--set")
        key, _, value = args[i + 1].partition("=")
        if not key.isidentifier():
            raise SystemExit("--set needs NAME=VALUE, got %r" % args[i + 1])
        settings.append((key, value))
        del args[i:i + 2]
    name = args[0]
    timeout = float(args[1]) if len(args) > 1 else 900.0
    body = (REPO / "revit" / "jobs" / (name + ".py")).read_text(encoding="utf-8")
    header = "REPO = %r\nJOB_NAME = %r\nRUN_AT = %r\n" % (
        str(REPO), name, datetime.datetime.now().isoformat(timespec="seconds"))
    header += "".join("%s = %r\n" % kv for kv in settings)
    text = header + body
    sha = hashlib.sha1(text.encode("utf-8")).hexdigest()
    (BRIDGE / "job.py").write_text(text, encoding="utf-8", newline="\n")
    state = BRIDGE / "bridge_state.json"
    start = time.time()
    while time.time() - start < timeout:
        try:
            rec = json.loads(state.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rec = {}
        if rec.get("sha1") == sha and "finished" in rec:
            sys.stdout.reconfigure(encoding="utf-8")
            print(json.dumps(rec, ensure_ascii=False, indent=2))
            return 0 if rec.get("status") == "ok" else 1
        time.sleep(1.0)
    print("timed out after %.0f s waiting for %s (is Dynamo open with bridge.dyn?)" % (timeout, name))
    return 2


if __name__ == "__main__":
    sys.exit(main())
