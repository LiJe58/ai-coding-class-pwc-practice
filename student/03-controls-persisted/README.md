# 03 · Controls Persisted

완료 상태: R-01–R-04 판정과 지정 실행 ID의 SQLite 저장. 전체/유효/정상/검토/오류는 `30/29/21/8/1`입니다.

다음 교재: `connect-review-screens` → `verify-day1`.

```text
npm run setup
npm run check
npm run start:backend
npm run dev:frontend
```

정상은 `001–021`, 검토는 `022–029`, `023`은 R-02 실패·R-03/R-04 평가 불가입니다. 프런트엔드는 백엔드 준비 상태만 표시하며 D1-06부터 구현합니다. `input/day-1`을 보존하고 SQLite는 실행 중에만 사용합니다. 문제 시 `python scripts/checkpoint.py reset student/03-controls-persisted`로 복구합니다.
