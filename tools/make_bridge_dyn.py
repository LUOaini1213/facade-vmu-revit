"""Write bridge.dyn: String(path) -> File From Path -> Python node (bridge_node.py).

Usage: python tools/make_bridge_dyn.py <job.py path> <output .dyn path>

The node layout follows the JSON that Dynamo 4.2 itself saves (checked against
the templates shipped in Revit 2027's DynamoForRevit folder).
"""
import io
import json
import sys
import uuid
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent


def _id():
    return uuid.uuid4().hex


def _port(name, description):
    return {
        "Id": _id(),
        "Name": name,
        "Description": description,
        "UsingDefaultValue": False,
        "Level": 2,
        "UseLevels": False,
        "KeepListStructure": False,
    }


def build(job_path: str) -> dict:
    code = (HERE / "revit" / "bridge" / "bridge_node.py").read_text(encoding="utf-8")

    s_out = _port("", "String")
    string_node = {
        "ConcreteType": "CoreNodeModels.Input.StringInput, CoreNodeModels",
        "Id": _id(),
        "NodeType": "StringInputNode",
        "Inputs": [],
        "Outputs": [s_out],
        "Replication": "Disabled",
        "Description": "Creates a string.",
        "InputValue": job_path,
    }
    f_in, f_out = _port("path", "Path to the file."), _port("file", "File object")
    file_node = {
        "ConcreteType": "CoreNodeModels.Input.FileObject, CoreNodeModels",
        "Id": _id(),
        "NodeType": "ExtensionNode",
        "Inputs": [f_in],
        "Outputs": [f_out],
        "Replication": "Disabled",
        "Description": "Creates a file object from the given path",
    }
    p_in, p_out = _port("IN[0]", "Input #0"), _port("OUT", "Result of the python script")
    py_node = {
        "ConcreteType": "PythonNodeModels.PythonNode, PythonNodeModels",
        "Code": code,
        "Engine": "PythonNet3",
        "VariableInputPorts": True,
        "Id": _id(),
        "NodeType": "PythonScriptNode",
        "Inputs": [p_in],
        "Outputs": [p_out],
        "Replication": "Disabled",
        "Description": "Runs an embedded Python script.",
    }
    nodes = [string_node, file_node, py_node]
    connectors = [
        {"Start": s_out["Id"], "End": f_in["Id"], "Id": _id(), "IsHidden": "False"},
        {"Start": f_out["Id"], "End": p_in["Id"], "Id": _id(), "IsHidden": "False"},
    ]
    names = ["job.py path", "File From Path (watches job.py)", "Bridge: run job.py"]
    xs = [0.0, 420.0, 760.0]
    node_views = [
        {"Id": n["Id"], "Name": name, "IsSetAsInput": False, "IsSetAsOutput": False,
         "Excluded": False, "ShowGeometry": True, "X": x, "Y": 0.0}
        for n, name, x in zip(nodes, names, xs)
    ]
    return {
        "Uuid": str(uuid.uuid4()),
        "IsCustomNode": False,
        "Description": "Runs job.py inside Revit whenever the file changes (curved-facade-revit).",
        "Name": "bridge",
        "ElementResolver": {"ResolutionMap": {}},
        "Inputs": [],
        "Outputs": [],
        "Nodes": nodes,
        "Connectors": connectors,
        "Dependencies": [],
        "NodeLibraryDependencies": [],
        "EnableLegacyPolyCurveBehavior": True,
        "Thumbnail": "",
        "GraphDocumentationURL": None,
        "ExtensionWorkspaceData": [],
        "Author": "Wenjie Luo",
        "Linting": {"activeLinter": "None",
                    "activeLinterId": "7b75fb44-43fd-4631-a878-29f4d5d8399a",
                    "warningCount": 0, "errorCount": 0},
        "Bindings": [],
        "View": {
            "Dynamo": {"ScaleFactor": 1.0, "HasRunWithoutCrash": True,
                       "IsVisibleInDynamoLibrary": True, "Version": "4.2.1.5887",
                       "RunType": "Automatic", "RunPeriod": "1000"},
            "Camera": {"Name": "_Background Preview", "EyeX": -17.0, "EyeY": 24.0,
                       "EyeZ": 50.0, "LookX": 12.0, "LookY": -13.0, "LookZ": -58.0,
                       "UpX": 0.0, "UpY": 1.0, "UpZ": 0.0},
            "ConnectorPins": [],
            "NodeViews": node_views,
            "Annotations": [],
            "X": 60.0,
            "Y": 200.0,
            "Zoom": 0.9,
        },
    }


if __name__ == "__main__":
    job, out = sys.argv[1], sys.argv[2]
    with io.open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(build(job), f, ensure_ascii=False, indent=2)
    print("wrote", out)
