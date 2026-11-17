"""Provider-neutral LLM interface plus the Gemini implementation (google-genai SDK).

The copilot only talks to ``LLM``. Tests use a scripted fake; production uses ``GeminiLLM``.
When GEMINI_API_KEY is not set, ``build_llm`` returns None and every AI feature falls back
to deterministic behavior instead of failing.
"""

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


@dataclass
class Media:
    data: bytes
    mime_type: str


Part = str | Media


@dataclass
class ToolSpec:
    name: str
    description: str
    parameters: dict[str, Any]  # JSON schema


@dataclass
class ToolCall:
    name: str
    args: dict[str, Any]
    id: str | None = None


@dataclass
class ToolResult:
    name: str
    result: dict[str, Any]
    id: str | None = None


@dataclass
class Msg:
    role: Literal["user", "model", "tool"]
    text: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    tool_results: list[ToolResult] = field(default_factory=list)
    raw: Any = None  # provider-native content, replayed verbatim (keeps thought signatures)


@dataclass
class Turn:
    text: str | None
    tool_calls: list[ToolCall]
    raw: Any = None


class LLM(Protocol):
    name: str

    async def generate_json(
        self,
        parts: list[Part],
        schema: type[M],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> M: ...

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str: ...

    async def tool_turn(self, system: str, messages: list[Msg], tools: list[ToolSpec]) -> Turn: ...


class GeminiLLM:
    name = "gemini"

    def __init__(self, api_key: str, model: str, client: Any = None):
        from google import genai

        self.client = client or genai.Client(api_key=api_key)
        self.model = model

    @staticmethod
    def _part(p: Part):
        from google.genai import types

        if isinstance(p, Media):
            return types.Part.from_bytes(data=p.data, mime_type=p.mime_type)
        return types.Part.from_text(text=p)

    async def generate_json(
        self,
        parts: list[Part],
        schema: type[M],
        *,
        system: str | None = None,
        model: str | None = None,
    ) -> M:
        from google.genai import types

        resp = await self.client.aio.models.generate_content(
            model=model or self.model,
            contents=[types.Content(role="user", parts=[self._part(p) for p in parts])],
            config=types.GenerateContentConfig(
                system_instruction=system,
                response_mime_type="application/json",
                response_schema=schema,
                temperature=0.1,
            ),
        )
        # Validate ourselves: model output is untrusted until it passes the schema.
        return schema.model_validate_json(resp.text or "{}")

    async def generate_text(self, prompt: str, *, system: str | None = None) -> str:
        from google.genai import types

        resp = await self.client.aio.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(system_instruction=system, temperature=0.2),
        )
        return resp.text or ""

    def _contents(self, messages: list[Msg]) -> list:
        from google.genai import types

        contents = []
        for m in messages:
            if m.raw is not None:
                contents.append(m.raw)
            elif m.role == "user":
                contents.append(
                    types.Content(role="user", parts=[types.Part.from_text(text=m.text or "")])
                )
            elif m.role == "model":
                parts = [types.Part.from_text(text=m.text)] if m.text else []
                parts += [
                    types.Part(function_call=types.FunctionCall(name=c.name, args=c.args, id=c.id))
                    for c in m.tool_calls
                ]
                contents.append(types.Content(role="model", parts=parts))
            else:
                contents.append(
                    types.Content(
                        role="user",
                        parts=[
                            types.Part(
                                function_response=types.FunctionResponse(
                                    name=r.name, response=r.result, id=r.id
                                )
                            )
                            for r in m.tool_results
                        ],
                    )
                )
        return contents

    async def tool_turn(self, system: str, messages: list[Msg], tools: list[ToolSpec]) -> Turn:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            tools=[
                types.Tool(
                    function_declarations=[
                        types.FunctionDeclaration(
                            name=t.name,
                            description=t.description,
                            parameters_json_schema=t.parameters,
                        )
                        for t in tools
                    ]
                )
            ],
            # We run tools ourselves so consent and validation rules always apply.
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )
        resp = await self.client.aio.models.generate_content(
            model=self.model, contents=self._contents(messages), config=config
        )
        calls = [
            ToolCall(name=fc.name or "", args=dict(fc.args or {}), id=fc.id)
            for fc in (resp.function_calls or [])
        ]
        raw = resp.candidates[0].content if resp.candidates else None
        text = None
        if not calls and raw is not None:
            text = "".join(
                p.text
                for p in (raw.parts or [])
                if getattr(p, "text", None) and not getattr(p, "thought", False)
            )
        return Turn(text=text, tool_calls=calls, raw=raw)


def build_llm(api_key: str | None, model: str) -> LLM | None:
    if not api_key:
        return None
    return GeminiLLM(api_key, model)
