# TraceForge

参考 BearCode 实际实现、逐模块手敲的 Coding Agent。当前支持真实模型驱动的工具循环、文件列表、文件读取、文件写入和工作区命令执行。

使用 Python 3.11+，项目环境由 uv 管理。当前模拟演示仅依赖标准库；`requirements.txt` 与 BearCode 的依赖声明保持一致，为后续真实模型和终端交互迁移准备。在项目根目录运行：

```bash
uv sync
uv run python demo.py
uv run python -m unittest discover -s tests -v
```

真实模型调用前，复制 `.env.example` 为 `.env` 并填写 `API`、`APIKEY`、`MODEL`。然后准备一个测试工作区：

```bash
mkdir -p playground
cp .env.example .env
uv run python main.py --workspace ./playground "列出工作区文件，并说明当前目录内容。"
```

## 模块职责

- `src/model.py`：约定模型只读历史，检查响应结构，不复制完整历史。
- `src/agent.py`：维护消息、调用 ID 唯一性、工具调度和模型调用预算。
- `src/tools.py`：检查工具名称、参数及路径范围，将预期执行错误返回给模型；命令在 workspace 中执行并有 30 秒超时。

## 固定接口

模型返回 `content` 和 `tool_calls`；每个调用包含 `id`、`name`、`arguments`。
工具返回 `tool_call_id`、`ok`、`content`。Agent 写入历史时添加 `role`。
`Agent.run()` 返回 `stop_reason`、`answer`、`model_calls`。

`stop_reason` 为 `final_answer` 或 `max_steps`，只说明运行为何结束，不代表任务正确完成。
文件访问错误作为工具观察交给模型；模型协议错误和程序缺陷不静默吞掉。
当前路径限制不是完整沙箱，尚未实现持久 Memory、真实模型接入或训练。

## 以 BearCode 为参照的迁移约定

每一模块按“原文件/函数 → 执行流程 → TraceForge 对应代码 → 关键设计原因 → 运行验证”讲解，给出完整代码供手敲。优先沿用原项目使用的库与协议，不另换 Agent 框架；已确认的缺陷不照搬。

| 能力 | BearCode 参照 | 迁移方式与原因 |
|---|---|---|
| 配置入口 | `agents/main.py` | 沿用 argparse、python-dotenv 和 MODEL/API/APIKEY 等配置解析思路；凭据与代码分离 |
| 模型客户端 | `agents/agent.py:Agent.__init__` | 沿用 openai.AsyncOpenAI / anthropic.AsyncAnthropic；先迁移一种后端，再补另一种 |
| Agent Loop | `_chat_openai` / `_chat_anthropic` | 迁移 asyncio、工具调用、结果回写；保证 SDK 消息格式与调用 ID 配对 |
| 工具 Schema | `agents/tools.py:tool_definitions`、`_to_openai_tools` | 用结构化声明告诉模型参数规范，声明与真实执行分离 |
| 流式处理 | `_call_openai_stream` | 沿用 SDK 流；拼接完整工具参数后再执行，避免半截 JSON 触发动作 |
| Memory | `agents/memory.py` | 对照文件存储、候选清单、选择与注入；解释预算、来源及跨任务隔离 |
| 终端 UI | `agents/ui.py` | 沿用 rich；展示层与执行逻辑分离 |
| Skills/演化 | `agents/skills.py`、`agents/online_skill_evolution.py` | 后续迁移，额外补充评测晋级与回滚证据 |

当前同步 mock 与内部字典协议是第一课的学习实现，并不是 BearCode SDK 调用的复刻。下一阶段对照原源码迁移异步真实模型调用；内部工具结果转换成供应商消息格式，不能把当前字典直接发给 API。

依赖一致指相同库与版本约束。BearCode 使用版本下界而非锁文件，因此不代表两台机器安装出的精确版本一致。后续真实模型接入通过后再记录经验证的环境版本。训练框架在 Linux/3090 阶段单独配置，不替换当前 Agent 栈。
