#!/usr/bin/env python3
"""Verify checked receipts, optionally rebuilding them from exact public inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parent
AUDIT = PACKAGE_ROOT / "audit.py"


class VerificationFailure(RuntimeError):
    pass


def require(condition: bool, detail: str) -> None:
    if not condition:
        raise VerificationFailure(detail)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def read_json_object(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise VerificationFailure(f"invalid JSON receipt {path.name}: {exc}") from exc
    require(isinstance(value, dict), f"JSON receipt is not an object: {path.name}")
    return value


def source_bound_comparison_projection(path: Path) -> bytes:
    value = read_json_object(path)
    expected_top = {
        "schema_version",
        "status",
        "run_a",
        "run_b",
        "stable_receipts",
        "all_stable_receipts_byte_identical",
        "fresh_process_identity",
        "boundary",
    }
    require(set(value) == expected_top, f"unexpected comparison schema: {path.name}")
    projected_runs = {}
    for field in ("run_a", "run_b"):
        run = value[field]
        require(isinstance(run, dict), f"invalid comparison run: {field}")
        expected_run = {
            "label",
            "python_hash_seed",
            "traversal_seed",
            "environment_receipt_sha256",
            "checker_sha256",
        }
        require(set(run) == expected_run, f"unexpected comparison run schema: {field}")
        projected_runs[field] = {
            key: run[key]
            for key in (
                "label",
                "python_hash_seed",
                "traversal_seed",
                "checker_sha256",
            )
        }
    projection = {
        "schema_version": value["schema_version"],
        "status": value["status"],
        "run_a": projected_runs["run_a"],
        "run_b": projected_runs["run_b"],
        "stable_receipts": value["stable_receipts"],
        "all_stable_receipts_byte_identical": value[
            "all_stable_receipts_byte_identical"
        ],
        "fresh_process_identity": value["fresh_process_identity"],
        "boundary": value["boundary"],
    }
    return canonical_bytes(projection)


def command(args: list[str], *, seed: int | None = None) -> None:
    environment = os.environ.copy()
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["LC_ALL"] = "C.UTF-8"
    environment["TZ"] = "UTC"
    if seed is not None:
        environment["PYTHONHASHSEED"] = str(seed)
    result = subprocess.run(
        args,
        env=environment,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if result.stdout:
        print(result.stdout, end="")
    require(result.returncode == 0, result.stderr.strip() or "command failed")


def receipt_only() -> None:
    command(
        [
            sys.executable,
            str(AUDIT),
            "verify-installed",
            "--package-root",
            str(PACKAGE_ROOT),
        ]
    )


def source_bound(source: Path, paper_pdf: Path, work_root: Path) -> None:
    require(source.is_dir(), f"missing source directory: {source}")
    require(paper_pdf.is_file(), f"missing paper PDF: {paper_pdf}")
    require(not work_root.exists(), f"work root already exists: {work_root}")
    work_root.mkdir(parents=True)
    run_a = work_root / "run-a"
    run_b = work_root / "run-b"
    comparison = work_root / "repeatability.json"

    command(
        [
            sys.executable,
            str(AUDIT),
            "run",
            "--source",
            str(source),
            "--paper-pdf",
            str(paper_pdf),
            "--output",
            str(run_a),
            "--run-label",
            "A",
            "--traversal-seed",
            "313",
        ],
        seed=313,
    )
    command(
        [
            sys.executable,
            str(AUDIT),
            "run",
            "--source",
            str(source),
            "--paper-pdf",
            str(paper_pdf),
            "--output",
            str(run_b),
            "--run-label",
            "B",
            "--traversal-seed",
            "727",
        ],
        seed=727,
    )
    command(
        [
            sys.executable,
            str(AUDIT),
            "compare",
            "--run-a",
            str(run_a),
            "--run-b",
            str(run_b),
            "--output",
            str(comparison),
        ]
    )

    for rebuilt_root in (run_a, run_b):
        for rel in ("audit.json", "mutation-controls.json"):
            rebuilt = rebuilt_root / rel
            installed = PACKAGE_ROOT / "raw" / rel
            require(installed.is_file(), f"missing installed receipt: {rel}")
            require(
                rebuilt.read_bytes() == installed.read_bytes(),
                f"source-bound receipt differs: {rebuilt_root.name}/{rel} "
                f"rebuilt={sha256(rebuilt)} installed={sha256(installed)}",
            )
    installed_comparison = PACKAGE_ROOT / "raw/repeatability.json"
    require(installed_comparison.is_file(), "missing installed repeatability receipt")
    require(
        source_bound_comparison_projection(comparison)
        == source_bound_comparison_projection(installed_comparison),
        "source-bound deterministic comparison projection differs",
    )
    receipt_only()
    print(
        "PASS: this source-bound invocation executed two fresh roots; both stable "
        "receipt sets byte-match the checked package"
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode", choices=("receipt-only", "source-bound"), default="receipt-only"
    )
    parser.add_argument("--source", type=Path)
    parser.add_argument("--paper-pdf", type=Path)
    parser.add_argument("--work-root", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.mode == "receipt-only":
            receipt_only()
        else:
            require(args.source is not None, "--source is required in source-bound mode")
            require(args.paper_pdf is not None, "--paper-pdf is required in source-bound mode")
            require(args.work_root is not None, "--work-root is required in source-bound mode")
            source_bound(args.source.resolve(), args.paper_pdf.resolve(), args.work_root.resolve())
    except VerificationFailure as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
