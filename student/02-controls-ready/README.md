# 02 · Controls Ready

완료 상태: 입력 오류와 R-01–R-04 판정을 분리했습니다. 전체/유효/정상/검토/오류는 `30/29/21/8/1`이며 아직 SQLite에는 저장하지 않습니다.

다음 교재: `save-results`.

```text
npm run setup
npm run check
npm run start:backend
npm run dev:frontend
```

정상은 `001–021`, 검토는 `022–029`, `023`은 R-02 실패·R-03/R-04 평가 불가입니다. 프런트엔드는 백엔드 준비 상태만 표시합니다. `input/day-1`을 보존하세요. 문제 시 `python scripts/checkpoint.py reset student/02-controls-ready`로 복구합니다.
