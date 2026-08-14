# 01 · Population Ready

완료 상태: CSV 30건을 읽고 R-01 입력 검증으로 유효 29건과 입력 오류 1건을 분리합니다.

다음 교재: `implement-control-rules` → `save-results`.

```text
npm run setup
npm run check
npm run start:backend
npm run dev:frontend
```

기대값은 전체 30, 유효 29, 입력 오류 1, 오류 ID `CHG-2608-030`입니다. CSV는 보존합니다. 문제 시 저장소 루트에서 `python scripts/checkpoint.py reset student/01-population-ready`로 복구합니다.
