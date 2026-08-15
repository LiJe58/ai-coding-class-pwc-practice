# 07 · Review Storage Ready

완료 상태: Day 2 검토자료는 그대로 보존하고, 사람 결론은 기존 기록을 지우지 않는 별도 SQLite 이력으로 저장합니다. U701만 저장할 수 있으며 잘못된 사용자·결론·메모·사례는 거부됩니다.

다음 교재: `build-final-review`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

Agent 검토자료 파일 `output/day-2/working-paper.json`을 보존하고 Day 3 SQLite는 실행 중에만 사용하세요. 문제 발생 시 `python scripts/checkpoint.py reset student/07-review-storage-ready`로 복구합니다.
