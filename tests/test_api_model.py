import asyncio
import unittest

from src.model import call_model
from src.api_model import to_api_messages


class ApiModelTests(unittest.TestCase):
    def test_tool_messages_use_openai_shape(self):
        messages = to_api_messages([
            {
                "role": "assistant",
                "content": "读取文件",
                "tool_calls": [{
                    "id": "call_1",
                    "name": "read_file",
                    "arguments": {"file_path": "hello.py"},
                }],
            },
            {
                "role": "tool",
                "tool_call_id": "call_1",
                "ok": True,
                "content": "hello",
            },
        ])

        self.assertEqual(messages[0]["tool_calls"][0]["function"]["name"], "read_file")
        self.assertEqual(
            messages[0]["tool_calls"][0]["function"]["arguments"],
            '{"file_path": "hello.py"}',
        )
        self.assertEqual(messages[1]["tool_call_id"], "call_1")
        self.assertEqual(messages[1]["content"], '{"ok": true, "content": "hello"}')

    def test_reasoning_content_keeps_exact_field_name(self):
        async def model(_messages):
            return {
                "content": "完成",
                "tool_calls": [],
                "reasoning_content": "内部思考元数据",
            }

        result = asyncio.run(call_model(model, []))
        self.assertEqual(result["reasoning_content"], "内部思考元数据")
        self.assertNotIn("resoning_content", result)


if __name__ == "__main__":
    unittest.main()
