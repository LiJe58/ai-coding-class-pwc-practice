import csv
import io
import json
import sqlite3
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field, field_validator


app = FastAPI(title="Internal Control Day 1")
ROOT = Path(__file__).resolve().parents[2]
INPUT_DIR = ROOT / "input" / "day-1"
DB_PATH = ROOT / "backend" / "data" / "day1_control_test.sqlite3"
DAY3_DB_PATH = ROOT / "backend" / "data" / "day3_reviews.sqlite3"
WORKING_PAPER_PATH = ROOT / "output" / "day-2" / "working-paper.json"
TEST_RUN_ID = "DAY1-2026-08-V1"
DAY2_SAMPLE_IDS = [
    *[f"CHG-2608-{index:03d}" for index in range(1, 5)],
    *[f"CHG-2608-{index:03d}" for index in range(22, 30)],
]
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
EXPORT_FIELDS = [
    "source_test_run_id", "agent_run_id", "working_paper_generated_at", "sample_id",
    "change_id", "case_id", "vendor_id", "vendor_name", "selection_reason",
    "day1_status", "human_conclusion", "review_comment", "reviewer_user_id",
    "reviewed_at", "approval_ids", "evidence_ids", "payment_ids",
]


class ReviewRequest(BaseModel):
    review_action_id: uuid.UUID
    reviewer_user_id: str
    conclusion: Literal["normal", "follow_up", "control_exception"]
    review_comment: str = Field(min_length=1, max_length=1000)

    @field_validator("review_comment", mode="before")
    @classmethod
    def trim_comment(cls, value: object) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("검토 의견을 입력하세요.")
        return value.strip()


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


def load_working_paper() -> dict:
    try:
        paper = json.loads(WORKING_PAPER_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"status": "invalid", "message": str(error), "working_paper": None, "validation": {"valid": False, "errors": [str(error)]}}
    expected = {"schema_version": "1.0", "source_test_run_id": TEST_RUN_ID}
    errors = [f"{key} 불일치" for key, value in expected.items() if paper.get(key) != value]
    samples = paper.get("samples", [])
    if [sample.get("change_id") for sample in samples] != DAY2_SAMPLE_IDS:
        errors.append("Day 2 표본 목록 또는 순서 불일치")
    if len(samples) != 12 or any(sample.get("requires_human_review") is not True for sample in samples):
        errors.append("모든 표본 12건은 사람 검토가 필요합니다.")
    return {
        "status": "invalid" if errors else "ready",
        "message": errors[0] if errors else "Agent 통제 검토자료 12건을 불러왔습니다.",
        "working_paper": paper,
        "validation": {"valid": not errors, "errors": errors},
    }


def require_working_paper() -> dict:
    result = load_working_paper()
    if result["status"] != "ready":
        raise HTTPException(status_code=409, detail=result["message"])
    return result["working_paper"]


def require_reviewer(user_id: str) -> None:
    user = next((row for row in read_inputs()["user_roles.csv"] if row["user_id"] == user_id), None)
    permissions = set(user["permissions"].split(";")) if user else set()
    if not user or user["user_status"] != "활성" or "CONTROL_REVIEW" not in permissions:
        raise HTTPException(status_code=403, detail="활성 CONTROL_REVIEW 권한이 필요합니다.")


def open_review_db() -> sqlite3.Connection:
    DAY3_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DAY3_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("""
        CREATE TABLE IF NOT EXISTS review_events (
            event_id TEXT PRIMARY KEY,
            review_action_id TEXT NOT NULL UNIQUE,
            source_test_run_id TEXT NOT NULL,
            agent_run_id TEXT NOT NULL,
            working_paper_generated_at TEXT NOT NULL,
            change_id TEXT NOT NULL,
            reviewer_user_id TEXT NOT NULL,
            conclusion TEXT NOT NULL CHECK (conclusion IN ('normal', 'follow_up', 'control_exception')),
            review_comment TEXT NOT NULL CHECK (length(review_comment) BETWEEN 1 AND 1000),
            reviewed_at TEXT NOT NULL
        )
    """)
    return connection


def review_events() -> list[dict]:
    with closing(open_review_db()) as connection, connection:
        return [dict(row) for row in connection.execute("SELECT * FROM review_events ORDER BY rowid")]


def day3_payload(paper: dict, events: list[dict]) -> dict:
    current = {}
    for event in events:
        if event["working_paper_generated_at"] == paper["generated_at"]:
            current[event["change_id"]] = event
    items = []
    for sample in paper["samples"]:
        history = [
            {**event, "is_current_working_paper": event["working_paper_generated_at"] == paper["generated_at"]}
            for event in reversed(events) if event["change_id"] == sample["change_id"]
        ]
        items.append({
            **{key: sample[key] for key in ("sample_id", "change_id", "case_id", "vendor_id", "vendor_name", "day1_status", "selection_reason")},
            "current_review": current.get(sample["change_id"]),
            "history": history,
        })
    counts = Counter(event["conclusion"] for event in current.values())
    reviewed_count = len(current)
    summary = {
        "total_count": len(paper["samples"]),
        "reviewed_count": reviewed_count,
        "pending_count": len(paper["samples"]) - reviewed_count,
        "normal_count": counts["normal"],
        "follow_up_count": counts["follow_up"],
        "control_exception_count": counts["control_exception"],
        "export_ready": reviewed_count == len(paper["samples"]),
    }
    return {"status": "ready", "summary": summary, **summary, "items": items}


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


@app.get("/api/day2/working-paper")
def get_day2_working_paper() -> dict:
    return load_working_paper()


@app.get("/api/day3/reviews")
def get_day3_reviews() -> dict:
    return day3_payload(require_working_paper(), review_events())


@app.post("/api/day3/reviews/{change_id}")
def save_day3_review(change_id: str, request: ReviewRequest) -> dict:
    paper = require_working_paper()
    if change_id not in {sample["change_id"] for sample in paper["samples"]}:
        raise HTTPException(status_code=404, detail=f"고정 표본에 없는 change_id입니다: {change_id}")
    require_reviewer(request.reviewer_user_id)
    expected = {
        "review_action_id": str(request.review_action_id),
        "source_test_run_id": paper["source_test_run_id"],
        "agent_run_id": paper["agent_run_id"],
        "working_paper_generated_at": paper["generated_at"],
        "change_id": change_id,
        "reviewer_user_id": request.reviewer_user_id,
        "conclusion": request.conclusion,
        "review_comment": request.review_comment,
    }
    event = {
        "event_id": str(uuid.uuid4()),
        **expected,
        "reviewed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    with closing(open_review_db()) as connection, connection:
        existing = connection.execute("SELECT * FROM review_events WHERE review_action_id = ?", (expected["review_action_id"],)).fetchone()
        if existing:
            event = dict(existing)
            if any(event[key] != value for key, value in expected.items()):
                raise HTTPException(status_code=409, detail="같은 요청 ID가 다른 저장 내용에 이미 사용되었습니다.")
        else:
            connection.execute("INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(event.values()))
    return {"status": "saved", "event": event, "summary": day3_payload(paper, review_events())["summary"]}


@app.get("/api/day3/export.csv")
def export_day3_reviews(reviewer_user_id: str = Query(...)) -> Response:
    require_reviewer(reviewer_user_id)
    paper = require_working_paper()
    payload = day3_payload(paper, review_events())
    if not payload["export_ready"]:
        raise HTTPException(status_code=409, detail=f"사람 검토가 {payload['pending_count']}건 남았습니다.")
    current = {item["change_id"]: item["current_review"] for item in payload["items"]}
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=EXPORT_FIELDS, lineterminator="\r\n")
    writer.writeheader()
    for sample in paper["samples"]:
        event = current[sample["change_id"]]
        writer.writerow({
            "source_test_run_id": paper["source_test_run_id"],
            "agent_run_id": paper["agent_run_id"],
            "working_paper_generated_at": paper["generated_at"],
            **{key: sample[key] for key in ("sample_id", "change_id", "case_id", "vendor_id", "vendor_name", "selection_reason", "day1_status")},
            "human_conclusion": event["conclusion"],
            "review_comment": event["review_comment"],
            "reviewer_user_id": event["reviewer_user_id"],
            "reviewed_at": event["reviewed_at"],
            **{key: ";".join(sample["source_ids"][key]) for key in ("approval_ids", "evidence_ids", "payment_ids")},
        })
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="day3-human-reviews.csv"'},
    )
