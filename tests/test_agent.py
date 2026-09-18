from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from demo import mock_model
from src.agent import Agent
from src.tools import execute_tools


class AgentTests(unittest.TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "hello.py").write_text("hello\n", encoding="utf-8")

    def test_complete_and_reset_history(self):
        agent = Agent(self.workspace, mock_model)
        for _ in range(2):
            result = agent.run("read hello.py")
            self.assertEqual(result, {
                "stop_reason": "final_answer",
                "answer": "hello.py 的内容是：\nhello\n",
                "model_calls": 3,
            })
            self.assertEqual([m["role"] for m in agent.messages], [
                "system", "user", "assistant", "tool", "assistant", "tool", "assistant"
            ])

    def test_budget_exhaustion(self):
        result = Agent(self.workspace, mock_model, max_steps=1).run("read")
        self.assertEqual(result, {
            "stop_reason": "max_steps", "answer": "", "model_calls": 1,
        })

    def test_batch_executes_once_and_error_is_observed(self):
        calls = [
            {"id": "a", "name": "read_file", "arguments": {"file_path": "missing"}},
            {"id": "b", "name": "read_file", "arguments": {"file_path": "hello.py"}},
        ]

        def model(messages):
            observations = [m for m in messages if m["role"] == "tool"]
            if not observations:
                return {"content": "", "tool_calls": calls}
            self.assertEqual([m["tool_call_id"] for m in observations], ["a", "b"])
            self.assertEqual([m["ok"] for m in observations], [False, True])
            return {"content": observations[-1]["content"], "tool_calls": []}

        with patch("src.agent.execute_tools", wraps=execute_tools) as execute:
            result = Agent(self.workspace, model).run("read")
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(result["answer"], "hello\n")

    def test_duplicate_ids_rejected_before_execution(self):
        call = {"id": "a", "name": "list_files", "arguments": {}}
        for calls, expected_executions in [([call, call], 0), ([call], 1)]:
            with self.subTest(calls=len(calls)):
                model = lambda messages: {"content": "", "tool_calls": calls}
                with patch("src.agent.execute_tools", wraps=execute_tools) as execute:
                    with self.assertRaises(ValueError):
                        Agent(self.workspace, model).run("read")
                    self.assertEqual(execute.call_count, expected_executions)

    def test_model_boundary_rejects_bad_structure(self):
        responses = [None, {"content": ""}, {
            "content": "", "tool_calls": [{"id": "a"}],
        }]
        for response in responses:
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    Agent(self.workspace, lambda messages: response).run("read")

    def test_tool_boundary_errors(self):
        (self.root / "outside.txt").write_text("outside", encoding="utf-8")
        (self.workspace / "link.txt").symlink_to(self.root / "outside.txt")
        cases = [
            ("unknown", {}),
            ("read_file", None),
            ("read_file", {}),
            ("read_file", {"file_path": 123}),
            ("read_file", {"file_path": "../outside.txt"}),
            ("read_file", {"file_path": "link.txt"}),
            ("read_file", {"file_path": str(self.workspace / "hello.py")}),
        ]
        for name, arguments in cases:
            with self.subTest(name=name, arguments=arguments):
                result = execute_tools(self.workspace, {
                    "id": "a", "name": name, "arguments": arguments,
                })
                self.assertFalse(result["ok"])
                self.assertEqual(result["tool_call_id"], "a")


if __name__ == "__main__":
    unittest.main()
