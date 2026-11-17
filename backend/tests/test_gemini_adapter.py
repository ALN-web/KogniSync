"""Drives the real GeminiLLM adapter against google-genai response objects (no network)."""

from google.genai import types

from app.ai.intent import TripIntent
from app.ai.llm import GeminiLLM, Msg, ToolResult, ToolSpec


class FakeModels:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def generate_content(self, *, model, contents, config):
        self.calls.append({"model": model, "contents": contents, "config": config})
        return self.responses.pop(0)


class FakeClient:
    def __init__(self, responses):
        self.aio = type("Aio", (), {})()
        self.aio.models = FakeModels(responses)


def response(*parts: types.Part) -> types.GenerateContentResponse:
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=list(parts)))]
    )


SPEC = ToolSpec(
    "search_journeys",
    "search",
    {"type": "object", "properties": {"origin": {"type": "string"}}, "required": ["origin"]},
)


async def test_tool_call_round_trip():
    fc = types.Part(
        function_call=types.FunctionCall(
            name="search_journeys", args={"origin": "BLR"}, id="call-1"
        )
    )
    client = FakeClient([response(fc), response(types.Part.from_text(text="Here you go."))])
    llm = GeminiLLM("k", "gemini-test", client=client)

    turn = await llm.tool_turn("sys", [Msg(role="user", text="hi")], [SPEC])
    assert [(c.name, c.args, c.id) for c in turn.tool_calls] == [
        ("search_journeys", {"origin": "BLR"}, "call-1")
    ]
    config = client.aio.models.calls[0]["config"]
    assert config.automatic_function_calling.disable is True
    decl = config.tools[0].function_declarations[0]
    assert decl.name == "search_journeys" and decl.parameters_json_schema == SPEC.parameters

    history = [
        Msg(role="user", text="hi"),
        Msg(role="model", tool_calls=turn.tool_calls, raw=turn.raw),
        Msg(role="tool", tool_results=[ToolResult("search_journeys", {"n": 1}, "call-1")]),
    ]
    turn2 = await llm.tool_turn("sys", history, [SPEC])
    assert turn2.text == "Here you go." and not turn2.tool_calls
    sent = client.aio.models.calls[1]["contents"]
    assert sent[1] is turn.raw  # model turn replayed verbatim (keeps thought signatures)
    fr = sent[2].parts[0].function_response
    assert (fr.name, fr.response, fr.id) == ("search_journeys", {"n": 1}, "call-1")


async def test_generate_json_validates_schema():
    client = FakeClient(
        [
            response(
                types.Part.from_text(
                    text='{"origin": "Udayapalya", "destination": "CP", "budget_inr": 8000}'
                )
            )
        ]
    )
    llm = GeminiLLM("k", "gemini-test", client=client)
    intent = await llm.generate_json(["text"], TripIntent)
    assert intent.budget_inr == 8000
    config = client.aio.models.calls[0]["config"]
    assert config.response_mime_type == "application/json"
