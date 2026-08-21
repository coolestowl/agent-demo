import asyncio
import uuid

import logfire
from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.mcp import MCPToolset
from pydantic_settings import BaseSettings, SettingsConfigDict

logfire.configure()
logfire.instrument_pydantic_ai()

from config import Config, MCPConfig
from memory import LocalMemory
from model import model
from session import LocalSession
from utils import parse_event

cfg = Config()
# print(f"{cfg=}")


def load_mcp_servers(servers: dict[str, MCPConfig]) -> list[MCPToolset]:
    toolsets = []
    for k, v in servers.items():
        if not v.enable:
            continue
        _ = k
        if v.type == "http":
            toolsets.append(MCPToolset(v.url, headers=v.headers))
    return toolsets


local_memory = LocalMemory("memory.txt")

agent = Agent(model)


@agent.instructions
def get_instructions() -> str:
    return """
# Role & Behavioral Guidelines

你是一个配备了主动记忆库的智能助手。你有两个工具：
1. `search_memory`: 搜索历史记忆。
2. `save_memory`: 保存新记忆。

在与用户的每一轮交互中，你必须严格遵循以下**主动记忆工作流**：

---

## 核心工作流 (Workflow per Turn)

### 阶段 1：自动检索 (Pre-Response Search)
在处理用户的输入并生成最终回复**之前**：
1. **分析意图**：评估用户当前的问题或主题是否可能依赖过去的历史信息（如偏好、过往经历、特定约定、项目细节等）。
2. **主动检索**：如果存在潜在相关性，**优先调用 `search_memory`** 检索相关背景。
3. **结合上下文**：根据检索到的记忆信息，提供个性化、针对性的回复。如果未找到相关记忆，正常回复即可，无需主动向用户声明“我检索了记忆但没找到”。

### 阶段 2：自主判断与存储 (Post-Input Memory Extraction)
在生成回复的过程中或完成回复后，分析用户在本轮对话中提供的信息：
1. **评估价值**：判断用户是否透露了具有**长期保留价值**的信息。
   - **应当记忆（Save）**：用户的个人偏好（如“我不吃辣”）、基本信息（职业、角色、技术栈）、长期目标、重要约束条件、习惯或频繁提及的对象。
   - **无需记忆（Ignore）**：一次性的问答（如“今天天气如何”）、临时指令（如“把这段代码翻译成 Python”）、闲聊废话、或是过于宽泛模糊的信息。
2. **主动保存**：一旦符合保存标准，**无需等待用户明确指示“请记住这个”**，静默或随回复一同调用 `save_memory`。
3. **提炼存储**：调用 `save_memory` 时，存储的文本必须经过**提炼和去语境化**（例如：将“我一般习惯用 Mac 电脑”提炼为“用户习惯使用的操作系统：macOS”），确保后续搜索的高准确度。

---

## 工具调用原则

- **隐式与自然**：存储记忆是你的后台管理行为，除非用户主动询问（如“你记得我喜欢什么吗”），否则无需在回复中强调“我已经将 xx 存入了记忆”。
- **精炼高质**：不要将整段对话直接存入 `save_memory`，只存提取出的结构化/半结构化关键事实。
- **避免重复**：如果你通过 `search_memory` 发现该信息已被准确记录，无需再次调用 `save_memory`。
"""


@agent.tool_plain
def save_memory(data: str) -> str:
    local_memory.store(data)
    return "ok"


@agent.tool_plain
def search_memory(keywords: list[str]) -> list[str]:
    return local_memory.search(keywords)


class Settings(BaseSettings):
    resume: str = Field(default="", description="session_id to resume")
    model_config = SettingsConfigDict(cli_parse_args=True)


async def main():
    settings = Settings()

    session_id = uuid.uuid4()
    if settings.resume != "":
        session_id = settings.resume
    print(f"[info] using session {session_id}")
    sess = LocalSession(filename=f"sessions/{session_id}.json")

    messages = sess.load()

    while True:
        try:
            user_input = input("[user] > ")
            if user_input.strip():
                if user_input == "quit":
                    break

                currentTag = ""
                async with agent.run_stream_events(
                    user_prompt=user_input,
                    message_history=messages,
                    toolsets=load_mcp_servers(cfg.mcpServers),
                ) as events:
                    async for event in events:
                        data = parse_event(event)
                        if data is None:
                            continue

                        # print(f"[event] {data}")
                        if data["type"] == "final":
                            messages = data["all_messages"]
                            print(f"\n[usage] {data['usage']}")
                        elif data["type"] in ["tool_call", "tool_result"]:
                            print(f"\n[tool] {data}")
                        elif data["type"] in ["thinking", "text"]:
                            if data["type"] != currentTag:
                                print(f"\n[{data['type']}]")
                                currentTag = data["type"]
                            print(data["content"], end="")
                        else:
                            print(f"\n[DEBUG] {data=}")
                    print()

        except KeyboardInterrupt, EOFError:
            break

    sess.store(messages=messages)


if __name__ == "__main__":
    asyncio.run(main())
