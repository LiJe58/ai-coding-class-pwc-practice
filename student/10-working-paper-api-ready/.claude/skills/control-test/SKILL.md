---
name: control-test
description: Mock ERP MCP 근거로 Day 2 거래처 계좌 변경 통제 표본 12건을 조사하고 검토 전 Agent 조서 파일을 작성할 때 사용합니다.
---

# Control Test

## 절차

1. `mock-erp` MCP 연결을 확인하고 도구 목록에 `get_control_population`, `select_day2_samples`, `get_case_evidence`가 있는지 확인합니다. 연결 실패 시 중단하고 부분 결과를 정상 완료로 기록하지 않습니다.
2. `get_control_population(status="all")`을 호출해 Day 1 실행 ID와 전체 30건·유효 29건·정상 21건·검토 필요 8건·입력 오류 1건을 확인합니다.
3. `select_day2_samples()`를 호출해 반환 순서가 `CHG-2608-001`–`004`, `CHG-2608-022`–`029`인지 확인합니다. 정상 4건에는 `교육용 지정 정상 표본`, 검토 필요 8건에는 `핵심 규칙 위반 전수`만 사용합니다.
4. 각 표본에 `get_case_evidence(change_id, requester_user_id="U701")`를 호출합니다. 성공·빈 결과·잘못된 요청·권한 거부를 `status` 필드로 구분합니다.
5. 각 사실을 `approval_id`, `evidence_id`, `payment_id` 또는 `rule_id`에 연결합니다. 근거 ID가 없으면 추정하지 말고 `확인 불가` 또는 `추가 확인 필요`로 기록합니다. 승인 없는 사례의 승인자를 만들지 않고, 증빙 등록부의 등록정보를 문서 내용처럼 설명하지 않습니다.
6. 고정 R-01–R-04 결과를 변경하지 않습니다. 증빙 미수취나 지급 위험을 R-02–R-04 위반으로 새로 판정하지 않습니다.
7. Agent 문안은 `agent_draft`에만 기록하고 모든 표본의 `requires_human_review`를 `true`로 둡니다. 최종 승인·적정·확정처럼 최종 검토 결과로 오해될 표현은 사용하지 않습니다. 단계명인 `Day 1`이나 수업 진행 상황은 문안에 쓰지 않습니다. `procedure`, `facts`, `draft_assessment`, `additional_follow_up`은 사례별로 구체적으로 작성하며 거래처명·변경 ID와 실제 승인·증빙·지급 ID, 시각, 상태, 계좌 토큰 중 판단에 사용한 정보를 명시합니다. 동일한 일반 문구를 표본마다 반복하지 않습니다.
8. 결과를 UTF-8 JSON으로 `output/day-2/working-paper.json`에 작성합니다. `schema_version`은 `1.0`, `agent_run_id`는 `DAY2-2026-08-V1`, `source_test_run_id`는 `DAY1-2026-08-V1`로 기록하고 `generated_at`에는 실제 생성 시각을 `YYYY-MM-DD HH:MM:SS` 형식으로 남깁니다. `mcp.server`는 `mock-erp`, `mcp.status`는 `connected`로 기록하며 `mcp.tools_used`와 `mcp.calls`에는 실제 호출만 남깁니다.
9. 작성 후 표본 12건, 정상 4건, 검토 필요 8건, 초안 12건, 고정 change_id 순서와 모든 인용 ID가 해당 MCP 응답에 존재하는지 확인합니다.

## 표본 구조

각 표본에는 `sample_id`, `change_id`, `case_id`, `vendor_id`, `vendor_name`, `selection_reason`, `day1_status`, `rule_results`, `source_ids`, `evidence`, `agent_draft`, `requires_human_review`만 둡니다. `source_ids`에는 `approval_ids`, `evidence_ids`, `payment_ids`를 두고, `agent_draft`에는 `procedure`, `facts`, `draft_assessment`, `additional_follow_up`, `citations`를 둡니다.
