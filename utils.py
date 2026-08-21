import json

from pydantic_ai import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    PartDeltaEvent,
    PartStartEvent,
    TextPart,
    TextPartDelta,
    ThinkingPart,
    ThinkingPartDelta,
)
from pydantic_ai.run import AgentRunResultEvent


def parse_event(event) -> dict | None:
    match event:
        case PartStartEvent() as evt:
            type_str = "unknown"
            if isinstance(evt.part, ThinkingPart):
                type_str = "thinking"
            elif isinstance(evt.part, TextPart):
                type_str = "text"
            else:
                return

            return {
                "type": type_str,
                "content": evt.part.content,
            }
        case PartDeltaEvent() as evt:
            type_str = "unknown"
            if isinstance(evt.delta, ThinkingPartDelta):
                type_str = "thinking"
            elif isinstance(evt.delta, TextPartDelta):
                type_str = "text"
            else:
                return

            return {
                "type": type_str,
                "content": evt.delta.content_delta,
            }
        case FunctionToolCallEvent() as evt:
            args = event.part.args
            if not isinstance(args, str) and not isinstance(args, dict):
                return

            try:
                if isinstance(args, str):
                    args = json.loads(args)
            except json.JSONDecodeError, ValueError:
                pass

            return {
                "type": "tool_call",
                "name": evt.part.tool_name,
                "call_id": evt.part.tool_call_id,
                "args": args if args is not None else {},
            }
        case FunctionToolResultEvent() as evt:
            content = evt.part.content
            if isinstance(content, str):
                content_str = content
            elif content is None:
                content_str = ""
            else:
                content_str = json.dumps(content, ensure_ascii=False)

            return {
                "type": "tool_result",
                "name": evt.part.tool_name,
                "call_id": evt.part.tool_call_id,
                "content": content_str,
            }
        case AgentRunResultEvent() as evt:
            usage = evt.result.usage
            return {
                "type": "final",
                "usage": {
                    "requests": usage.requests,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                },
                "all_messages": evt.result.all_messages(),
            }
        case _:
            pass
