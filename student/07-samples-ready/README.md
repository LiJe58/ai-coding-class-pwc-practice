# 07 · Samples Ready

완료 상태: `select_day2_samples`가 정상 4건과 검토 필요 8건을 정해진 순서로 반복해서 반환합니다.

다음 교재: `connect-evidence`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

표본 순서는 `001–004, 022–029`이며 `030`은 제외됩니다. CSV와 SQLite를 MCP에서 변경하지 마세요. 문제 발생 시 `python scripts/checkpoint.py reset student/07-samples-ready`로 복구합니다.
