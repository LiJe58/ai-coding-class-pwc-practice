import csv
import sqlite3
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, HTTPException


app = FastAPI(title="Internal Control Lab")
ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "input" / "day-1"
DB_PATH = ROOT / "backend" / "data" / "day1_control_test.sqlite3"
TEST_RUN_ID = "DAY1-2026-08-V1"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"
SCHEMAS = {
    "vendor_changes.csv": ["change_id", "case_id", "vendor_id", "request_id", "requested_at", "requested_by", "before_account_token", "requested_account_token", "changed_at", "changed_by", "change_reason"],
    "vendor_master.csv": ["vendor_id", "vendor_name", "business_registration_no_masked", "vendor_status", "vendor_type", "bank_code", "bank_name", "account_holder", "current_account_masked", "current_account_token", "last_updated_at", "last_updated_by"],
    "change_approvals.csv": ["approval_id", "change_id", "approval_stage", "decision", "approved_at", "approved_by", "approved_account_token", "approval_note"],
    "evidence_register.csv": ["evidence_id", "request_id", "document_type", "document_name", "document_status", "issued_date", "received_at", "verified_at", "verified_by", "document_account_token", "storage_ref", "note"],
    "payment_requests.csv": ["payment_id", "vendor_id", "change_id", "requested_at", "scheduled_date", "amount_krw", "payment_status", "payment_purpose", "beneficiary_account_token", "requested_by"],
    "user_roles.csv": ["user_id", "user_name", "department", "position", "role_name", "user_status", "valid_from", "valid_to", "permissions"],
}
RULE_NAMES = {"R-01": "필수값과 형식", "R-02": "변경 전 승인", "R-03": "요청·승인 업무 분리", "R-04": "승인 계좌와 ERP 일치"}


def read_inputs() -> dict[str, list[dict[str, str]]]:
    data = {}
    for filename, fields in SCHEMAS.items():
        try:
            with (INPUT_DIR / filename).open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                if reader.fieldnames != fields:
                    raise ValueError(f"{filename} 헤더가 입력 명세와 다릅니다.")
                data[filename] = list(reader)
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
    return data


def timestamp(value: str) -> datetime:
    return datetime.strptime(value, TIMESTAMP_FORMAT)


def rule(rule_id: str, result: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "rule_name": RULE_NAMES[rule_id], "result": result, "detail": detail}


def build_result() -> dict:
    data = read_inputs()
    changes = data["vendor_changes.csv"]
    vendors = {row["vendor_id"]: row for row in data["vendor_master.csv"]}
    approvals = defaultdict(list)
    evidence = defaultdict(list)
    payments = defaultdict(list)
    for row in data["change_approvals.csv"]:
        approvals[row["change_id"]].append(row)
    for row in data["evidence_register.csv"]:
        evidence[row["request_id"]].append(row)
    for row in data["payment_requests.csv"]:
        payments[row["change_id"]].append(row)
    id_counts = Counter(row["change_id"] for row in changes if row["change_id"])
    required = ["change_id", "case_id", "vendor_id", "request_id", "requested_by", "before_account_token", "requested_account_token", "changed_by"]
    population = []
    for change in changes:
        errors = [f"{field} 필수값 누락" for field in required if not change[field].strip()]
        parsed = {}
        for field in ("requested_at", "changed_at"):
            try:
                parsed[field] = timestamp(change[field])
            except ValueError:
                errors.append(f"{field} 형식 오류 ({TIMESTAMP_FORMAT})")
        if change["change_id"] and id_counts[change["change_id"]] > 1:
            errors.append("중복 change_id")
        vendor = vendors.get(change["vendor_id"], {})
        base = {
            **change,
            "vendor_name": vendor.get("vendor_name", "연결 불가"),
            "erp_account_token": vendor.get("current_account_token", ""),
            "approval_ids": [],
            "evidence_ids": [row["evidence_id"] for row in evidence[change["request_id"]]],
            "payment_ids": [row["payment_id"] for row in payments[change["change_id"]]],
        }
        if errors:
            base.update({"status": "error", "reason": "; ".join(errors), "rules": [rule("R-01", "fail", "; ".join(errors) + "; R-02~R-04 평가 제외")]})
            population.append(base)
            continue
        candidates = [row for row in approvals[change["change_id"]] if row["decision"] == "승인"]
        final = [row for row in candidates if row["approval_stage"] == "최종 승인"] or candidates
        approval = max(final, key=lambda row: timestamp(row["approved_at"]), default=None)
        rules = [rule("R-01", "pass", "필수값·날짜 형식·change_id 중복 확인 완료")]
        if approval is None:
            rules += [rule("R-02", "fail", "최종 승인 기록 없음"), rule("R-03", "not_applicable", "최종 승인 기록이 없어 평가 불가"), rule("R-04", "not_applicable", "최종 승인 기록이 없어 평가 불가")]
        else:
            approved = timestamp(approval["approved_at"])
            rules.append(rule("R-02", "pass" if approved <= parsed["changed_at"] else "fail", "ERP 반영 전 또는 같은 시각 승인" if approved <= parsed["changed_at"] else "ERP 반영 후 승인"))
            separated = change["requested_by"] != approval["approved_by"]
            rules.append(rule("R-03", "pass" if separated else "fail", "요청자와 최종 승인자 분리" if separated else "요청자와 최종 승인자가 동일"))
            matched = approval["approved_account_token"] == vendor.get("current_account_token", "")
            rules.append(rule("R-04", "pass" if matched else "fail", "승인 계좌와 ERP 계좌 일치" if matched else "승인 계좌와 ERP 계좌 불일치"))
        failures = [item for item in rules if item["result"] == "fail" and item["rule_id"] != "R-01"]
        base.update({"status": "review" if failures else "normal", "reason": "; ".join(item["detail"] for item in failures) if failures else "핵심 규칙 모두 충족", "approval_ids": [approval["approval_id"]] if approval else [], "rules": rules})
        population.append(base)
    summary = {
        "population_count": len(population),
        "valid_count": sum(row["status"] != "error" for row in population),
        "normal_count": sum(row["status"] == "normal" for row in population),
        "review_count": sum(row["status"] == "review" for row in population),
        "input_error_count": sum(row["status"] == "error" for row in population),
    }
    return {"test_run_id": TEST_RUN_ID, "summary": summary, "population": population, "exceptions": [row for row in population if row["status"] == "review"], "input_errors": [row for row in population if row["status"] == "error"], "persistence": None}


def persist_result(result: dict) -> dict:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as connection, connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS control_test_runs (test_run_id TEXT PRIMARY KEY, population_count INTEGER, valid_count INTEGER, normal_count INTEGER, review_count INTEGER, input_error_count INTEGER);
            CREATE TABLE IF NOT EXISTS population_results (test_run_id TEXT, change_id TEXT, status TEXT, PRIMARY KEY (test_run_id, change_id));
            CREATE TABLE IF NOT EXISTS rule_results (test_run_id TEXT, change_id TEXT, rule_id TEXT, result TEXT, detail TEXT, PRIMARY KEY (test_run_id, change_id, rule_id));
            CREATE TABLE IF NOT EXISTS input_errors (test_run_id TEXT, change_id TEXT, errors TEXT, PRIMARY KEY (test_run_id, change_id));
        """)
        summary = result["summary"]
        connection.execute("INSERT OR REPLACE INTO control_test_runs VALUES (?, ?, ?, ?, ?, ?)", (TEST_RUN_ID, *summary.values()))
        for table in ("population_results", "rule_results", "input_errors"):
            connection.execute(f"DELETE FROM {table} WHERE test_run_id = ?", (TEST_RUN_ID,))
        for row in result["population"]:
            if row["status"] == "error":
                connection.execute("INSERT INTO input_errors VALUES (?, ?, ?)", (TEST_RUN_ID, row["change_id"], row["reason"]))
            else:
                connection.execute("INSERT INTO population_results VALUES (?, ?, ?)", (TEST_RUN_ID, row["change_id"], row["status"]))
            for item in row["rules"]:
                connection.execute("INSERT INTO rule_results VALUES (?, ?, ?, ?, ?)", (TEST_RUN_ID, row["change_id"], item["rule_id"], item["result"], item["detail"]))
    return {"database": "backend/data/day1_control_test.sqlite3", "valid_population_rows": summary["valid_count"]}


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ready", "message": "실습 처리 영역이 준비되었습니다."}


@app.get("/api/control-test")
def get_control_test() -> dict:
    return build_result()


@app.post("/api/control-test/run")
def run_control_test() -> dict:
    result = build_result()
    result["persistence"] = persist_result(result)
    return result
