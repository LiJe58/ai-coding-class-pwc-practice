# 04 · MCP Connected

완료 상태: Day 1 결과를 읽는 `mock-erp` MCP 서버와 읽기 전용 Tool 3개가 연결되어 있습니다.

다음 교재: `select-fixed-samples` → `connect-evidence` → `write-control-test-skill`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

모집단 기대값은 `30/29/21/8/1`입니다. CSV와 SQLite를 MCP에서 변경하지 마세요. 문제 발생 시 `python scripts/checkpoint.py reset student/04-mcp-connected`로 복구합니다.
