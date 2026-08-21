import asyncio
import uuid
from pathlib import Path

import logfire
from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.capabilities import Capability
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


def load_mcp_servers(servers: dict[str, MCPConfig]) -> list[Capability]:
    caps = []
    for k, v in servers.items():
        if not v.enable:
            continue
        if v.type == "http":
            caps.append(
                Capability(
                    id=k,
                    toolsets=[MCPToolset(v.url, headers=v.headers)],
                    defer_loading=True,
                )
            )
    return caps


def load_skills(dir: str) -> list[Capability]:
    caps = []
    for skill_file in Path(dir).glob("**/skill.md", case_sensitive=False):
        cap = parse_skill_md(skill_file)
        cap.defer_loading = True
        caps.append(cap)
    return caps


def parse_skill_md(file_path: Path) -> Capability:
    content = file_path.read_text(encoding="utf-8")
    skill_id = file_path.parent.name
    description = ""
    instructions = content

    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            header, instructions = parts[1], parts[2].strip()
            for line in header.strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    k, v = k.strip(), v.strip()
                    if k in ("id", "name"):
                        skill_id = v
                    elif k == "description":
                        description = v

    return Capability(
        id=skill_id,
        description=description or f"技能包: {skill_id}",
        instructions=instructions,
    )


agent = Agent(
    model,
    capabilities=[
        *load_mcp_servers(cfg.mcpServers),
        *load_skills(cfg.skill_dir),
    ],
)


@agent.instructions
def get_instructions() -> str:
    return "你是一个专业的个人助手，回答简单直接，风格冷酷。并且永远以用户使用的语言进行回复"


@agent.tool_plain(retries=1)
def bash(args: list[str]) -> dict:
    """
    The `args` argument MUST be provided as a list of strings (`list[str]`),
    where the executable and every flag/argument are separated into distinct list elements
    (similar to Python's `subprocess.run` array format).
    Do NOT pass the entire command as a single string inside a list.
    """
    import subprocess

    result = subprocess.run(args, check=False, capture_output=True, text=True)
    return {"code": result.returncode, "stdout": result.stdout}


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
