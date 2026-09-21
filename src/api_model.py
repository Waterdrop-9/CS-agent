import json
from openai import AsyncOpenAI


def to_api_messages(messages: list[dict]) -> list[dict]:
    """把 TraceForge 的内部历史转换为 API 消息，不修改原历史。"""
    result = []

    for message in messages:
        role = message["role"]

        if role == "tool":
            result.append({
                "role": "tool",
                "tool_call_id": message["tool_call_id"],
                "content": json.dumps(
                    {
                        "ok": message["ok"],
                        "content": message["content"],
                    },
                    ensure_ascii=False,
                ),
            })
            continue

        item = {
            "role": role,
            "content": message["content"],
        }

        if role == "assistant":
            if "reasoning_content" in message:
                item["reasoning_content"] = message["reasoning_content"]

            if message["tool_calls"]:
                item["tool_calls"] = [
                    {
                        "id": call["id"],
                        "type": "function",
                        "function": {
                            "name": call["name"],
                            "arguments": json.dumps(
                                call["arguments"],
                                ensure_ascii=False,
                            ),
                        },
                    }
                    for call in message["tool_calls"]
                ]

        result.append(item)

    return result


class APIModel:
    def __init__(
        self,
        client: AsyncOpenAI,
        model: str,
        tools: list[dict],
    ):
        self.client = client
        self.model = model

        self.tools = [
            {
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["input_schema"],
                },
            }
            for tool in tools
        ]

    async def __call__(self, messages: list[dict]) -> dict:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=to_api_messages(messages),
            tools=self.tools,
            stream=False,
        )

        choice = response.choices[0]

        if choice.finish_reason not in ("stop", "tool_calls"):
            raise RuntimeError(
                f"模型未正常完成输出：{choice.finish_reason}"
            )

        message = choice.message

        result = {
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,
                    "name": call.function.name,
                    "arguments": json.loads(call.function.arguments),
                }
                for call in (message.tool_calls or [])
            ],
        }

        reasoning = getattr(message, "reasoning_content", None)
        if reasoning is not None:
            result["reasoning_content"] = reasoning

        return result