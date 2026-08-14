from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.main import DAY2_SAMPLE_IDS, build_result, read_inputs


mcp = FastMCP("mock-erp", log_level="ERROR")
ALLOWED_EVIDENCE_PERMISSIONS = {"EVIDENCE_VERIFY", "CONTROL_REVIEW"}


def response(status: str, message: str, **data: object) -> dict:
    return {"status": status, "message": message, **data}


def population_row(row: dict) -> dict:
    return {
        "change_id": row["change_id"],
        "case_id": row["case_id"],
        "vendor_id": row["vendor_id"],
        "vendor_name": row["vendor_name"],
        "status": row["status"],
        "violated_rules": [item["rule_id"] for item in row["rules"] if item["result"] == "fail"],
        "rule_results": row["rules"],
    }


@mcp.tool()
def get_control_population(status: str = "all") -> dict:
    """Day 1 모집단과 R-01~R-04 판정 요약을 읽기 전용으로 조회합니다."""
    if status not in {"all", "normal", "review", "error"}:
        return response("invalid_request", "status는 all, normal, review, error 중 하나여야 합니다.", rows=[])
    result = build_result()
    rows = [population_row(row) for row in result["population"] if status == "all" or row["status"] == status]
    return response("success" if rows else "empty", f"Day 1 모집단 {len(rows)}건을 조회했습니다." if rows else "조건에 맞는 모집단이 없습니다.", test_run_id=result["test_run_id"], summary=result["summary"], rows=rows)


@mcp.tool()
def select_day2_samples() -> dict:
    """교육용 고정 Day 2 표본 12건을 지정 순서로 조회합니다."""
    result = build_result()
    by_id = {row["change_id"]: row for row in result["population"]}
    rows = []
    for change_id in DAY2_SAMPLE_IDS:
        item = population_row(by_id[change_id])
        item["selection_reason"] = "핵심 규칙 위반 전수" if item["status"] == "review" else "교육용 고정 정상 표본"
        rows.append(item)
    return response("success", "교육용 고정 표본 12건을 선택했습니다.", source_test_run_id=result["test_run_id"], summary={"sample_count": 12, "normal_count": 4, "review_count": 8}, rows=rows)


@mcp.tool()
def get_case_evidence(change_id: str, requester_user_id: str) -> dict:
    """권한을 확인한 뒤 한 변경 사례의 연결 승인·증빙·지급 메타데이터를 조회합니다."""
    data = read_inputs()
    users = {row["user_id"]: row for row in data["user_roles.csv"]}
    requester = users.get(requester_user_id)
    permissions = set(requester["permissions"].split(";")) if requester else set()
    if not requester or requester["user_status"] != "활성" or permissions.isdisjoint(ALLOWED_EVIDENCE_PERMISSIONS):
        return response("permission_denied", "활성 사용자에게 EVIDENCE_VERIFY 또는 CONTROL_REVIEW 권한이 필요합니다.", change_id=change_id, requester_user_id=requester_user_id, evidence=None)

    result = build_result()
    day1_row = next((row for row in result["population"] if row["change_id"] == change_id), None)
    change = next((row for row in data["vendor_changes.csv"] if row["change_id"] == change_id), None)
    if day1_row is None or change is None:
        return response("invalid_request", f"존재하지 않는 change_id입니다: {change_id}", change_id=change_id, evidence=None)

    approvals = [row for row in data["change_approvals.csv"] if row["change_id"] == change_id]
    evidence_rows = [row for row in data["evidence_register.csv"] if row["request_id"] == change["request_id"]]
    payments = [row for row in data["payment_requests.csv"] if row["change_id"] == change_id]
    vendor = next((row for row in data["vendor_master.csv"] if row["vendor_id"] == change["vendor_id"]), None)
    related_user_ids = {requester_user_id, change["requested_by"], change["changed_by"]}
    related_user_ids.update(row["approved_by"] for row in approvals)
    related_user_ids.update(row["verified_by"] for row in evidence_rows if row["verified_by"])
    related_user_ids.update(row["requested_by"] for row in payments)
    user_rows = [{**users[user_id], "permissions": users[user_id]["permissions"].split(";")} for user_id in sorted(related_user_ids) if user_id in users]
    source_ids = {
        "approval_ids": [row["approval_id"] for row in approvals],
        "evidence_ids": [row["evidence_id"] for row in evidence_rows],
        "payment_ids": [row["payment_id"] for row in payments],
    }
    return response(
        "success",
        "승인 기록 없음" if not approvals else f"{change_id}의 연결 근거를 조회했습니다.",
        change_id=change_id,
        requester_user_id=requester_user_id,
        approval_status="승인 기록 없음" if not approvals else "승인 기록 조회",
        source_ids=source_ids,
        evidence={
            "vendor_change": change,
            "vendor_master": vendor,
            "approvals": approvals,
            "evidence_register": evidence_rows,
            "payment_requests": payments,
            "user_roles": user_rows,
            "day1_result": {"status": day1_row["status"], "reason": day1_row["reason"], "rule_results": day1_row["rules"]},
        },
    )


if __name__ == "__main__":
    mcp.run()
