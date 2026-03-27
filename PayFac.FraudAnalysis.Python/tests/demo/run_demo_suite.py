"""Run demo test cases from tests/demo/demo_test_cases.json.

Usage:
  python tests/demo/run_demo_suite.py --base-url http://localhost:8000

Notes:
  - This runner executes HTTP-based cases.
  - SQL/manual validation steps are printed for operator follow-up.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import requests


def load_cases(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def run_http_case(base_url: str, case: dict[str, Any]) -> tuple[bool, str]:
    req = case["request"]
    method = req.get("method", "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return True, f"SKIP non-http case ({method})"

    path = req["path"]
    url = base_url.rstrip("/") + path
    payload = req.get("json")

    try:
        if method == "GET":
            resp = requests.get(url, timeout=60)
        elif method == "POST":
            resp = requests.post(url, json=payload, timeout=120)
        elif method == "PUT":
            resp = requests.put(url, json=payload, timeout=120)
        elif method == "PATCH":
            resp = requests.patch(url, json=payload, timeout=120)
        else:
            resp = requests.delete(url, timeout=60)
    except Exception as exc:
        return False, f"ERROR request failed: {exc}"

    expected_status = case.get("expected", {}).get("status_code")
    ok = expected_status is None or resp.status_code == expected_status

    details = [f"HTTP {resp.status_code}"]
    if not ok:
        details.append(f"expected {expected_status}")

    try:
        body = resp.json()
        if isinstance(body, dict):
            keys = ", ".join(sorted(body.keys())[:8])
            details.append(f"body keys: {keys}")
    except Exception:
        details.append("body is non-JSON")

    return ok, " | ".join(details)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--suite-file",
        default="tests/demo/demo_test_cases.json",
        help="Path to demo suite json",
    )
    args = parser.parse_args()

    suite = load_cases(Path(args.suite_file))
    cases = suite.get("test_cases", [])

    passed = 0
    failed = 0
    skipped = 0

    print(f"Running {len(cases)} demo cases against {args.base_url}")

    for case in cases:
        case_id = case.get("id", "unknown")
        title = case.get("title", "")
        ok, msg = run_http_case(args.base_url, case)

        is_skip = msg.startswith("SKIP")
        if is_skip:
            skipped += 1
            status = "SKIP"
        elif ok:
            passed += 1
            status = "PASS"
        else:
            failed += 1
            status = "FAIL"

        print(f"[{status}] {case_id} - {title} :: {msg}")

        expected = case.get("expected", {})
        if "manual_validation" in expected:
            print("  Manual validation:")
            for step in expected["manual_validation"]:
                print(f"    - {step}")
        if "sql_validation" in expected:
            print(f"  SQL validation: {expected['sql_validation']}")

    print("\nSummary")
    print(f"  Passed:  {passed}")
    print(f"  Failed:  {failed}")
    print(f"  Skipped: {skipped}")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
