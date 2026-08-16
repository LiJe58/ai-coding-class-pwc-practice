# 10 · Working Paper API Ready

완료 상태: 고정 Agent 통제 검토자료 12건을 읽기 전용 API로 제공하고 파일·JSON·내용 오류를 정상 응답과 구분합니다. 프런트엔드는 아직 Day 1 화면입니다.

다음 교재: `build-working-paper-screen`.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

`output/day-2/working-paper.json`과 입력 CSV를 보존하세요. 문제 발생 시 `python scripts/checkpoint.py reset student/10-working-paper-api-ready`로 복구합니다.
