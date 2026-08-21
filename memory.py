from pathlib import Path


class LocalMemory:
    def __init__(self, filename: str):
        self.filepath = Path(filename)
        self.empty = False
        if not self.filepath.exists():
            self.filepath.write_text("")
            self.empty = True

    def search(self, keywords: list[str]) -> list[str]:
        with self.filepath.open("r") as f:
            return [line.strip() for line in f if any(kw in line for kw in keywords)]

    def store(self, memory: str):
        with self.filepath.open("a") as f:
            f.write(f"{memory}\n")
