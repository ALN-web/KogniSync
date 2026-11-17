from collections.abc import Callable
from typing import Any

from app.ai.llm import Msg, ToolCall, ToolSpec, Turn


class FakeLLM:
    """Scripted stand-in for Gemini. Each tool turn pops the next script entry; an entry can
    be a Turn or a function of the conversation so far."""

    name = "fake"

    def __init__(
        self,
        turns: list[Turn | Callable[[list[Msg]], Turn]] | None = None,
        json_result: Any = None,
        text: str = "summary",
        fail: bool = False,
    ):
        self.turns = list(turns or [])
        self.json_result = json_result
        self.text = text
        self.fail = fail
        self.systems: list[str] = []
        self.json_calls: list[tuple[list, type]] = []

    async def tool_turn(self, system: str, messages: list[Msg], tools: list[ToolSpec]) -> Turn:
        if self.fail:
            raise RuntimeError("quota exceeded")
        self.systems.append(system)
        if not self.turns:
            return Turn(text="Done.", tool_calls=[])
        nxt = self.turns.pop(0)
        return nxt(messages) if callable(nxt) else nxt

    async def generate_json(self, parts, schema, *, system=None, model=None):
        if self.fail:
            raise RuntimeError("quota exceeded")
        self.json_calls.append((parts, schema))
        return self.json_result

    async def generate_text(self, prompt: str, *, system=None) -> str:
        if self.fail:
            raise RuntimeError("quota exceeded")
        return self.text


def call(name: str, **args) -> Turn:
    return Turn(text=None, tool_calls=[ToolCall(name=name, args=args, id="c1")])


def last_tool_result(messages: list[Msg]) -> dict:
    return messages[-1].tool_results[0].result
