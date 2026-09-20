# Agent Demo：从对话到可扩展个人助手

这是一个基于 [Pydantic AI](https://ai.pydantic.dev/) 的渐进式示例项目。每个 `demo_*.py` 只在前一个示例的基础上增加一项能力：先让模型能对话，再让它记住上下文、调用工具、连接 MCP、维护长期记忆，并最终按需加载 Skills。

建议严格按下文顺序运行。这样每次看到的新代码和新现象，都能对应到一个明确的 Agent 能力。

## 1. 准备环境

项目要求 Python 3.14+，使用 `uv` 管理依赖：

```bash
uv sync
```

模型通过 OpenRouter 调用。请在项目根目录创建 `.env`，不要将它提交到版本控制：

```dotenv
OPENROUTER_API_KEY=你的_OpenRouter_API_Key
```

会话示例会向 `sessions/` 写入 JSON 文件；首次运行前创建该目录：

```bash
mkdir -p sessions
```

之后所有命令均在项目根目录执行，并统一使用：

```bash
uv run python <脚本名>
```

> `model.py` 当前固定使用 `deepseek/deepseek-v4-flash`，并配置了 OpenRouter 的提供商限制和重试 HTTP 客户端。如需换模型或提供商，可从这里开始调整。

> `config.yaml` 中可能包含 MCP 服务的访问凭据。把它当作敏感配置处理：不要在截图、提交记录或公开仓库中暴露真实 token；实际使用时建议改为本地私密配置或由环境变量注入。

## 2. 推荐运行路线

| 顺序 | 脚本 | 新增能力 | 可尝试的输入 |
| --- | --- | --- | --- |
| 1 | `demo_chat.py` | 单轮流式对话 | `用一句话解释什么是 Agent` |
| 2 | `demo_chatbot.py` | 进程内多轮上下文 | 先说“我叫小王”，再问“我叫什么？” |
| 3 | `demo_sessions.py` | 会话持久化与恢复 | 退出后用 `--resume` 恢复 |
| 4 | `demo_tools.py` | 模型调用本地函数工具 | `用 bash 查看当前目录有哪些 Python 文件` |
| 5 | `demo_mcp_server.py` + `demo_mcp.py` | 通过 MCP 使用外部工具 | `调用 echo 工具，把“你好”原样返回` |
| 6 | `demo_memory.py` | 本地长期记忆 | `我偏好使用 Python，请记住`，随后询问偏好 |
| 7 | `demo_skills.py` | 按需加载技能及其 MCP 能力 | 创建一个 Skill 后提出与它匹配的问题 |
| 8 | `main.py` | 汇总：Skills、MCP、工具和会话 | 按你的配置进行综合测试 |

除 `demo_chat.py` 外，交互式脚本输入 `quit`（或按 `Ctrl-C` / `Ctrl-D`）退出。

## 3. 逐步运行与理解

### 第一步：单轮流式对话

```bash
uv run python demo_chat.py
```

输入问题后，`Agent(model)` 将提示词发送给模型。`run_stream_events()` 不等待完整答案，而是持续产生事件；`utils.py` 的 `parse_event()` 将它们整理为思考、正文、工具调用、工具结果和最终用量，终端据此即时输出。

这一层的核心链路是：

```text
用户输入 → Agent → 模型 → 流式事件 → parse_event → 终端输出
```

### 第二步：多轮聊天

```bash
uv run python demo_chatbot.py
```

该示例在内存中维护 `messages`。每轮结束时从最终事件取得 `all_messages`，下一轮通过 `message_history=messages` 再传回 Agent。因此模型能引用本次进程中先前的对话；但程序一退出，历史就消失。

### 第三步：会话持久化

```bash
uv run python demo_sessions.py
```

启动时会显示一串 session ID，例如：

```text
[info] using session 123e4567-e89b-12d3-a456-426614174000
```

输入几轮内容后用 `quit` 退出。`LocalSession` 会将模型消息序列化到 `sessions/<session-id>.json`。使用相同 ID 恢复：

```bash
uv run python demo_sessions.py --resume 123e4567-e89b-12d3-a456-426614174000
```

原理上，这和第二步的短期上下文相同；区别仅在于 `session.py` 将上下文写入磁盘，使其跨进程存在。

### 第四步：本地工具调用

```bash
uv run python demo_tools.py
```

`@agent.tool` 将 Python 函数注册为可被模型选择的工具。模型判断任务需要执行命令时，会生成结构化的 `bash(args)` 调用；程序执行后把标准输出作为工具结果回传模型，再由模型组织最终回答。终端的 `[tool]` 日志可看到这条往返。

```text
用户任务 → 模型选择 bash → 本地执行 subprocess → 工具结果 → 模型回答
```

注意：示例中的 `bash` 会按模型给出的参数执行本地命令。仅应在隔离、可信的开发环境中运行；生产环境应改为命令白名单、受限工作目录、权限隔离和审计。

### 第五步：MCP 服务与客户端

先在一个终端启动本地 MCP 服务：

```bash
uv run python demo_mcp_server.py
```

它以 Streamable HTTP 方式提供 `echo(msg)` 工具，默认地址与 `config.yaml` 中启用的 `mcp_server_name` 相对应：`http://127.0.0.1:8000/mcp`。

保持服务运行，在另一个终端启动客户端：

```bash
uv run python demo_mcp.py
```

`demo_mcp.py` 会读取 `config.yaml`，为其中 `enable: true` 的 HTTP 服务创建 `MCPToolset`，并在每轮运行时交给 Agent。MCP 的价值是把“工具的实现”放到独立进程或远程服务中，客户端只通过统一协议发现和调用它，而不需要直接导入服务端代码。

如果不想连接某个服务，将其在 `config.yaml` 中设为 `enable: false`。运行 `demo_mcp.py` 前，至少应启用一个可访问的 MCP 服务。

### 第六步：长期记忆

本步骤仍会加载 `config.yaml` 中启用的 MCP 服务，因此请保持上一步的本地 MCP 服务运行，或关闭全部 MCP 配置后自行调整示例。

```bash
uv run python demo_memory.py
```

它额外注册了两个工具：

- `search_memory(keywords)`：从 `memory.txt` 中按关键字查找已存记忆；
- `save_memory(data)`：追加一条提炼后的长期信息。

系统指令要求模型先判断是否应检索，再判断用户输入是否具有长期价值并选择存储。因此，`messages` 负责完整的近期对话，`memory.txt` 负责跨会话的少量关键事实；两者不是同一种记忆。为方便反复演示，可在开始前手动清空 `memory.txt`。

### 第七步：Skills 与能力按需加载

```bash
uv run python demo_skills.py
```

`demo_skills.py` 会递归搜索 `config.yaml` 中 `skill_dir` 指定目录（默认 `./skills`）内的 `skill.md`，把每个文件转换为 `Capability`。能力初始采用 `defer_loading=True`，让模型先根据名称和描述判断是否需要，而不是每轮都注入全部细节。这是 Skills 适合规模化的原因：提示词不会随着技能数量线性膨胀。

仓库初始没有预置 `skills/`，可创建一个最小示例：

```bash
mkdir -p skills/release-note
```

在 `skills/release-note/skill.md` 中写入：

```markdown
---
id: release-note
description: 将变更整理成简洁、面向用户的发布说明
---

当用户需要发布说明时：
1. 按“新增、改进、修复”分组。
2. 使用简洁的中文，避免暴露内部实现细节。
```

重新运行脚本后，可以输入“把新增深色模式和修复登录超时写成发布说明”。该 Skill 只提供专门的指令；它也可以像代码中的 MCP 配置一样，组合工具集，形成完整的领域能力。

### 第八步：完整入口

```bash
uv run python main.py
```

`main.py` 汇集了前述能力：读取 MCP 与 Skills 为 `Capability`、注册本地 `bash` 工具、流式展示事件，并用 `LocalSession` 保存或恢复对话。恢复方式同样为：

```bash
uv run python main.py --resume <session-id>
```

## 4. 项目结构与整体原理

```text
model.py / http_client.py     模型、OpenRouter 配置与 HTTP 重试
utils.py                      将 Pydantic AI 事件转为终端可显示的数据
session.py                    模型消息的 JSON 会话存储
memory.py                     简单的文本长期记忆库
config.py / config.yaml       MCP 服务和 Skill 目录配置
demo_*.py                     分阶段教学脚本
main.py                       能力整合入口
```

最终的执行模型可以概括为：

```text
用户输入
  ↓
Agent（系统指令 + 近期会话 + 可按需加载的 Skills）
  ↓                         ↘
模型选择直接回答             本地工具 / MCP 工具 / 记忆工具
  ↓                         ↙
流式事件解析与输出 ← 工具结果回传模型
  ↓
会话写入 sessions/，长期事实写入 memory.txt
```

其中，模型负责理解、规划和决定是否调用工具；普通 Python 工具负责本地动作；MCP 负责连接可独立部署的外部能力；Session 和 Memory 分别处理短期完整上下文与长期提炼事实；Skills 则把特定领域的说明和能力组织为可按需加载的模块。

## 5. 常见问题

**提示找不到 API Key**：确认根目录 `.env` 存在，变量名为 `OPENROUTER_API_KEY`，并重新启动命令。

**会话脚本报 `sessions/...` 不存在**：先运行 `mkdir -p sessions`。

**MCP 客户端连接失败**：确认 `demo_mcp_server.py` 正在另一终端运行，并检查 `config.yaml` 中 URL 为 `http://127.0.0.1:8000/mcp`、对应项已启用。

**Skill 没有生效**：检查文件名必须是 `skill.md`（大小写均可），且位于 `skills/<技能名>/` 的任意子目录；描述应清楚说明何时使用该 Skill。

**工具没有被调用**：工具由模型自主决定。请把请求描述得更明确，例如“请使用 bash 列出当前目录下的 `.py` 文件”，并查看 `[tool]` 输出。
