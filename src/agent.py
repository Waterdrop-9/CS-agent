from pathlib import Path

from src.model import ModelFunction, call_model
from src.tools import execute_tools


class Agent:
    def __init__(self, workspace: Path, model: ModelFunction, max_steps: int = 8):
        self.workspace = workspace.resolve()
        if not self.workspace.is_dir():
            raise ValueError("workspace 必须是已经存在的目录")
        if max_steps < 1:
            raise ValueError("max_steps 必须大于零")
        self.model = model
        self.max_steps = max_steps
        self.messages: list[dict] = []

    def run(self, task: str) -> dict:
        """运行独立任务；停止原因不代表任务通过验证。"""
        self.messages = [
            {
                "role": "system",
                "content": (
                    "You are TraceForge, a coding agent. "
                    "Available tools: list_files and read_file. "
                    "Use tool results as evidence. "
                    "When finished, answer without tool calls."
                ),
            },
            {"role": "user", "content": task},
        ]
        seen_call_ids: set[str] = set()

        # max_steps 限制模型调用次数，不是工具调用次数。
        for step in range(1, self.max_steps + 1):
            response = call_model(self.model, self.messages)
            tool_calls = response["tool_calls"]

            # 格式已由模型边界检查；循环只检查运行内的 ID 唯一性。
            call_ids = [call["id"] for call in tool_calls]
            if len(call_ids) != len(set(call_ids)) or seen_call_ids.intersection(call_ids):
                raise ValueError("工具调用 ID 在本批或历史中重复")

            self.messages.append({"role": "assistant", **response})
            if not tool_calls:
                return {
                    "stop_reason": "final_answer",
                    "answer": response["content"],
                    "model_calls": step,
                }

            seen_call_ids.update(call_ids)
            for call in tool_calls:
                result = execute_tools(self.workspace, call)
                self.messages.append({"role": "tool", **result})

        return {
            "stop_reason": "max_steps",
            "answer": "",
            "model_calls": self.max_steps,
        }
