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

from .agent import (
    TOOL_NAME,
    AgentConfigurationError,
    AgentExecutionError,
    AgentModelError,
    AgentPermissionError,
    AgentToolError,
    create_agent_preview,
)


app = FastAPI(title="Internal Control Day 1")

WORKSPACE_DIR = Path(__file__).resolve().parents[2]
INPUT_DIR = WORKSPACE_DIR / "input" / "day-1"
DB_PATH = WORKSPACE_DIR / "backend" / "data" / "day1_control_test.sqlite3"
DAY3_DB_PATH = WORKSPACE_DIR / "backend" / "data" / "day3_reviews.sqlite3"
TEST_RUN_ID = "DAY1-2026-08-V1"
DAY2_SAMPLE_IDS = [
    "CHG-2608-001", "CHG-2608-002", "CHG-2608-003", "CHG-2608-004",
    "CHG-2608-022", "CHG-2608-023", "CHG-2608-024", "CHG-2608-025",
    "CHG-2608-026", "CHG-2608-027", "CHG-2608-028", "CHG-2608-029",
]
WORKING_PAPER_PATH = WORKSPACE_DIR / "output" / "day-2" / "working-paper.json"
TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"

SCHEMAS = {
    "vendor_changes.csv": ["change_id", "case_id", "vendor_id", "request_id", "requested_at", "requested_by", "before_account_token", "requested_account_token", "changed_at", "changed_by", "change_reason"],
    "vendor_master.csv": ["vendor_id", "vendor_name", "business_registration_no_masked", "vendor_status", "vendor_type", "bank_code", "bank_name", "account_holder", "current_account_masked", "current_account_token", "last_updated_at", "last_updated_by"],
    "change_approvals.csv": ["approval_id", "change_id", "approval_stage", "decision", "approved_at", "approved_by", "approved_account_token", "approval_note"],
    "evidence_register.csv": ["evidence_id", "request_id", "document_type", "document_name", "document_status", "issued_date", "received_at", "verified_at", "verified_by", "document_account_token", "storage_ref", "note"],
    "payment_requests.csv": ["payment_id", "vendor_id", "change_id", "requested_at", "scheduled_date", "amount_krw", "payment_status", "payment_purpose", "beneficiary_account_token", "requested_by"],
    "user_roles.csv": ["user_id", "user_name", "department", "position", "role_name", "user_status", "valid_from", "valid_to", "permissions"],
}

RULE_NAMES = {
    "R-01": "필수값과 형식",
    "R-02": "변경 전 승인",
    "R-03": "요청·승인 업무 분리",
    "R-04": "승인 계좌와 ERP 일치",
}

REVIEW_EVENT_FIELDS = [
    "event_id", "review_action_id", "source_test_run_id", "agent_run_id",
    "working_paper_generated_at", "change_id", "reviewer_user_id", "conclusion",
    "review_comment", "reviewed_at",
]
EXPORT_FIELDS = [
    "source_test_run_id", "agent_run_id", "working_paper_generated_at", "sample_id",
    "change_id", "case_id", "vendor_id", "vendor_name", "selection_reason",
    "day1_status", "human_conclusion", "review_comment", "reviewer_user_id",
    "reviewed_at", "approval_ids", "evidence_ids", "payment_ids",
]
AGENT_RUN_FIELDS = [
    "run_id", "change_id", "requester_user_id", "status", "permission_status",
    "configuration_status", "tool_name", "tool_arguments_json", "tool_status",
    "model_status", "answer", "error_code", "error_message", "started_at", "completed_at",
]


class ReviewRequest(BaseModel):
    review_action_id: uuid.UUID
    reviewer_user_id: str
    conclusion: Literal["normal", "follow_up", "control_exception"]
    review_comment: str = Field(min_length=1, max_length=1000)

    @field_validator("review_comment", mode="before")
    @classmethod
    def trim_comment(cls, value: object) -> str:
        if not isinstance(value, str):
            raise ValueError("검토 의견은 문자열이어야 합니다.")
        value = value.strip()
        if not value:
            raise ValueError("검토 의견을 입력해 주세요.")
        return value


class AgentPreviewRequest(BaseModel):
    requester_user_id: str = Field(min_length=1)


def read_inputs() -> dict[str, list[dict[str, str]]]:
    data = {}
    for filename, expected_fields in SCHEMAS.items():
        path = INPUT_DIR / filename
        try:
            with path.open(encoding="utf-8-sig", newline="") as file:
                reader = csv.DictReader(file)
                if reader.fieldnames != expected_fields:
                    raise ValueError(f"{filename} 헤더가 입력 명세와 다릅니다.")
                data[filename] = list(reader)
        except (OSError, UnicodeError, csv.Error, ValueError) as error:
            raise HTTPException(status_code=500, detail=str(error)) from error
    return data


def parse_timestamp(value: str) -> datetime:
    return datetime.strptime(value, TIMESTAMP_FORMAT)


def rule(rule_id: str, result: str, detail: str) -> dict[str, str]:
    return {"rule_id": rule_id, "rule_name": RULE_NAMES[rule_id], "result": result, "detail": detail}


def build_result() -> dict:
    data = read_inputs()
    changes = data["vendor_changes.csv"]
    vendors = {row["vendor_id"]: row for row in data["vendor_master.csv"]}
    users = {row["user_id"]: row for row in data["user_roles.csv"]}
    approvals_by_change = defaultdict(list)
    evidence_by_request = defaultdict(list)
    payments_by_change = defaultdict(list)
    for row in data["change_approvals.csv"]:
        approvals_by_change[row["change_id"]].append(row)
    for row in data["evidence_register.csv"]:
        evidence_by_request[row["request_id"]].append(row)
    for row in data["payment_requests.csv"]:
        payments_by_change[row["change_id"]].append(row)

    id_counts = Counter(row["change_id"] for row in changes if row["change_id"])
    required = ["change_id", "case_id", "vendor_id", "request_id", "requested_by", "before_account_token", "requested_account_token", "changed_by"]
    population = []

    for change in changes:
        errors = [f"{field} 필수값 누락" for field in required if not change[field].strip()]
        parsed_dates = {}
        for field in ("requested_at", "changed_at"):
            try:
                parsed_dates[field] = parse_timestamp(change[field])
            except ValueError:
                errors.append(f"{field} 형식 오류 ({TIMESTAMP_FORMAT})")
        if change["change_id"] and id_counts[change["change_id"]] > 1:
            errors.append("중복 change_id")

        vendor = vendors.get(change["vendor_id"], {})
        evidence_rows = evidence_by_request[change["request_id"]]
        payment_rows = payments_by_change[change["change_id"]]
        base = {
            **change,
            "vendor_name": vendor.get("vendor_name", "연결 불가"),
            "requested_by_name": users.get(change["requested_by"], {}).get("user_name", change["requested_by"]),
            "changed_by_name": users.get(change["changed_by"], {}).get("user_name", change["changed_by"]),
            "erp_account_token": vendor.get("current_account_token", ""),
            "current_account_masked": vendor.get("current_account_masked", ""),
            "approval_ids": [],
            "evidence_ids": [row["evidence_id"] for row in evidence_rows],
            "evidence_attention_ids": [row["evidence_id"] for row in evidence_rows if row["document_status"] in {"미수취", "추가 확인"}],
            "payment_ids": [row["payment_id"] for row in payment_rows],
            "amount_krw": sum(int(row["amount_krw"]) for row in payment_rows),
            "payment_risk": False,
            "payment_risk_note": "해당 없음",
        }

        if errors:
            base.update({
                "status": "error",
                "reason": "; ".join(errors),
                "approved_by_name": "평가 제외",
                "approved_account_token": "",
                "rules": [rule("R-01", "fail", "; ".join(errors) + "; R-02~R-04 평가 제외")],
            })
            population.append(base)
            continue

        changed_at = parsed_dates["changed_at"]
        candidates = [row for row in approvals_by_change[change["change_id"]] if row["decision"] == "승인"]
        final_candidates = [row for row in candidates if row["approval_stage"] == "최종 승인"] or candidates
        approval = max(final_candidates, key=lambda row: parse_timestamp(row["approved_at"]), default=None)
        rules = [rule("R-01", "pass", "필수값·날짜 형식·change_id 중복 확인 완료")]

        if approval is None:
            rules.extend([
                rule("R-02", "fail", "최종 승인 기록 없음"),
                rule("R-03", "not_applicable", "최종 승인 기록이 없어 평가 불가"),
                rule("R-04", "not_applicable", "최종 승인 기록이 없어 평가 불가"),
            ])
        else:
            approved_at = parse_timestamp(approval["approved_at"])
            rules.append(rule("R-02", "pass" if approved_at <= changed_at else "fail", "ERP 반영 전 또는 같은 시각 승인" if approved_at <= changed_at else "ERP 반영 후 승인"))
            separated = change["requested_by"] != approval["approved_by"]
            rules.append(rule("R-03", "pass" if separated else "fail", "요청자와 최종 승인자 분리" if separated else "요청자와 최종 승인자가 동일"))
            matched = approval["approved_account_token"] == vendor.get("current_account_token", "")
            rules.append(rule("R-04", "pass" if matched else "fail", "승인 계좌와 ERP 계좌 일치" if matched else "승인 계좌와 ERP 계좌 불일치"))

        risky_payments = []
        for payment in payment_rows:
            scheduled = parse_timestamp(payment["scheduled_date"])
            day_gap = (scheduled.date() - changed_at.date()).days
            if 0 <= day_gap <= 5 and int(payment["amount_krw"]) >= 10_000_000:
                risky_payments.append(payment)
        failures = [item for item in rules if item["result"] == "fail" and item["rule_id"] != "R-01"]
        base.update({
            "status": "review" if failures else "normal",
            "reason": "; ".join(item["detail"] for item in failures) if failures else "핵심 규칙 모두 충족",
            "approval_ids": [approval["approval_id"]] if approval else [],
            "approved_by_name": users.get(approval["approved_by"], {}).get("user_name", approval["approved_by"]) if approval else "승인 기록 없음",
            "approved_account_token": approval["approved_account_token"] if approval else "",
            "rules": rules,
            "payment_risk": bool(risky_payments),
            "payment_risk_note": "변경 후 5일 이내 10,000,000원 이상 지급 예정" if risky_payments else "해당 없음",
        })
        population.append(base)

    summary = {
        "population_count": len(population),
        "valid_count": sum(row["status"] != "error" for row in population),
        "normal_count": sum(row["status"] == "normal" for row in population),
        "review_count": sum(row["status"] == "review" for row in population),
        "input_error_count": sum(row["status"] == "error" for row in population),
        "duplicate_change_id_count": sum(count - 1 for count in id_counts.values() if count > 1),
    }
    return {
        "test_run_id": TEST_RUN_ID,
        "summary": summary,
        "sources": [{"filename": filename, "row_count": len(rows), "status": "ready"} for filename, rows in data.items()],
        "population": population,
        "exceptions": [row for row in population if row["status"] == "review"],
        "input_errors": [row for row in population if row["status"] == "error"],
        "persistence": None,
    }


def persist_result(result: dict) -> dict[str, int | str]:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    executed_at = datetime.now().astimezone().isoformat(timespec="seconds")
    with sqlite3.connect(DB_PATH) as connection:
        connection.executescript("""
            CREATE TABLE IF NOT EXISTS control_test_runs (
                test_run_id TEXT PRIMARY KEY, executed_at TEXT NOT NULL,
                population_count INTEGER NOT NULL, valid_count INTEGER NOT NULL,
                normal_count INTEGER NOT NULL, review_count INTEGER NOT NULL,
                input_error_count INTEGER NOT NULL
            );
            CREATE TABLE IF NOT EXISTS population_results (
                test_run_id TEXT NOT NULL, change_id TEXT NOT NULL, case_id TEXT NOT NULL,
                vendor_id TEXT NOT NULL, vendor_name TEXT NOT NULL, status TEXT NOT NULL,
                reason TEXT NOT NULL, PRIMARY KEY (test_run_id, change_id)
            );
            CREATE TABLE IF NOT EXISTS rule_results (
                test_run_id TEXT NOT NULL, change_id TEXT NOT NULL, rule_id TEXT NOT NULL,
                result TEXT NOT NULL, detail TEXT NOT NULL,
                PRIMARY KEY (test_run_id, change_id, rule_id)
            );
            CREATE TABLE IF NOT EXISTS input_errors (
                test_run_id TEXT NOT NULL, change_id TEXT NOT NULL, errors TEXT NOT NULL,
                PRIMARY KEY (test_run_id, change_id)
            );
        """)
        summary = result["summary"]
        connection.execute("""
            INSERT INTO control_test_runs VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(test_run_id) DO UPDATE SET
                executed_at=excluded.executed_at, population_count=excluded.population_count,
                valid_count=excluded.valid_count, normal_count=excluded.normal_count,
                review_count=excluded.review_count, input_error_count=excluded.input_error_count
        """, (TEST_RUN_ID, executed_at, summary["population_count"], summary["valid_count"], summary["normal_count"], summary["review_count"], summary["input_error_count"]))
        for table in ("population_results", "rule_results", "input_errors"):
            connection.execute(f"DELETE FROM {table} WHERE test_run_id = ?", (TEST_RUN_ID,))
        for row in result["population"]:
            if row["status"] == "error":
                connection.execute("INSERT INTO input_errors VALUES (?, ?, ?)", (TEST_RUN_ID, row["change_id"], row["reason"]))
            else:
                connection.execute("INSERT INTO population_results VALUES (?, ?, ?, ?, ?, ?, ?)", (TEST_RUN_ID, row["change_id"], row["case_id"], row["vendor_id"], row["vendor_name"], row["status"], row["reason"]))
            for item in row["rules"]:
                connection.execute("INSERT INTO rule_results VALUES (?, ?, ?, ?, ?)", (TEST_RUN_ID, row["change_id"], item["rule_id"], item["result"], item["detail"]))
    return {
        "database": "backend/data/day1_control_test.sqlite3",
        "valid_population_rows": summary["valid_count"],
        "rule_result_rows": sum(len(row["rules"]) for row in result["population"]),
        "input_error_rows": summary["input_error_count"],
    }


def validate_working_paper(payload: object) -> list[str]:
    if not isinstance(payload, dict):
        return ["최상위 JSON은 객체여야 합니다."]
    required = {"schema_version", "agent_run_id", "source_test_run_id", "generated_at", "mcp", "summary", "samples"}
    errors = [f"필수 필드 누락: {key}" for key in sorted(required - payload.keys())]
    samples = payload.get("samples")
    if not isinstance(samples, list):
        errors.append("samples는 배열이어야 합니다.")
        samples = []
    change_ids = [sample.get("change_id") for sample in samples if isinstance(sample, dict)]
    if len(samples) != 12:
        errors.append(f"표본은 12건이어야 합니다. 현재 {len(samples)}건입니다.")
    if change_ids != DAY2_SAMPLE_IDS:
        errors.append("change_id 목록 또는 순서가 Day 2 지정 표본과 다릅니다.")
    if payload.get("source_test_run_id") != TEST_RUN_ID:
        errors.append(f"source_test_run_id는 {TEST_RUN_ID}이어야 합니다.")
    mcp = payload.get("mcp")
    if not isinstance(mcp, dict):
        errors.append("mcp는 객체여야 합니다.")
    else:
        missing = {"server", "status", "tools_used", "calls"} - mcp.keys()
        if missing:
            errors.append(f"mcp 필수 필드 누락: {', '.join(sorted(missing))}")
        if mcp.get("status") != "connected":
            errors.append("MCP 실행이 정상 연결 상태로 완료되지 않았습니다.")
    summary = payload.get("summary")
    summary_required = {"population_count", "valid_count", "sample_count", "normal_sample_count", "review_sample_count", "draft_count", "additional_follow_up_count"}
    if not isinstance(summary, dict):
        errors.append("summary는 객체여야 합니다.")
    elif missing := summary_required - summary.keys():
        errors.append(f"summary 필수 필드 누락: {', '.join(sorted(missing))}")
    sample_required = {"sample_id", "change_id", "case_id", "vendor_id", "vendor_name", "selection_reason", "day1_status", "rule_results", "source_ids", "evidence", "agent_draft", "requires_human_review"}
    source_required = {"approval_ids", "evidence_ids", "payment_ids"}
    draft_required = {"procedure", "facts", "draft_assessment", "additional_follow_up", "citations"}
    for index, sample in enumerate(samples, start=1):
        if not isinstance(sample, dict):
            errors.append(f"samples[{index - 1}]는 객체여야 합니다.")
            continue
        missing = sample_required - sample.keys()
        if missing:
            errors.append(f"{sample.get('change_id', index)} 필수 필드 누락: {', '.join(sorted(missing))}")
        source_ids = sample.get("source_ids")
        if not isinstance(source_ids, dict) or source_required - source_ids.keys():
            errors.append(f"{sample.get('change_id', index)} source_ids 형식이 올바르지 않습니다.")
        agent_draft = sample.get("agent_draft")
        if not isinstance(agent_draft, dict) or draft_required - agent_draft.keys():
            errors.append(f"{sample.get('change_id', index)} agent_draft 형식이 올바르지 않습니다.")
        if sample.get("requires_human_review") is not True:
            errors.append(f"{sample.get('change_id', index)}는 담당자 검토 필요 상태여야 합니다.")
    return errors


def load_working_paper() -> dict:
    if not WORKING_PAPER_PATH.exists():
        return {"status": "not_generated", "message": "Agent 검토자료가 아직 생성되지 않았습니다.", "working_paper": None, "validation": {"valid": False, "errors": []}}
    try:
        payload = json.loads(WORKING_PAPER_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        return {"status": "invalid", "message": "working-paper.json을 읽을 수 없습니다.", "working_paper": None, "validation": {"valid": False, "errors": [str(error)]}}
    errors = validate_working_paper(payload)
    if errors:
        return {"status": "invalid", "message": errors[0], "working_paper": payload, "validation": {"valid": False, "errors": errors}}
    return {
        "status": "ready",
        "message": "Agent 검토자료 12건을 불러왔습니다.",
        "working_paper": payload,
        "validation": {"valid": True, "errors": [], "sample_count": 12, "change_ids_match": True, "source_test_run_id_match": True},
    }


def require_working_paper() -> dict:
    result = load_working_paper()
    if result["status"] != "ready":
        raise HTTPException(status_code=409, detail={"reason": result["status"], "message": result["message"]})
    return result["working_paper"]


def require_reviewer(user_id: str) -> None:
    user = next((row for row in read_inputs()["user_roles.csv"] if row["user_id"] == user_id), None)
    permissions = set(user["permissions"].split(";")) if user else set()
    if not user or user["user_status"] != "활성" or "CONTROL_REVIEW" not in permissions:
        raise HTTPException(
            status_code=403,
            detail=f"검토자 {user_id}에게 CONTROL_REVIEW 권한이 없습니다. U701 · 내부통제 검토자를 선택해 주세요.",
        )


def open_review_db() -> sqlite3.Connection:
    DAY3_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DAY3_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.executescript("""
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
        );
        CREATE TABLE IF NOT EXISTS agent_runs (
            run_id TEXT PRIMARY KEY,
            change_id TEXT NOT NULL,
            requester_user_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('success', 'permission_denied', 'config_error', 'tool_error', 'model_error')),
            permission_status TEXT NOT NULL,
            configuration_status TEXT NOT NULL,
            tool_name TEXT,
            tool_arguments_json TEXT,
            tool_status TEXT NOT NULL,
            model_status TEXT NOT NULL,
            answer TEXT,
            error_code TEXT,
            error_message TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL
        );
    """)
    return connection


def agent_run_payload(row: dict) -> dict:
    payload = dict(row)
    payload["tool_arguments"] = json.loads(payload.pop("tool_arguments_json")) if payload["tool_arguments_json"] else None
    return payload


def save_agent_run(
    *, change_id: str, requester_user_id: str, status: str, permission_status: str,
    configuration_status: str, tool_status: str, model_status: str, started_at: str,
    answer: str | None = None, error_message: str | None = None,
) -> dict:
    record = {
        "run_id": str(uuid.uuid4()),
        "change_id": change_id,
        "requester_user_id": requester_user_id,
        "status": status,
        "permission_status": permission_status,
        "configuration_status": configuration_status,
        "tool_name": TOOL_NAME if tool_status != "not_called" else None,
        "tool_arguments_json": json.dumps(
            {"change_id": change_id, "requester_user_id": requester_user_id}, ensure_ascii=False
        ) if tool_status != "not_called" else None,
        "tool_status": tool_status,
        "model_status": model_status,
        "answer": answer,
        "error_code": None if status == "success" else status,
        "error_message": error_message,
        "started_at": started_at,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    }
    try:
        with closing(open_review_db()) as connection, connection:
            connection.execute(
                f"INSERT INTO agent_runs ({', '.join(AGENT_RUN_FIELDS)}) VALUES ({', '.join('?' for _ in AGENT_RUN_FIELDS)})",
                tuple(record[field] for field in AGENT_RUN_FIELDS),
            )
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(status_code=500, detail="Agent 실행 이력을 저장하지 못했습니다.") from error
    return agent_run_payload(record)


def review_events() -> list[dict]:
    try:
        with closing(open_review_db()) as connection, connection:
            return [dict(row) for row in connection.execute("SELECT * FROM review_events ORDER BY rowid")]
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(status_code=500, detail="검토 이력을 읽을 수 없습니다.") from error


def current_reviews(paper: dict, events: list[dict]) -> dict[str, dict]:
    current = {}
    for event in events:
        if event["working_paper_generated_at"] == paper["generated_at"]:
            current[event["change_id"]] = event
    return current


def review_summary(paper: dict, events: list[dict]) -> dict[str, int | bool]:
    current = current_reviews(paper, events)
    counts = Counter(event["conclusion"] for event in current.values())
    reviewed_count = len(current)
    total_count = len(paper["samples"])
    return {
        "total_count": total_count,
        "reviewed_count": reviewed_count,
        "pending_count": total_count - reviewed_count,
        "normal_count": counts["normal"],
        "follow_up_count": counts["follow_up"],
        "control_exception_count": counts["control_exception"],
        "export_ready": reviewed_count == total_count,
    }


def day3_ready_payload(paper: dict, events: list[dict]) -> dict:
    current = current_reviews(paper, events)
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
    summary = review_summary(paper, events)
    return {
        "status": "ready",
        "source_test_run_id": paper["source_test_run_id"],
        "agent_run_id": paper["agent_run_id"],
        "working_paper_generated_at": paper["generated_at"],
        "summary": summary,
        **summary,
        "items": items,
    }


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


@app.post("/api/day2/agent-preview/{change_id}")
async def post_agent_preview(change_id: str, request: AgentPreviewRequest) -> dict:
    paper = require_working_paper()
    if change_id not in {sample["change_id"] for sample in paper["samples"]}:
        raise HTTPException(status_code=404, detail=f"지정 표본에 없는 change_id입니다: {change_id}")
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    try:
        require_reviewer(request.requester_user_id)
    except HTTPException:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="permission_denied", permission_status="denied", configuration_status="not_checked",
            tool_status="not_called", model_status="not_called", started_at=started_at,
            error_message="Agent 실행 권한이 없습니다.",
        )
        raise
    try:
        result = await create_agent_preview(change_id, request.requester_user_id)
        run = save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="success", permission_status="allowed", configuration_status="ready",
            tool_status=result["tool_events"][0]["status"], model_status="success",
            started_at=started_at, answer=result["answer"],
        )
        return {**result, "run_id": run["run_id"]}
    except AgentConfigurationError as error:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="config_error", permission_status="allowed", configuration_status="missing",
            tool_status="not_called", model_status="not_called", started_at=started_at,
            error_message="Agent API 설정을 확인해 주세요.",
        )
        raise HTTPException(status_code=503, detail="Agent 실행에 필요한 API 설정이 없습니다.") from error
    except AgentPermissionError as error:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="permission_denied", permission_status="denied", configuration_status="ready",
            tool_status="permission_denied", model_status="started", started_at=started_at,
            error_message="근거 조회 권한이 없습니다.",
        )
        raise HTTPException(status_code=403, detail="이 근거를 조회할 권한이 없습니다.") from error
    except AgentToolError as error:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="tool_error", permission_status="allowed", configuration_status="ready",
            tool_status=error.tool_status if error.tool_status != "not_called" else "error",
            model_status="started", started_at=started_at,
            error_message="근거 조회에 실패했습니다.",
        )
        raise HTTPException(status_code=502, detail="Agent가 근거를 확인하지 못했습니다.") from error
    except (AgentModelError, AgentExecutionError) as error:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="model_error", permission_status="allowed", configuration_status="ready",
            tool_status=error.tool_status, model_status="error", started_at=started_at,
            error_message="Agent 응답 생성에 실패했습니다.",
        )
        raise HTTPException(status_code=502, detail="Agent가 답변을 만들지 못했습니다.") from error
    except Exception as error:
        save_agent_run(
            change_id=change_id, requester_user_id=request.requester_user_id,
            status="model_error", permission_status="allowed", configuration_status="ready",
            tool_status="not_called", model_status="error", started_at=started_at,
            error_message="Agent 호출에 실패했습니다.",
        )
        raise HTTPException(status_code=502, detail="내부 Agent 호출에 실패했습니다.") from error


@app.get("/api/day2/agent-runs")
def get_agent_runs(change_id: str = Query(...), requester_user_id: str = Query(...)) -> dict:
    paper = require_working_paper()
    if change_id not in {sample["change_id"] for sample in paper["samples"]}:
        raise HTTPException(status_code=404, detail=f"지정 표본에 없는 change_id입니다: {change_id}")
    require_reviewer(requester_user_id)
    try:
        with closing(open_review_db()) as connection, connection:
            rows = connection.execute(
                "SELECT * FROM agent_runs WHERE change_id = ? ORDER BY rowid DESC", (change_id,)
            ).fetchall()
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(status_code=500, detail="Agent 실행 이력을 읽을 수 없습니다.") from error
    return {"items": [agent_run_payload(dict(row)) for row in rows]}


@app.get("/api/day3/reviews")
def get_day3_reviews() -> dict:
    day2 = load_working_paper()
    if day2["status"] != "ready":
        return {
            "status": "blocked",
            "reason": day2["status"],
            "blocked_reason": {"code": day2["status"], "message": day2["message"]},
            "items": [],
        }
    return day3_ready_payload(day2["working_paper"], review_events())


@app.post("/api/day3/reviews/{change_id}")
def save_day3_review(change_id: str, request: ReviewRequest) -> dict:
    paper = require_working_paper()
    if change_id not in {sample["change_id"] for sample in paper["samples"]}:
        raise HTTPException(status_code=404, detail=f"지정 표본에 없는 change_id입니다: {change_id}")
    require_reviewer(request.reviewer_user_id)
    action_id = str(request.review_action_id)
    expected = (
        action_id, paper["source_test_run_id"], paper["agent_run_id"], paper["generated_at"],
        change_id, request.reviewer_user_id, request.conclusion, request.review_comment,
    )
    try:
        with closing(open_review_db()) as connection, connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute("SELECT * FROM review_events WHERE review_action_id = ?", (action_id,)).fetchone()
            if existing:
                event = dict(existing)
                actual = tuple(event[key] for key in (
                    "review_action_id", "source_test_run_id", "agent_run_id", "working_paper_generated_at",
                    "change_id", "reviewer_user_id", "conclusion", "review_comment",
                ))
                if actual != expected:
                    raise HTTPException(status_code=409, detail="같은 review_action_id가 다른 검토 내용에 이미 사용되었습니다.")
            else:
                event = dict(zip(REVIEW_EVENT_FIELDS, (
                    str(uuid.uuid4()), action_id, paper["source_test_run_id"], paper["agent_run_id"], paper["generated_at"],
                    change_id, request.reviewer_user_id, request.conclusion, request.review_comment,
                    datetime.now().astimezone().isoformat(timespec="seconds"),
                )))
                connection.execute("""
                    INSERT INTO review_events (
                        event_id, review_action_id, source_test_run_id, agent_run_id,
                        working_paper_generated_at, change_id, reviewer_user_id, conclusion,
                        review_comment, reviewed_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, tuple(event[field] for field in REVIEW_EVENT_FIELDS))
            events = [dict(row) for row in connection.execute("SELECT * FROM review_events ORDER BY rowid")]
    except HTTPException:
        raise
    except (OSError, sqlite3.Error) as error:
        raise HTTPException(status_code=500, detail="검토 의견을 저장하지 못했습니다.") from error
    return {"status": "saved", "event": event, "summary": review_summary(paper, events)}


@app.get("/api/day3/export.csv")
def export_day3_reviews(reviewer_user_id: str = Query(...)) -> Response:
    require_reviewer(reviewer_user_id)
    paper = require_working_paper()
    events = review_events()
    current = current_reviews(paper, events)
    summary = review_summary(paper, events)
    if not summary["export_ready"]:
        raise HTTPException(status_code=409, detail=f"현재 Agent 초안의 담당자 검토가 {summary['pending_count']}건 남았습니다.")
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
