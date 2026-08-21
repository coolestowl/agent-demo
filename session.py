from pathlib import Path

from pydantic_ai import ModelMessagesTypeAdapter
from pydantic_ai.messages import ModelMessage
from pydantic_core import to_json


class LocalSession:
    def __init__(self, filename: str):
        self.filepath = Path(filename)
        self.empty = False
        if not self.filepath.exists():
            self.filepath.write_text("")
            self.empty = True

    def load(self) -> list[ModelMessage]:
        if self.empty:
            return []
        with self.filepath.open("r") as f:
            return ModelMessagesTypeAdapter.validate_json(f.read())

    def store(self, messages: list[ModelMessage]):
        with self.filepath.open("w") as f:
            f.write(
                str(to_json(messages, bytes_mode="utf8", indent=4), encoding="utf8")
            )
        if len(messages) > 0:
            self.empty = False
