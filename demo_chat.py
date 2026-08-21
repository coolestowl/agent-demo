import asyncio

import logfire
from pydantic_ai import Agent

logfire.configure()
logfire.instrument_pydantic_ai()

from model import model
from utils import parse_event

agent = Agent(model)


@agent.instructions
def get_instructions() -> str:
    return "你是一个专业的个人助手，回答简单直接，风格冷酷。并且永远以用户使用的语言进行回复。"


async def main():
    user_input = input("[user] > ")

    currentTag = ""
    async with agent.run_stream_events(
        user_prompt=user_input,
    ) as events:
        async for event in events:
            data = parse_event(event)
            if data is None:
                continue

            # print(f"[event] {data}")
            if data["type"] == "final":
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


if __name__ == "__main__":
    asyncio.run(main())
