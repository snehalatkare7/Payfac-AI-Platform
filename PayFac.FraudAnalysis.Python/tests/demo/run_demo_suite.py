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
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.api.schemas import (
        AnalyzeTransactionRequest,
        BatchAnalyzeRequest,
        FeedbackRequest,
    )
except Exception:
    AnalyzeTransactionRequest = None
    BatchAnalyzeRequest = None
    FeedbackRequest = None


def load_cases(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _has_placeholder(value: Any) -> bool:
    if isinstance(value, str):
        return "<COPY" in value or value.strip().startswith("<")
    if isinstance(value, list):
        return any(_has_placeholder(v) for v in value)
    if isinstance(value, dict):
        return any(_has_placeholder(v) for v in value.values())
    return False


def _resolve_placeholders(req: dict, captured_ids: dict[str, str]) -> dict:
    """Attempt to replace placeholder decision_id values with captured alert_ids."""
    import copy
    resolved = copy.deepcopy(req)
    payload = resolved.get("json", {})
    if not isinstance(payload, dict):
        return resolved

    decision_id = payload.get("decision_id", "")
    if isinstance(decision_id, str) and "<COPY" in decision_id:
        # Extract the referenced case ID from the placeholder text
        # Patterns: "<COPY alert_id FROM TC-002 RESPONSE>"
        #           "<COPY alert_id FROM PREVIOUS /v1/analyze RESPONSE>"
        ref_match = re.search(r"TC-(\d+)", decision_id)
        if ref_match:
            ref_id = f"TC-{ref_match.group(1).zfill(3)}"
            if ref_id in captured_ids:
                payload["decision_id"] = captured_ids[ref_id]
        elif captured_ids:
            # Use the most recent captured alert_id
            payload["decision_id"] = list(captured_ids.values())[-1]

    resolved["json"] = payload
    return resolved


def _normalize_assertion(assertion: str) -> str:
    # Remove parenthetical guidance: "(LLM-dependent)", etc.
    return re.sub(r"\s*\([^)]*\)", "", assertion).strip()


def _extract_path(data: Any, path: str) -> Any:
    cur = data
    for part in path.split("."):
        if isinstance(cur, dict) and part in cur:
            cur = cur[part]
        else:
            raise KeyError(path)
    return cur


def _parse_list_literal(text: str) -> list[str]:
    try:
        parsed = json.loads(text.replace("'", '"'))
        if isinstance(parsed, list):
            return [str(v) for v in parsed]
    except Exception:
        pass
    return []


def _is_coherent_prose(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    # Reject obvious markdown list starts.
    if s.startswith(("-", "*", "#", "|", "•")):
        return False
    return len(s.split()) >= 5


def evaluate_assertion(assertion: str, body: Any) -> tuple[bool | None, str]:
    """Return (result, detail).

    result:
      - True  => assertion passed
      - False => assertion failed
      - None  => assertion unsupported (manual)
    """
    raw = assertion
    assertion = _normalize_assertion(assertion)
    low = assertion.lower()

    # Response-level checks
    if low == "response is an array":
        ok = isinstance(body, list)
        return ok, f"response array={ok}"

    m = re.match(r"^detail contains ['\"](.+?)['\"]$", assertion, flags=re.I)
    if m:
        needle = m.group(1).lower()
        detail = str(body.get("detail", "")).lower() if isinstance(body, dict) else ""
        ok = needle in detail
        return ok, f"detail contains '{needle}'={ok}"

    # Structured field checks require dict body
    if not isinstance(body, dict):
        return None, f"unsupported for non-dict body: {raw}"

    # "field between a and b"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+between\s+([0-9.]+)\s+and\s+([0-9.]+)$", assertion, flags=re.I)
    if m:
        field, lo, hi = m.group(1), float(m.group(2)), float(m.group(3))
        try:
            val = float(_extract_path(body, field))
            ok = lo <= val <= hi
            return ok, f"{field}={val}, expected [{lo}, {hi}]"
        except Exception:
            return False, f"missing/invalid field {field}"

    # "field is a non-empty array" / "field is an array"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+is\s+a\s+non-empty\s+array$", assertion, flags=re.I)
    if m:
        field = m.group(1)
        try:
            val = _extract_path(body, field)
            ok = isinstance(val, list) and len(val) > 0
            return ok, f"{field} non-empty array={ok}"
        except Exception:
            return False, f"missing field {field}"

    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+is\s+an\s+array$", assertion, flags=re.I)
    if m:
        field = m.group(1)
        try:
            val = _extract_path(body, field)
            ok = isinstance(val, list)
            return ok, f"{field} array={ok}"
        except Exception:
            return False, f"missing field {field}"

    # "field is boolean"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+is\s+boolean$", assertion, flags=re.I)
    if m:
        field = m.group(1)
        try:
            val = _extract_path(body, field)
            ok = isinstance(val, bool)
            return ok, f"{field} boolean={ok}"
        except Exception:
            return False, f"missing field {field}"

    # "analyzed_by_agents includes ['a','b']"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+includes\s+(\[.*\])$", assertion, flags=re.I)
    if m:
        field, list_text = m.group(1), m.group(2)
        expected_values = _parse_list_literal(list_text)
        try:
            val = _extract_path(body, field)
            if not isinstance(val, list):
                return False, f"{field} is not a list"
            missing = [v for v in expected_values if v not in val]
            ok = not missing
            return ok, f"{field} missing={missing}" if missing else f"{field} includes all expected"
        except Exception:
            return False, f"missing field {field}"

    # "field does NOT include 'x'"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+does\s+not\s+include\s+['\"](.+?)['\"]$", assertion, flags=re.I)
    if m:
        field, value = m.group(1), m.group(2)
        try:
            val = _extract_path(body, field)
            if isinstance(val, list):
                ok = value not in val
            else:
                ok = value not in str(val)
            return ok, f"{field} excludes '{value}'={ok}"
        except Exception:
            return False, f"missing field {field}"

    # "field in ['a','b']"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s+in\s+(\[.*\])$", assertion, flags=re.I)
    if m:
        field, list_text = m.group(1), m.group(2)
        allowed = _parse_list_literal(list_text)
        try:
            val = _extract_path(body, field)
            ok = str(val) in allowed
            return ok, f"{field}={val}, allowed={allowed}"
        except Exception:
            return False, f"missing field {field}"

    # Numeric comparisons: ==, <=, >=, <, >
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s*(==|<=|>=|<|>)\s*([0-9.]+)$", assertion)
    if m:
        field, op, rhs = m.group(1), m.group(2), float(m.group(3))
        try:
            lhs = float(_extract_path(body, field))
        except Exception:
            return False, f"missing/invalid field {field}"

        if op == "==":
            ok = lhs == rhs
        elif op == "<=":
            ok = lhs <= rhs
        elif op == ">=":
            ok = lhs >= rhs
        elif op == "<":
            ok = lhs < rhs
        else:
            ok = lhs > rhs
        return ok, f"{field}={lhs} {op} {rhs} => {ok}"

    # "field == 'value'"
    m = re.match(r"^([a-zA-Z0-9_\.]+)\s*==\s*['\"](.+?)['\"]$", assertion)
    if m:
        field, rhs = m.group(1), m.group(2)
        try:
            lhs = _extract_path(body, field)
            ok = str(lhs) == rhs
            return ok, f"{field}={lhs}, expected={rhs}"
        except Exception:
            return False, f"missing field {field}"

    # Coherence checks used by suite
    if low == "summary is a coherent prose sentence":
        ok = _is_coherent_prose(body.get("summary"))
        return ok, f"summary prose={ok}"

    if low.startswith("each item has:"):
        # Applies to list responses with dict items.
        fields_text = assertion.split(":", 1)[1].strip()
        fields = [f.strip() for f in fields_text.split(",") if f.strip()]
        if not isinstance(body, list):
            return False, "response is not an array"
        for idx, item in enumerate(body):
            if not isinstance(item, dict):
                return False, f"item[{idx}] is not an object"
            missing = [f for f in fields if f not in item]
            if missing:
                return False, f"item[{idx}] missing fields {missing}"
        return True, f"all items have required fields {fields}"

    return None, f"unsupported assertion: {raw}"


def evaluate_body_assertions(
    case: dict[str, Any],
    body: Any,
    strict_assertions: bool,
) -> tuple[bool, list[str], list[str]]:
    assertions = case.get("expected", {}).get("body_assertions", [])
    if not assertions:
        return True, [], []

    failures: list[str] = []
    manual: list[str] = []
    for assertion in assertions:
        result, detail = evaluate_assertion(assertion, body)
        if result is True:
            continue
        if result is False:
            failures.append(f"{assertion} -> {detail}")
            continue
        # result is None => unsupported/manual
        if strict_assertions:
            failures.append(f"{assertion} -> {detail}")
        else:
            manual.append(assertion)

    return len(failures) == 0, failures, manual


def validate_request_schema(case: dict[str, Any]) -> tuple[bool, str]:
    req = case.get("request", {})
    method = req.get("method", "GET").upper()
    path = req.get("path", "")
    payload = req.get("json")

    if method not in {"POST", "PUT", "PATCH"}:
        return True, "no body schema validation required"

    if payload is None:
        return False, "missing JSON payload"

    if _has_placeholder(payload):
        return True, "contains placeholders; skipped schema validation"

    def _fallback_validate_analyze(data: dict[str, Any]) -> tuple[bool, str]:
        required = {
            "transaction_id": str,
            "merchant_id": str,
            "amount_cents": int,
        }
        for field, typ in required.items():
            if field not in data:
                return False, f"missing required field: {field}"
            if not isinstance(data[field], typ):
                return False, f"field {field} must be {typ.__name__}"
        return True, "fallback validate AnalyzeTransactionRequest: OK"

    def _fallback_validate_batch(data: dict[str, Any]) -> tuple[bool, str]:
        txns = data.get("transactions")
        if not isinstance(txns, list) or not txns:
            return False, "transactions must be a non-empty array"
        for idx, txn in enumerate(txns):
            if not isinstance(txn, dict):
                return False, f"transactions[{idx}] must be object"
            ok, msg = _fallback_validate_analyze(txn)
            if not ok:
                return False, f"transactions[{idx}] invalid: {msg}"
        return True, "fallback validate BatchAnalyzeRequest: OK"

    def _fallback_validate_feedback(data: dict[str, Any]) -> tuple[bool, str]:
        if not isinstance(data.get("decision_id"), str) or not data.get("decision_id"):
            return False, "decision_id must be non-empty string"
        if not isinstance(data.get("was_correct"), bool):
            return False, "was_correct must be boolean"
        return True, "fallback validate FeedbackRequest: OK"

    try:
        if path == "/v1/analyze":
            if AnalyzeTransactionRequest is not None:
                AnalyzeTransactionRequest.model_validate(payload)
                return True, "valid AnalyzeTransactionRequest"
            return _fallback_validate_analyze(payload)
        if path == "/v1/analyze/batch":
            if BatchAnalyzeRequest is not None:
                BatchAnalyzeRequest.model_validate(payload)
                return True, "valid BatchAnalyzeRequest"
            return _fallback_validate_batch(payload)
        if path == "/v1/feedback":
            if FeedbackRequest is not None:
                FeedbackRequest.model_validate(payload)
                return True, "valid FeedbackRequest"
            return _fallback_validate_feedback(payload)
        return True, "no known schema mapping for this path"
    except Exception as exc:
        return False, f"schema validation failed: {exc}"


def run_http_case(
    base_url: str,
    case: dict[str, Any],
    strict_assertions: bool,
    captured_ids: dict[str, str] | None = None,
) -> tuple[bool, str]:
    req = case["request"]
    method = req.get("method", "GET").upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        return True, f"SKIP non-http case ({method})"

    # If execution_steps with multiple iterations, send preliminary warmup requests
    exec_steps = case.get("execution_steps", [])
    warmup_count = max(0, len(exec_steps) - 1)  # Send N-1 warmup calls

    path = req["path"]
    url = base_url.rstrip("/") + path
    payload = req.get("json")

    data_bytes = None
    headers = {"Content-Type": "application/json"}
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")

    # Warmup requests for velocity tests
    for i in range(warmup_count):
        import copy
        warmup_payload = copy.deepcopy(payload) if payload else None
        if warmup_payload and "transaction_id" in warmup_payload:
            warmup_payload["transaction_id"] = f"{warmup_payload['transaction_id']}-warmup-{i+1}"
        warmup_bytes = json.dumps(warmup_payload).encode("utf-8") if warmup_payload else None
        warmup_req = urllib.request.Request(url=url, data=warmup_bytes, headers=headers, method=method)
        try:
            with urllib.request.urlopen(warmup_req, timeout=120) as _resp:
                pass
        except Exception:
            pass  # Best-effort warmup

    request = urllib.request.Request(
        url=url,
        data=data_bytes,
        headers=headers,
        method=method,
    )

    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status_code = response.getcode()
            resp_text = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status_code = exc.code
        resp_text = exc.read().decode("utf-8", errors="replace") if hasattr(exc, "read") else ""
    except Exception as exc:
        return False, f"ERROR request failed: {exc}"

    expected_status = case.get("expected", {}).get("status_code")
    ok = expected_status is None or status_code == expected_status

    details = [f"HTTP {status_code}"]
    if not ok:
        details.append(f"expected {expected_status}")

    body = None
    try:
        body = json.loads(resp_text)
        if isinstance(body, dict):
            keys = ", ".join(sorted(body.keys())[:8])
            details.append(f"body keys: {keys}")
    except Exception:
        details.append("body is non-JSON")

    if body is not None and ok:
        # Capture alert_id for feedback test cases
        if captured_ids is not None and isinstance(body, dict):
            aid = body.get("alert_id")
            if aid:
                captured_ids[case.get("id", "")] = aid
            # Also capture from batch
            alerts = body.get("alerts")
            if isinstance(alerts, list):
                for idx, al in enumerate(alerts):
                    if isinstance(al, dict) and al.get("alert_id"):
                        captured_ids[f"{case.get('id', '')}_batch_{idx}"] = al["alert_id"]

        assertions_ok, failures, manual = evaluate_body_assertions(
            case, body, strict_assertions
        )
        if not assertions_ok:
            ok = False
            details.append(f"assertions_failed={len(failures)}")
            details.extend(f"assert_fail: {f}" for f in failures[:3])
        elif manual:
            details.append(f"manual_assertions={len(manual)}")

    return ok, " | ".join(details)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://localhost:8000")
    parser.add_argument(
        "--suite-file",
        default="tests/demo/demo_test_cases.json",
        help="Path to demo suite json",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help=(
            "Validate request schemas and case structure without making HTTP calls"
        ),
    )
    parser.add_argument(
        "--strict-assertions",
        action="store_true",
        help="Fail when an assertion is unsupported by the runner",
    )
    parser.add_argument(
        "--case-prefix",
        default="",
        help="Run only cases whose id starts with this prefix (e.g. TC-00)",
    )
    args = parser.parse_args()

    suite = load_cases(Path(args.suite_file))
    cases = suite.get("test_cases", [])
    if args.case_prefix:
        cases = [c for c in cases if c.get("id", "").startswith(args.case_prefix)]

    passed = 0
    failed = 0
    skipped = 0
    captured_ids: dict[str, str] = {}

    mode = "DRY-RUN" if args.dry_run else "HTTP"
    print(f"Running {len(cases)} demo cases in {mode} mode")
    if not args.dry_run:
        print(f"Target base URL: {args.base_url}")

    for case in cases:
        case_id = case.get("id", "unknown")
        title = case.get("title", "")
        req = case.get("request", {})
        if not req:
            skipped += 1
            print(f"[SKIP] {case_id} - {title} :: no HTTP request definition")
            expected = case.get("expected", {})
            if "manual_validation" in expected:
                print("  Manual validation:")
                for step in expected["manual_validation"]:
                    print(f"    - {step}")
            continue

        if _has_placeholder(req):
            # Try to resolve placeholders from captured alert_ids
            resolved = _resolve_placeholders(req, captured_ids)
            if _has_placeholder(resolved):
                skipped += 1
                print(f"[SKIP] {case_id} - {title} :: placeholder values present (no prior alert_id captured)")
                continue
            req = resolved
            case = {**case, "request": req}

        if args.dry_run:
            ok, msg = validate_request_schema(case)
        else:
            ok, msg = run_http_case(
                args.base_url,
                case,
                strict_assertions=args.strict_assertions,
                captured_ids=captured_ids,
            )

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
