import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from src.agent import Agent


async def mock_model(messages: list[dict]) -> dict:
    """根据工具观察依次执行：列文件、读文件、回答。"""
    observations = [message for message in messages if message["role"] == "tool"]
    if not observations:
        return {
            "content": "先查看工作区。",
            "tool_calls": [{"id": "call_001", "name": "list_files", "arguments": {}}],
        }

    last = observations[-1]
    if not last["ok"]:
        return {"content": f"工具执行失败：{last['content']}", "tool_calls": []}

    if len(observations) == 1:
        if "hello.py" not in last["content"].splitlines():
            return {"content": "工作区中没有 hello.py。", "tool_calls": []}
        return {
            "content": "读取 hello.py。",
            "tool_calls": [{
                "id": "call_002",
                "name": "read_file",
                "arguments": {"file_path": "hello.py"},
            }],
        }
    return {"content": f"hello.py 的内容是：\n{last['content']}", "tool_calls": []}


async def main() -> None:
    with TemporaryDirectory() as directory:
        workspace = Path(directory)
        (workspace / "hello.py").write_text(
            "print('Hello, TraceForge!')\n", encoding="utf-8"
        )
        agent = Agent(workspace, mock_model)
        result = await agent.run("读取 hello.py，告诉我它的内容。")
        print("运行结果：")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("\n交互轨迹：")
        print(json.dumps(agent.messages, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
