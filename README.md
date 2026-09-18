# TraceForge

从零实现的 Coding Agent。当前支持模拟模型驱动的工具循环、文件列表和文件读取。

使用 Python 3.11+，仅依赖标准库。在项目根目录运行：

```bash
python3 demo.py
python3 -m unittest discover -s tests -v
```

## 模块职责

- `src/model.py`：约定模型只读历史，检查响应结构，不复制完整历史。
- `src/agent.py`：维护消息、调用 ID 唯一性、工具调度和模型调用预算。
- `src/tools.py`：检查工具名称、参数及路径范围，将预期执行错误返回给模型。

## 固定接口

模型返回 `content` 和 `tool_calls`；每个调用包含 `id`、`name`、`arguments`。
工具返回 `tool_call_id`、`ok`、`content`。Agent 写入历史时添加 `role`。
`Agent.run()` 返回 `stop_reason`、`answer`、`model_calls`。

`stop_reason` 为 `final_answer` 或 `max_steps`，只说明运行为何结束，不代表任务正确完成。
文件访问错误作为工具观察交给模型；模型协议错误和程序缺陷不静默吞掉。
当前路径限制不是完整沙箱，尚未实现持久 Memory、真实模型接入或训练。
