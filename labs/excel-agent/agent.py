from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from openai import AsyncOpenAI


TOOL_NAME = "get_pbc_mismatches"
MAX_AGENT_STEPS = 3
TOOL = {
    "type": "function",
    "name": TOOL_NAME,
    "description": "PBC 검증 결과에서 차이가 큰 불일치 항목을 조회합니다.",
    "parameters": {
        "type": "object",
        "properties": {"top_n": {"type": "integer", "minimum": 1, "maximum": 20}},
        "required": ["top_n"],
        "additionalProperties": False,
    },
    "strict": True,
}


async def call_mcp_tool(top_n: int) -> dict:
    server = StdioServerParameters(command=sys.executable, args=[str(Path(__file__).with_name("mcp_server.py"))])
    async with stdio_client(server) as streams:
        async with ClientSession(*streams) as session:
            await session.initialize()
            result = await session.call_tool(TOOL_NAME, {"top_n": top_n})
    structured = getattr(result, "structuredContent", None)
    if structured:
        return structured.get("result", structured)
    for item in result.content:
        if getattr(item, "type", None) == "text":
            return json.loads(item.text)
    raise RuntimeError("MCP Tool 결과를 읽을 수 없습니다.")


async def run_agent(user_request: str, top_n: int = 4) -> dict:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    if not api_key or not model:
        raise RuntimeError("OPENAI_API_KEY와 OPENAI_MODEL을 먼저 설정하세요.")

    options = {"api_key": api_key, "max_retries": 0, "timeout": 30.0}
    if base_url := os.getenv("OPENAI_BASE_URL"):
        options["base_url"] = base_url.rstrip("/")
    client = AsyncOpenAI(**options)
    input_items = [{"role": "user", "content": user_request}]
    tool_events = []

    for step in range(MAX_AGENT_STEPS):
        response = await client.responses.create(
            model=model,
            instructions="PBC 수치는 Tool 결과만 사용해 한국어로 설명하고 사람 검토가 필요하다고 알리세요.",
            input=input_items,
            tools=[TOOL],
            tool_choice={"type": "function", "name": TOOL_NAME} if step == 0 else "none",
            parallel_tool_calls=False,
        )
        input_items += response.output
        calls = [item for item in response.output if item.type == "function_call"]
        if not calls:
            if not tool_events or not response.output_text:
                raise RuntimeError("Agent 답변을 만들 수 없습니다.")
            return {
                "answer": response.output_text,
                "tool_events": tool_events,
                "requires_human_review": True,
            }
        if len(calls) != 1 or tool_events or calls[0].name != TOOL_NAME:
            raise RuntimeError("허용되지 않은 Tool 호출입니다.")
        arguments = json.loads(calls[0].arguments or "{}")
        if arguments != {"top_n": top_n}:
            raise RuntimeError("Tool 호출 인자가 요청과 다릅니다.")
        result = await call_mcp_tool(top_n)
        tool_events.append({"tool": TOOL_NAME, "arguments": arguments, "status": "success"})
        input_items.append({
            "type": "function_call_output",
            "call_id": calls[0].call_id,
            "output": json.dumps(result, ensure_ascii=False),
        })

    raise RuntimeError("Agent 실행 단계를 초과했습니다.")


def main() -> int:
    parser = argparse.ArgumentParser(description="PBC 불일치 확인 Agent")
    parser.add_argument("--top-n", type=int, default=4)
    parser.add_argument("question", nargs="?", default="PBC 불일치 항목을 근거와 함께 설명해 주세요.")
    args = parser.parse_args()
    try:
        result = asyncio.run(run_agent(args.question, args.top_n))
    except (OSError, RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    except Exception:
        print("외부 Agent 호출에 실패했습니다. API 설정과 연결 상태를 확인하세요.", file=sys.stderr)
        return 1
    print(result["answer"])
    print(json.dumps({"tool_events": result["tool_events"], "requires_human_review": True}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
