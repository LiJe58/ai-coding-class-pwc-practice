from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from dotenv import load_dotenv
from openai import AsyncOpenAI


ROOT = Path(__file__).resolve().parents[2]
TOOL_NAME = "get_case_evidence"
MAX_AGENT_STEPS = 3
TOOL = {
    "type": "function",
    "name": TOOL_NAME,
    "description": "권한을 확인한 뒤 한 변경 사례의 승인·증빙·지급 근거를 조회합니다.",
    "parameters": {
        "type": "object",
        "properties": {
            "change_id": {"type": "string"},
            "requester_user_id": {"type": "string"},
        },
        "required": ["change_id", "requester_user_id"],
        "additionalProperties": False,
    },
    "strict": True,
}


class AgentConfigurationError(Exception):
    pass


class AgentPermissionError(Exception):
    pass


class AgentExecutionError(Exception):
    def __init__(self, message: str, *, tool_status: str = "not_called") -> None:
        super().__init__(message)
        self.tool_status = tool_status


class AgentToolError(AgentExecutionError):
    pass


class AgentModelError(AgentExecutionError):
    pass


def load_agent_settings() -> tuple[str | None, str | None, str | None]:
    load_dotenv(ROOT / ".env", override=False)
    return os.getenv("OPENAI_API_KEY"), os.getenv("OPENAI_MODEL"), os.getenv("OPENAI_BASE_URL")


async def fetch_case_evidence(arguments: dict[str, str]) -> dict:
    server = StdioServerParameters(command=sys.executable, args=[str(ROOT / "backend" / "mcp_server.py")])
    async with stdio_client(server) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool(TOOL_NAME, arguments)
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured.get("result", structured)
    for item in result.content:
        if getattr(item, "type", None) == "text":
            return json.loads(item.text)
    raise AgentToolError("MCP Tool 결과를 읽을 수 없습니다.")


async def create_agent_preview(change_id: str, requester_user_id: str) -> dict:
    api_key, model, base_url = load_agent_settings()
    if not api_key or not model:
        raise AgentConfigurationError

    client_options = {"api_key": api_key, "max_retries": 0, "timeout": 30.0}
    if base_url:
        client_options["base_url"] = base_url.rstrip("/")
    client = AsyncOpenAI(**client_options)
    expected_arguments = {"change_id": change_id, "requester_user_id": requester_user_id}
    input_items = [{
        "role": "user",
        "content": f"{change_id} 사례를 {requester_user_id} 권한으로 다시 확인하고, 확인된 근거만 한국어로 설명하세요.",
    }]
    tool_events = []

    for step in range(MAX_AGENT_STEPS):
        try:
            response = await client.responses.create(
                model=model,
                instructions="근거 조회 결과를 추측 없이 설명하고 마지막에 담당자 검토가 필요하다고 알리세요.",
                input=input_items,
                tools=[TOOL],
                tool_choice={"type": "function", "name": TOOL_NAME} if step == 0 else "none",
                parallel_tool_calls=False,
            )
        except Exception as error:
            raise AgentModelError("Agent 모델 호출에 실패했습니다.", tool_status="success" if tool_events else "not_called") from error
        input_items += response.output
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not tool_events or not response.output_text:
                raise AgentModelError("Agent 답변을 만들 수 없습니다.", tool_status="success" if tool_events else "not_called")
            return {
                "status": "completed",
                "change_id": change_id,
                "answer": response.output_text,
                "tool_events": tool_events,
                "requires_human_review": True,
            }
        if len(calls) != 1 or tool_events or calls[0].name != TOOL_NAME:
            raise AgentModelError("허용되지 않은 Tool 호출입니다.", tool_status="success" if tool_events else "not_called")
        try:
            arguments = json.loads(calls[0].arguments or "{}")
        except json.JSONDecodeError as error:
            raise AgentModelError("Tool 호출 인자를 읽을 수 없습니다.") from error
        if arguments != expected_arguments:
            raise AgentModelError("Tool 호출 인자가 요청과 다릅니다.")
        try:
            evidence = await fetch_case_evidence(arguments)
        except AgentExecutionError:
            raise
        except Exception as error:
            raise AgentToolError("근거 조회에 실패했습니다.") from error
        status = evidence.get("status", "error")
        tool_events.append({"tool": TOOL_NAME, "arguments": arguments, "status": status})
        if status == "permission_denied":
            raise AgentPermissionError
        if status != "success":
            raise AgentToolError("근거 조회에 실패했습니다.", tool_status=status)
        input_items.append({
            "type": "function_call_output",
            "call_id": calls[0].call_id,
            "output": json.dumps(evidence, ensure_ascii=False),
        })

    raise AgentModelError("Agent 실행 단계를 초과했습니다.", tool_status="success" if tool_events else "not_called")
