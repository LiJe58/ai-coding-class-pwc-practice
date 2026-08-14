# 03 · Day 1 Complete

완료 상태: `30/29/21/8/1` 대시보드, 예외 `022~029`, 선택 상세, R-01~R-04, SQLite와 오류·다시 시도 UI가 같은 API에 연결됩니다.

다음 교재: `understand-agent-parts` → `connect-mock-erp`.

```text
npm run setup
npm run check
npm run start:backend
npm run dev:frontend
```

`CHG-2608-023` 상세에는 R-02 실패와 R-03/R-04 평가 불가가 표시됩니다. CSV를 보존하고 SQLite는 runtime으로만 사용합니다. 문제 시 `python scripts/checkpoint.py reset student/03-day1-complete`로 복구합니다.
