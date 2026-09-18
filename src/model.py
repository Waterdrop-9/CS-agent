from collections.abc import Callable


# 模型函数只读取 messages，返回新响应，不修改历史或已返回的对象。
ModelFunction = Callable[[list[dict]], dict]


def call_model(model: ModelFunction, messages: list[dict]) -> dict:
    """在模型边界检查响应结构；工具参数是否合法由工具层负责。"""
    response = model(messages)
    if not isinstance(response, dict):
        raise ValueError("模型响应必须是字典")

    content = response.get("content")
    tool_calls = response.get("tool_calls")
    if not isinstance(content, str) or not isinstance(tool_calls, list):
        raise ValueError("模型响应需要字符串 content 和列表 tool_calls")

    for call in tool_calls:
        if not isinstance(call, dict) or not all(
            isinstance(call.get(key), str) and call[key].strip()
            for key in ("id", "name")
        ):
            raise ValueError("工具调用需要非空字符串 id 和 name")

    return {"content": content, "tool_calls": tool_calls}
