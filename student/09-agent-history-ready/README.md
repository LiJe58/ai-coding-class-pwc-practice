# 09 · Agent History Ready

완료 상태: 기존 사람 검토 UI와 완료·CSV 흐름을 유지하면서 현재 테스트 사용자, 읽기 전용 Agent 권한 카드, `get_case_evidence` 1회 실행, 사례별 append-only 실행 이력 조회가 연결되어 있습니다. 성공·권한 거부·설정 오류·Tool 오류·모델 오류는 사람 결론 및 `working-paper.json`과 분리해 기록합니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

Agent 실행에는 서버 환경변수 `OPENAI_API_KEY`, `OPENAI_MODEL`이 필요하며 호환 API를 사용할 때만 `OPENAI_BASE_URL`을 설정합니다. 설정이 없으면 Agent API만 503으로 중단됩니다. `backend/data/day3_reviews.sqlite3`의 `agent_runs`는 과정 규모의 runtime 기록으로 자동 삭제하지 않지만 체크포인트에는 빈 DB 상태만 포함됩니다. API 키, 전체 모델 메시지, 원본 ERP 행은 저장하지 않습니다.

U701은 실행과 조회가 가능하고 U601은 모델·MCP 호출 전에 거부됩니다. 입력 CSV와 `output/day-2/working-paper.json`은 수정하지 않습니다. 복구는 `python scripts/checkpoint.py reset student/09-agent-history-ready`를 사용합니다.
