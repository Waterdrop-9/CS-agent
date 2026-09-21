from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import AsyncMock, patch

from demo import mock_model
from src.agent import Agent
from src.tools import execute_tools


class AgentTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        (self.workspace / "hello.py").write_text("hello\n", encoding="utf-8")

    async def test_complete_and_reset_history(self):
        agent = Agent(self.workspace, mock_model)
        for _ in range(2):
            result = await agent.run("read hello.py")
            self.assertEqual(result, {
                "stop_reason": "final_answer",
                "answer": "hello.py 的内容是：\nhello\n",
                "model_calls": 3,
            })
            self.assertEqual([m["role"] for m in agent.messages], [
                "system", "user", "assistant", "tool", "assistant", "tool", "assistant"
            ])

    async def test_budget_exhaustion(self):
        result = await Agent(self.workspace, mock_model, max_steps=1).run("read")
        self.assertEqual(result, {
            "stop_reason": "max_steps", "answer": "", "model_calls": 1,
        })

    async def test_batch_executes_once_and_error_is_observed(self):
        calls = [
            {"id": "a", "name": "read_file", "arguments": {"file_path": "missing"}},
            {"id": "b", "name": "read_file", "arguments": {"file_path": "hello.py"}},
        ]

        async def model(messages):
            observations = [m for m in messages if m["role"] == "tool"]
            if not observations:
                return {"content": "", "tool_calls": calls}
            self.assertEqual([m["tool_call_id"] for m in observations], ["a", "b"])
            self.assertEqual([m["ok"] for m in observations], [False, True])
            return {"content": observations[-1]["content"], "tool_calls": []}

        with patch("src.agent.execute_tools", wraps=execute_tools) as execute:
            result = await Agent(self.workspace, model).run("read")
            self.assertEqual(execute.call_count, 2)
            self.assertEqual(result["answer"], "hello\n")

    async def test_duplicate_ids_rejected_before_execution(self):
        call = {"id": "a", "name": "list_files", "arguments": {}}
        for calls, expected_executions in [([call, call], 0), ([call], 1)]:
            with self.subTest(calls=len(calls)):
                model = AsyncMock(return_value={"content": "", "tool_calls": calls})
                with patch("src.agent.execute_tools", wraps=execute_tools) as execute:
                    with self.assertRaises(ValueError):
                        await Agent(self.workspace, model).run("read")
                    self.assertEqual(execute.call_count, expected_executions)

    async def test_model_boundary_rejects_bad_structure(self):
        responses = [None, {"content": ""}, {
            "content": "", "tool_calls": [{"id": "a"}],
        }]
        for response in responses:
            with self.subTest(response=response):
                with self.assertRaises(ValueError):
                    await Agent(
                        self.workspace,
                        AsyncMock(return_value=response),
                    ).run("read")

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

    def test_write_file_creates_and_overwrites_file(self):
        result = execute_tools(self.workspace, {
            "id": "write_1",
            "name": "write_file",
            "arguments": {
                "file_path": "new.py",
                "content": "print('first')\n",
            },
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_call_id"], "write_1")
        self.assertEqual(
            (self.workspace / "new.py").read_text(encoding="utf-8"),
            "print('first')\n",
        )

        execute_tools(self.workspace, {
            "id": "write_2",
            "name": "write_file",
            "arguments": {
                "file_path": "new.py",
                "content": "print('second')\n",
            },
        })

        self.assertEqual(
            (self.workspace / "new.py").read_text(encoding="utf-8"),
            "print('second')\n",
        )

    def test_write_file_cannot_escape_workspace(self):
        result = execute_tools(self.workspace, {
            "id": "write_3",
            "name": "write_file",
            "arguments": {
                "file_path": "../outside.py",
                "content": "danger\n",
            },
        })

        self.assertFalse(result["ok"])
        self.assertEqual(result["tool_call_id"], "write_3")
        self.assertFalse((self.root / "outside.py").exists())

    async def test_agent_can_write_file_through_model_loop(self):
        async def model(messages):
            tool_results = [message for message in messages if message["role"] == "tool"]
            if not tool_results:
                return {
                    "content": "写入修复后的代码。",
                    "tool_calls": [{
                        "id": "write_4",
                        "name": "write_file",
                        "arguments": {
                            "file_path": "hello.py",
                            "content": "print('fixed')\n",
                        },
                    }],
                }

            self.assertTrue(tool_results[-1]["ok"])
            return {
                "content": "文件已经写入。",
                "tool_calls": [],
            }

        result = await Agent(self.workspace, model).run("修复 hello.py")

        self.assertEqual(result["stop_reason"], "final_answer")
        self.assertEqual(result["model_calls"], 2)
        self.assertEqual(
            (self.workspace / "hello.py").read_text(encoding="utf-8"),
            "print('fixed')\n",
        )

    def test_run_command_returns_success_output(self):
        result = execute_tools(self.workspace, {
            "id": "command_1",
            "name": "run_command",
            "arguments": {
                "command": "python -c \"print('hello from command')\"",
            },
        })

        self.assertTrue(result["ok"])
        self.assertEqual(result["tool_call_id"], "command_1")
        self.assertIn("exit_code=0", result["content"])
        self.assertIn("hello from command", result["content"])

    def test_run_command_returns_failed_process_output(self):
        result = execute_tools(self.workspace, {
            "id": "command_2",
            "name": "run_command",
            "arguments": {
                "command": "python -c \"import sys; print('failure'); sys.exit(2)\"",
            },
        })

        self.assertFalse(result["ok"])
        self.assertIn("exit_code=2", result["content"])
        self.assertIn("failure", result["content"])

    def test_run_command_rejects_empty_command(self):
        result = execute_tools(self.workspace, {
            "id": "command_3",
            "name": "run_command",
            "arguments": {"command": ""},
        })

        self.assertFalse(result["ok"])

    def test_run_command_uses_workspace_as_current_directory(self):
        result = execute_tools(self.workspace, {
            "id": "command_4",
            "name": "run_command",
            "arguments": {
                "command": "python -c \"import os; print(os.getcwd())\"",
            },
        })

        self.assertTrue(result["ok"])
        self.assertIn(str(self.workspace), result["content"])


if __name__ == "__main__":
    unittest.main()
