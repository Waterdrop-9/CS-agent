import argparse
import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import AsyncOpenAI

from src.agent import Agent
from src.api_model import APIModel
from src.tools import TOOL_DEFINITIONS


async def main() -> None:
    parser = argparse.ArgumentParser(description="TraceForge coding agent")
    parser.add_argument("task", help="交给 Agent 的任务")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path.cwd(),
    )
    parser.add_argument("--max-steps", type=int, default=8)
    args = parser.parse_args()

    load_dotenv(Path(__file__).resolve().parent / ".env")

    names = ("MODEL", "API", "APIKEY")
    config = {
        name: os.getenv(name, "").strip()
        for name in names
    }

    missing = [name for name, value in config.items() if not value]
    if missing:
        raise ValueError(f".env 缺少配置：{', '.join(missing)}")

    async with AsyncOpenAI(
        base_url=config["API"],
        api_key=config["APIKEY"],
    ) as client:
        model = APIModel(
            client=client,
            model=config["MODEL"],
            tools=TOOL_DEFINITIONS,
        )

        agent = Agent(
            workspace=args.workspace,
            model=model,
            max_steps=args.max_steps,
        )

        result = await agent.run(args.task)

    print("\n工具调用：")
    for message in agent.messages:
        if message["role"] == "assistant":
            for call in message["tool_calls"]:
                print(f"  {call['name']}({call['arguments']})")
        elif message["role"] == "tool":
            status = "成功" if message["ok"] else "失败"
            print(f"    -> {status}")

    print(f"\n停止原因：{result['stop_reason']}")
    print(f"模型调用次数：{result['model_calls']}")
    print(f"\n{result['answer']}")


if __name__ == "__main__":
    asyncio.run(main())