# Instructor Complete

완료 상태: Day 1~3 전체 기능, 상태 연결, 완료 조건, 권한·멱등 저장, CSV export gate, 실패 복구 UI와 적용 범위 템플릿이 포함됩니다. 선택 사례는 현재 테스트 사용자 권한을 먼저 확인한 뒤 `get_case_evidence`를 한 번만 호출하는 Agent로 다시 확인할 수 있고, 결과와 안전한 실패 상태는 사람 검토 이력과 분리된 SQLite 실행 이력으로 누적됩니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

Agent 실행에는 서버 환경변수 `OPENAI_API_KEY`, `OPENAI_MODEL`이 필요하며 호환 API를 사용할 때만 `OPENAI_BASE_URL`을 설정합니다. 설정이 없으면 Agent 실행 API만 503으로 중단되고 기존 화면과 검토 API는 계속 동작합니다. API 키, 전체 모델 메시지, 원본 ERP 행은 실행 이력에 저장하지 않습니다.

초기 집계는 `12/0/12`, 완료 집계 예시는 `12/12/0/4/1/7`입니다. 12건 검토 전 export는 거부됩니다. 입력 CSV와 `output/day-2/working-paper.json`은 보존하고 SQLite·다운로드 CSV는 runtime으로만 사용하세요. `backend/data/day3_reviews.sqlite3`의 `agent_runs`는 실행할 때마다 새 행을 추가하며 자동 삭제하지 않습니다. 복구는 `python scripts/checkpoint.py reset instructor/complete`를 사용합니다.
