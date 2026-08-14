# 08 · Review UI Ready

완료 상태: 같은 요청 식별값을 다시 보내도 기록이 늘지 않고, 같은 식별값으로 다른 내용을 보내면 거부합니다. Agent 초안과 사람 결론, 현재 결론과 전체 이력을 분리해 화면에 표시합니다.

다음 교재: `connect-review-status` → `complete-and-export` → `verify-failures` → `run-final-demo` → `write-application-scope`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

U701은 저장할 수 있고 U601은 거부됩니다. Day 2 조서를 보존하고 Day 3 SQLite는 실행 중에만 사용하세요. 문제 발생 시 `python scripts/checkpoint.py reset student/08-review-ui-ready`로 복구합니다.
