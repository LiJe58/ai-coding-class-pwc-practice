# 13 · Review UI Ready

완료 상태: 같은 요청 ID를 다시 보내도 기록이 늘지 않고, 같은 ID로 다른 내용을 보내면 거부합니다. Agent 초안과 최종 검토 결과, 현재 결론과 전체 이력을 분리해 화면에 표시하며 12건 완료 집계와 CSV 내보내기를 제공합니다.

다음 교재: `agent-history-final`.

이 체크포인트에는 Agent 실행·이력 API와 화면이 아직 없습니다. `agent-history-final`에서 직접 구현하며, 완성 결과는 `student/14-agent-history-ready` 또는 `instructor/complete`를 기준으로 확인합니다.

```text
npm run setup
npm run check
npm run start:backend
npm run start:mcp
npm run dev:frontend
```

U701은 저장할 수 있고 U601은 거부됩니다. Agent 검토자료를 보존하고 담당자 검토 SQLite는 실행 중에만 사용하세요. 문제 발생 시 `python scripts/checkpoint.py reset student/13-review-ui-ready`로 복구합니다.
