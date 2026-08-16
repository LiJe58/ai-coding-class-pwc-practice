# 08 · Evidence Ready

완료 상태: `get_case_evidence`가 U701의 승인·증빙·지급·규칙 근거를 source ID와 함께 반환하고 U601은 자료 조회 전에 거부합니다.

다음 교재: `write-control-test-skill`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

`CHG-2608-023`은 승인 ID가 없으며 U701 성공·U601 거부가 구분됩니다. 입력 자료를 변경하지 마세요. 문제 발생 시 `python scripts/checkpoint.py reset student/08-evidence-ready`로 복구합니다.
