import csv
import io
import json
import os
import sqlite3
import uuid
from collections import Counter, defaultdict
from contextlib import closing
from datetime import datetime
from pathlib import Path
from typing import Literal

import httpx
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


class AgentPreviewRequest(BaseModel):
    requester_user_id: str = Field(pattern=r"^U\d{3}$")


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
        "message": errors[0] if errors else "Agent 통제조서 12건을 불러왔습니다.",
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


def require_agent_requester(user_id: str) -> None:
    user = next((row for row in read_inputs()["user_roles.csv"] if row["user_id"] == user_id), None)
    permissions = set(user["permissions"].split(";")) if user else set()
    if not user or user["user_status"] != "활성" or permissions.isdisjoint({"EVIDENCE_VERIFY", "CONTROL_REVIEW"}):
        raise HTTPException(status_code=403, detail="활성 EVIDENCE_VERIFY 또는 CONTROL_REVIEW 권한이 필요합니다.")


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
    # ponytail: 과정 규모의 append-only 기록이다. 보존정책이 생기기 전에는 자동 삭제·갱신하지 않는다.
    connection.execute("""
        CREATE TABLE IF NOT EXISTS agent_runs (
            agent_run_id TEXT PRIMARY KEY,
            change_id TEXT NOT NULL,
            requester_user_id TEXT NOT NULL,
            status TEXT NOT NULL CHECK (status IN ('success', 'permission_denied', 'config_error', 'tool_error', 'model_error')),
            model_name TEXT,
            tool_name TEXT,
            tool_input_json TEXT,
            tool_status TEXT,
            response_text TEXT,
            error_code TEXT,
            started_at TEXT NOT NULL,
            completed_at TEXT NOT NULL
        )
    """)
    return connection


def save_agent_run(run: dict) -> dict:
    with closing(open_review_db()) as connection, connection:
        connection.execute(
            """INSERT INTO agent_runs (
                agent_run_id, change_id, requester_user_id, status, model_name, tool_name,
                tool_input_json, tool_status, response_text, error_code, started_at, completed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            tuple(run[key] for key in (
                "agent_run_id", "change_id", "requester_user_id", "status", "model_name", "tool_name",
                "tool_input_json", "tool_status", "response_text", "error_code", "started_at", "completed_at",
            )),
        )
    return run


def list_agent_runs(change_id: str) -> list[dict]:
    with closing(open_review_db()) as connection, connection:
        return [dict(row) for row in connection.execute(
            "SELECT * FROM agent_runs WHERE change_id = ? ORDER BY started_at DESC, rowid DESC",
            (change_id,),
        )]


def call_evidence_tool(change_id: str, requester_user_id: str) -> dict:
    from mcp_server import get_case_evidence

    return get_case_evidence(change_id, requester_user_id)


def call_model(*, api_key: str, model: str, base_url: str, input_items: list, tool_choice: object) -> dict:
    tool = {
        "type": "function",
        "name": "get_case_evidence",
        "description": "권한을 확인한 뒤 선택 사례의 승인·증빙·지급 근거를 읽기 전용으로 조회합니다.",
        "strict": True,
        "parameters": {
            "type": "object",
            "properties": {
                "change_id": {"type": "string"},
                "requester_user_id": {"type": "string"},
            },
            "required": ["change_id", "requester_user_id"],
            "additionalProperties": False,
        },
    }
    response = httpx.post(
        f"{base_url.rstrip('/')}/responses",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "model": model,
            "instructions": "조회 근거만 요약하고 최종 사람 결론을 변경하거나 추정하지 마세요.",
            "input": input_items,
            "tools": [tool],
            "tool_choice": tool_choice,
            "parallel_tool_calls": False,
            "store": False,
        },
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def model_text(payload: dict) -> str:
    if payload.get("output_text"):
        return str(payload["output_text"]).strip()
    texts = []
    for item in payload.get("output", []):
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if content.get("type") == "output_text" and content.get("text"):
                texts.append(content["text"])
    return "\n".join(texts).strip()


def agent_error(run: dict, *, status: str, code: str, message: str, http_status: int, tool_status: str = "not_called") -> None:
    run.update({
        "status": status,
        "tool_status": tool_status,
        "response_text": message,
        "error_code": code,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    save_agent_run(run)
    raise HTTPException(status_code=http_status, detail={"status": status, "error_code": code, "message": message})


def review_events() -> list[dict]:
    with closing(open_review_db()) as connection, connection:
        return [dict(row) for row in connection.execute("SELECT * FROM review_events ORDER BY rowid")]


def day3_payload(paper: dict, events: list[dict]) -> dict:
    current = {}
    for event in events:
        current[event["change_id"]] = event
    items = []
    for sample in paper["samples"]:
        history = [event for event in reversed(events) if event["change_id"] == sample["change_id"]]
        items.append({
            **{key: sample[key] for key in ("sample_id", "change_id", "case_id", "vendor_id", "vendor_name", "day1_status", "selection_reason")},
            "current_review": current.get(sample["change_id"]),
            "history": history,
        })
    counts = Counter(event["conclusion"] for event in current.values())
    reviewed = len(current)
    summary = {
        "total_count": len(paper["samples"]),
        "reviewed_count": reviewed,
        "pending_count": len(paper["samples"]) - reviewed,
        "normal_count": counts["normal"],
        "follow_up_count": counts["follow_up"],
        "control_exception_count": counts["control_exception"],
        "export_ready": reviewed == len(paper["samples"]),
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


@app.post("/api/day2/agent-preview/{change_id}")
def run_agent_preview(change_id: str, request: AgentPreviewRequest) -> dict:
    paper = require_working_paper()
    if change_id not in {sample["change_id"] for sample in paper["samples"]}:
        raise HTTPException(status_code=404, detail=f"고정 표본에 없는 change_id입니다: {change_id}")
    started_at = datetime.now().astimezone().isoformat(timespec="seconds")
    tool_input = {"change_id": change_id, "requester_user_id": request.requester_user_id}
    run = {
        "agent_run_id": str(uuid.uuid4()),
        "change_id": change_id,
        "requester_user_id": request.requester_user_id,
        "status": "model_error",
        "model_name": None,
        "tool_name": "get_case_evidence",
        "tool_input_json": json.dumps(tool_input, ensure_ascii=False, separators=(",", ":")),
        "tool_status": "not_called",
        "response_text": None,
        "error_code": None,
        "started_at": started_at,
        "completed_at": started_at,
    }
    try:
        require_agent_requester(request.requester_user_id)
    except HTTPException:
        agent_error(
            run,
            status="permission_denied",
            code="permission_denied",
            message="현재 사용자는 Agent 근거 조회 권한이 없습니다.",
            http_status=403,
        )

    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    model = os.environ.get("OPENAI_MODEL", "").strip()
    if not api_key or not model:
        agent_error(
            run,
            status="config_error",
            code="agent_config_missing",
            message="Agent API 설정이 없어 이 기능만 사용할 수 없습니다.",
            http_status=503,
        )
    run["model_name"] = model
    base_url = os.environ.get("OPENAI_BASE_URL", "").strip() or "https://api.openai.com/v1"
    input_items: list = [{
        "role": "user",
        "content": f"{change_id}의 근거를 get_case_evidence로 한 번 조회하고 사람 검토용 설명을 작성하세요.",
    }]
    try:
        first = call_model(
            api_key=api_key,
            model=model,
            base_url=base_url,
            input_items=input_items,
            tool_choice={"type": "function", "name": "get_case_evidence"},
        )
    except Exception:
        agent_error(
            run,
            status="model_error",
            code="model_request_failed",
            message="모델 요청에 실패했습니다. 잠시 후 다시 시도하세요.",
            http_status=502,
        )
    calls = [item for item in first.get("output", []) if item.get("type") == "function_call"]
    if len(calls) != 1 or calls[0].get("name") != "get_case_evidence":
        agent_error(
            run,
            status="model_error",
            code="model_tool_call_invalid",
            message="모델이 허용된 Tool 호출 형식을 지키지 않았습니다.",
            http_status=502,
        )
    try:
        evidence = call_evidence_tool(change_id, request.requester_user_id)
    except Exception:
        agent_error(
            run,
            status="tool_error",
            code="evidence_tool_failed",
            message="근거 조회 Tool 실행에 실패했습니다.",
            http_status=502,
            tool_status="error",
        )
    if evidence.get("status") != "success":
        agent_error(
            run,
            status="tool_error",
            code="evidence_tool_rejected",
            message="근거 조회 Tool이 요청을 완료하지 못했습니다.",
            http_status=502,
            tool_status=str(evidence.get("status", "error")),
        )
    run["tool_status"] = "success"
    input_items.extend(first["output"])
    input_items.append({
        "type": "function_call_output",
        "call_id": calls[0]["call_id"],
        "output": json.dumps(evidence, ensure_ascii=False),
    })
    try:
        final = call_model(
            api_key=api_key,
            model=model,
            base_url=base_url,
            input_items=input_items,
            tool_choice="none",
        )
    except Exception:
        agent_error(
            run,
            status="model_error",
            code="model_response_failed",
            message="모델 최종 설명 생성에 실패했습니다.",
            http_status=502,
            tool_status="success",
        )
    response_text = model_text(final)
    if not response_text:
        agent_error(
            run,
            status="model_error",
            code="model_response_empty",
            message="모델이 표시할 최종 설명을 반환하지 않았습니다.",
            http_status=502,
            tool_status="success",
        )
    run.update({
        "status": "success",
        "response_text": response_text,
        "completed_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    })
    save_agent_run(run)
    return {"status": "success", "run": run}


@app.get("/api/day2/agent-runs")
def get_agent_runs(change_id: str = Query(...), requester_user_id: str = Query(...)) -> dict:
    require_agent_requester(requester_user_id)
    return {"status": "ready", "runs": list_agent_runs(change_id)}


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
                raise HTTPException(status_code=409, detail="같은 action ID가 다른 요청에 이미 사용되었습니다.")
        else:
            connection.execute("INSERT INTO review_events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", tuple(event.values()))
    return {"status": "saved", "event": event}


@app.get("/api/day3/export.csv")
def export_day3_reviews(reviewer_user_id: str = Query(...)) -> Response:
    require_reviewer(reviewer_user_id)
    paper = require_working_paper()
    payload = day3_payload(paper, review_events())
    if not payload["export_ready"]:
        raise HTTPException(status_code=409, detail=f"사람 검토 {payload['pending_count']}건이 남았습니다.")
    current = {item["change_id"]: item["current_review"] for item in payload["items"]}
    fields = [
        "source_test_run_id", "agent_run_id", "working_paper_generated_at", "sample_id", "change_id", "case_id", "vendor_id", "vendor_name",
        "selection_reason", "day1_status", "human_conclusion", "review_comment", "reviewer_user_id", "reviewed_at", "approval_ids", "evidence_ids", "payment_ids",
    ]
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, lineterminator="\r\n")
    writer.writeheader()
    for sample in paper["samples"]:
        event = current[sample["change_id"]]
        writer.writerow({
            "source_test_run_id": paper["source_test_run_id"], "agent_run_id": paper["agent_run_id"], "working_paper_generated_at": paper["generated_at"],
            **{key: sample[key] for key in ("sample_id", "change_id", "case_id", "vendor_id", "vendor_name", "selection_reason", "day1_status")},
            "human_conclusion": event["conclusion"], "review_comment": event["review_comment"], "reviewer_user_id": event["reviewer_user_id"], "reviewed_at": event["reviewed_at"],
            **{key: ";".join(sample["source_ids"][key]) for key in ("approval_ids", "evidence_ids", "payment_ids")},
        })
    return Response(content="\ufeff" + output.getvalue(), media_type="text/csv; charset=utf-8", headers={"Content-Disposition": 'attachment; filename="day3-human-reviews.csv"'})
