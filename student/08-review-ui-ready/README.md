# 08 · Review UI Ready

완료 상태: 같은 action ID 재시도는 이벤트를 늘리지 않고, 다른 payload 충돌은 거부합니다. Agent 초안과 사람 결론, 현재 결론과 전체 이력을 분리해 화면에 표시합니다.

다음 교재: `connect-status` → `define-completion` → `export-results` → `recover-failure` → `final-demo` → `application-scope`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

U701은 저장할 수 있고 U601은 거부됩니다. Day 2 조서를 보존하고 Day 3 SQLite는 runtime으로만 사용하세요. 문제 발생 시 `python scripts/checkpoint.py reset student/08-review-ui-ready`로 복구합니다.
