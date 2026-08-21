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


agent = Agent(model)


@agent.instructions
def get_instructions() -> str:
    return "你是一个专业的个人助手，回答简单直接，风格冷酷。并且永远以用户使用的语言进行回复"


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
