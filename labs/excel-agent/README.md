# Excel PBC Agent 실습

비식별 Excel의 PBC 검증 결과를 Python 함수, MCP Tool, 실제 모델 호출 순서로 확인합니다. 필수 Tool은 `get_pbc_mismatches(top_n)` 하나입니다.

## 준비

1. 가상환경을 활성화하고 `python -m pip install -r requirements.txt`를 실행합니다.
2. 강사가 제공한 `Excel_Copilot_anonymized.xlsx`를 `data` 폴더에 둡니다.
3. 실제 Agent를 실행할 때만 `OPENAI_API_KEY`, `OPENAI_MODEL`을 환경변수로 설정합니다. 내부 호환 API가 필요하면 `OPENAI_BASE_URL`도 설정합니다.

비밀값을 `.env`, 코드, 화면 캡처나 실행 결과에 남기지 마세요.

## 1. Python 함수 직접 호출

```bash
python -c "from excel_tool import get_pbc_mismatches; print(get_pbc_mismatches(4))"
```

결과의 `counts`가 일치 137건, 불일치 4건인지 확인합니다.

## 2. MCP Tool 직접 호출

```bash
python -c "import asyncio; from agent import call_mcp_tool; print(asyncio.run(call_mcp_tool(4)))"
```

같은 함수가 `get_pbc_mismatches`라는 MCP Tool로 실행되는지 확인합니다.

## 3. 실제 Agent 실행

```bash
python agent.py --top-n 4
```

마지막 줄의 `tool_events`에서 Tool 이름, `top_n`, 성공 상태를 확인합니다. Excel 원본 행 전체는 실행 결과에 따로 출력하지 않습니다. 모델 설명은 초안이므로 사람이 근거와 결론을 다시 검토합니다.

## 선택 과제

Claude Code에 거래처별 금액을 요약하는 `top_counterparties` Tool을 추가하도록 요청해 보세요. 먼저 어떤 시트와 금액 열을 사용할지 설명하게 하고, 기존 필수 Tool과 환경변수 규칙을 바꾸지 않도록 합니다.

Day 3을 마친 뒤 강사용 완성 앱에서 표본을 선택하고 `Agent로 다시 확인` 버튼도 실행합니다. 이 결과는 화면에만 표시되며 최종 검토 결과가나 검토 이력에 저장되지 않습니다.
