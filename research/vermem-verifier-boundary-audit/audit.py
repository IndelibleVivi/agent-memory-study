"""Exercise the pinned upstream LocalVerifier on public synthetic inputs."""

import argparse
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import types


HERE = Path(__file__).resolve().parent
UPSTREAM = "https://github.com/Sun-SYSU-24/VerMem"
COMMIT = "4782751c79faa08421a27c23b4d02c591bc3357d"
MODULES = ("memory_operations", "memory_schemas", "local_verifier")


def load_verifier(checkout):
    """Use the exact public source without vendoring or importing training."""
    head = subprocess.check_output(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"], text=True
    ).strip()
    if head != COMMIT:
        raise ValueError(f"Expected upstream commit {COMMIT}; got {head}")
    paths = [f"00_verifiers/{name}.py" for name in MODULES]
    subprocess.run(
        ["git", "-C", str(checkout), "diff", "--exit-code", "HEAD", "--", *paths],
        check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )
    # The numbered upstream directory needs a package name for relative imports.
    # Load only the three modules under test; do not run its broad __init__.
    package = types.ModuleType("ams_vermem_source")
    package.__path__ = [str(checkout / "00_verifiers")]
    sys.modules[package.__name__] = package
    loaded = {}
    for name, path in zip(MODULES, paths):
        qualified = f"{package.__name__}.{name}"
        spec = importlib.util.spec_from_file_location(qualified, checkout / path)
        module = importlib.util.module_from_spec(spec)
        sys.modules[qualified] = module
        spec.loader.exec_module(module)
        loaded[name] = module
    return loaded


def run(checkout):
    modules = load_verifier(checkout)
    operations = modules["memory_operations"]
    verifier = modules["local_verifier"].LocalVerifier(
        modules["memory_schemas"].AgentMemoryConfig()
    )
    fixtures = json.loads((HERE / "fixtures.json").read_text())
    rows = []
    for case in fixtures["cases"]:
        inputs = copy.deepcopy(case["inputs"])
        proposal = operations.MemoryOperationProposal.from_dict(inputs["proposal"])
        result = operations.MemoryOperationResult.from_dict(inputs["result"])
        before = (proposal.to_dict(), result.to_dict(), copy.deepcopy(inputs["context"]))
        report = verifier.verify(proposal, result, inputs["context"]).to_dict()
        # UUID identifies a call, not its decision. Retain every other report field.
        report.pop("verification_id")
        unchanged = before == (proposal.to_dict(), result.to_dict(), inputs["context"])
        rows.append({
            "id": case["id"], "role": case["role"],
            "input": case["inputs"], "report": report,
            "expectedVerdict": case["expectedVerdict"],
            "expectationMatched": report["verdict"] == case["expectedVerdict"],
            "inputUnchanged": unchanged,
        })
    return {
        "upstream": UPSTREAM, "commit": COMMIT,
        "executedModules": [f"00_verifiers/{name}.py" for name in MODULES],
        "method": "Direct LocalVerifier calls; synthetic proposal/result pairs; no executor or model.",
        "normalization": "Only each random verification_id is omitted from the returned report.",
        "results": rows,
        "summary": {
            "cases": len(rows),
            "controls": sum(row["role"] == "control" for row in rows),
            "counterexamplesAccepted": sum(
                row["role"] == "counterexample" and row["report"]["verdict"] == "pass"
                for row in rows
            ),
            "allExpectationsMatched": all(row["expectationMatched"] for row in rows),
            "allInputsUnchanged": all(row["inputUnchanged"] for row in rows),
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True, help="Pinned external VerMem checkout")
    parser.add_argument("--check", action="store_true", help="Execute upstream and compare with saved results")
    args = parser.parse_args()
    result = run(args.upstream.resolve())
    if not result["summary"]["allExpectationsMatched"] or not result["summary"]["allInputsUnchanged"]:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        raise SystemExit("FAIL: observed verifier behavior differs from the characterized contract")
    if args.check:
        saved = json.loads((HERE / "results.json").read_text())
        if result != saved:
            raise SystemExit("FAIL: fresh upstream execution differs from saved results")
        print("PASS: 12 upstream verifier cases match saved results; 7 controls; 5 accepted counterexamples")
    else:
        print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
