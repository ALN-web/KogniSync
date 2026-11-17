from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.ai.copilot import check_grounding
from app.ai.intent import TripIntent, parse_rules
from app.ai.llm import Turn
from app.domain.models import IST
from app.main import create_app
from app.services.kv import MemoryKV
from tests.conftest import NOW, FakeClock, make_settings
from tests.fakes import FakeLLM, call, last_tool_result


def ai_client(llm, **settings) -> TestClient:
    return TestClient(
        create_app(make_settings(**settings), clock=FakeClock(), kv=MemoryKV(), llm=llm)
    )


# ---------------- rule-based intent parsing ----------------


def test_rules_parse_the_spec_example():
    i = parse_rules("Reach CP Delhi by 10am Monday under ₹8,000, prefer train", NOW)
    assert i.origin is None and i.destination == "CP Delhi"
    assert i.budget_inr == 8000
    assert i.prefer_modes == ["train"]
    # NOW is Monday 06:00, so "Monday 10am" is today.
    assert datetime.fromisoformat(i.arrive_by) == datetime(2026, 11, 23, 10, 0, tzinfo=IST)


@pytest.mark.parametrize(
    "text, budget",
    [
        ("under 8k", 8000),
        ("budget of rs 12,500", 12500),
        ("below INR 900", 900),
        ("within ₹ 3000", 3000),
    ],
)
def test_rules_parse_budgets(text, budget):
    assert parse_rules(f"Pune to Mumbai {text}", NOW).budget_inr == budget


def test_rules_parse_route_avoid_and_departure():
    i = parse_rules("from Koramangala to Whitefield leaving at 7pm tomorrow, no cabs", NOW)
    assert (i.origin, i.destination) == ("Koramangala", "Whitefield")
    assert i.avoid_modes == ["cab"]
    assert datetime.fromisoformat(i.depart_after) == datetime(2026, 11, 24, 19, 0, tzinfo=IST)
    i = parse_rules("Udayapalya, Bengaluru to CP Delhi by train", NOW)
    assert (i.origin, i.destination) == ("Udayapalya, Bengaluru", "CP Delhi")
    assert i.prefer_modes == ["train"]


def test_grounding_check():
    payloads = [{"cost_inr": 8327, "journeys": [{"cost_display": "₹3,440"}]}]
    assert check_grounding("Total ₹8,327 (live).", payloads).verified
    assert check_grounding("Cheapest ₹3,440.", payloads).verified
    bad = check_grounding("Only ₹1,999!", payloads)
    assert not bad.verified and bad.ungrounded_amounts == [1999]
    assert check_grounding("Under your ₹9,000 budget", payloads, "budget 9000").verified


# ---------------- fallback (no Gemini key) ----------------


def test_chat_without_key_uses_offline_planner(client):
    res = client.post(
        "/api/v1/copilot/chat", json={"message": "Udayapalya, Bengaluru to CP Delhi under 9000"}
    ).json()
    assert res["ai_mode"] == "fallback"
    assert res["tool_calls"][0]["name"] == "search_journeys"
    assert res["tool_calls"][0]["args"]["budget_inr"] == 9000
    assert res["journeys"] and "Recommended" in res["answer"]
    assert res["grounding"]["verified"] is True


def test_fallback_asks_for_origin_then_uses_context(client):
    msg = "Reach CP Delhi by 10am tuesday under ₹9,000, prefer train"
    res = client.post("/api/v1/copilot/chat", json={"message": msg}).json()
    assert "Where are you starting from" in res["answer"] and not res["tool_calls"]
    res = client.post(
        "/api/v1/copilot/chat",
        json={"message": msg, "context": {"origin": "Udayapalya, Bengaluru"}},
    ).json()
    args = res["tool_calls"][0]["args"]
    assert args["budget_inr"] == 9000 and args["prefer_modes"] == ["train"]
    assert args["arrive_by"].startswith("2026-11-24T10:00")


def test_fallback_disruption_and_hold_proposal(client):
    j = client.post(
        "/api/v1/journeys/search", json={"origin": "Koramangala", "destination": "Whitefield"}
    ).json()
    jid = j["journeys"][0]["id"]
    res = client.post(
        "/api/v1/copilot/chat", json={"message": "book this", "context": {"journey_id": jid}}
    ).json()
    assert res["proposed_action"]["journey_id"] == jid
    assert res["proposed_action"]["requires_consent"] is True
    assert res["grounding"]["verified"]
    res = client.post("/api/v1/copilot/chat", json={"message": "any delays?"}).json()
    assert res["answer"] == "No active disruptions right now."


def test_status_without_key(client):
    assert client.get("/api/v1/copilot/status").json()["gemini_configured"] is False


# ---------------- Gemini path (scripted fake) ----------------


def _quote_recommended(messages):
    result = last_tool_result(messages)
    rec = result["journeys"][0]
    return Turn(
        text=f"Best: {rec['route']} for {rec['cost_display']} ({rec['cost_provenance']}).",
        tool_calls=[],
    )


def test_gemini_tool_loop_grounded_answer():
    llm = FakeLLM(
        [
            call("search_journeys", origin="Udayapalya, Bengaluru", destination="CP Delhi"),
            _quote_recommended,
        ]
    )
    res = (
        ai_client(llm)
        .post("/api/v1/copilot/chat", json={"message": "Udayapalya to CP Delhi"})
        .json()
    )
    assert res["ai_mode"] == "gemini"
    assert [t["name"] for t in res["tool_calls"]] == ["search_journeys"]
    assert res["grounding"]["verified"] and res["notice"] is None
    assert res["journeys"]
    assert "Current time: Monday 23 November 2026" in llm.systems[0]


def test_gemini_invented_price_is_replaced():
    llm = FakeLLM(
        [
            call("search_journeys", origin="Udayapalya", destination="CP Delhi"),
            Turn(text="You can fly for just ₹999!", tool_calls=[]),
        ]
    )
    c = ai_client(llm)
    res = c.post("/api/v1/copilot/chat", json={"message": "cheap flight to delhi"}).json()
    assert res["grounding"]["verified"] is False
    assert res["grounding"]["ungrounded_amounts"] == [999]
    assert "₹999" not in res["answer"] and "Recommended" in res["answer"]
    assert res["notice"]
    assert c.app.state.container.telemetry.counters["grounding_rejected"] == 1


def test_gemini_create_hold_only_proposes():
    c = ai_client(None)
    jid = c.post(
        "/api/v1/journeys/search", json={"origin": "Koramangala", "destination": "Whitefield"}
    ).json()["journeys"][0]["id"]
    llm = FakeLLM(
        [
            call("create_hold", journey_id=jid),
            Turn(text="I've prepared it; please confirm in the app.", tool_calls=[]),
        ]
    )
    c.app.state.container.copilot.llm = llm
    res = c.post("/api/v1/copilot/chat", json={"message": "hold it"}).json()
    assert res["proposed_action"]["journey_id"] == jid
    assert c.app.state.container.telemetry.counters.get("hold_created", 0) == 0


def test_invalid_tool_args_are_reported_back():
    seen = {}

    def check(messages):
        seen.update(last_tool_result(messages))
        return Turn(text="Which city?", tool_calls=[])

    llm = FakeLLM([call("search_journeys", destination="Delhi"), check])
    res = ai_client(llm).post("/api/v1/copilot/chat", json={"message": "to delhi"}).json()
    assert res["tool_calls"][0]["ok"] is False
    assert seen["error"] == "invalid arguments"


def test_gemini_failure_falls_back():
    c = ai_client(FakeLLM(fail=True))
    res = c.post("/api/v1/copilot/chat", json={"message": "Koramangala to Whitefield"}).json()
    assert res["ai_mode"] == "fallback" and res["journeys"]
    assert "unavailable" in res["notice"]
    assert c.app.state.container.telemetry.counters["gemini_error"] == 1


def test_intent_endpoint_uses_structured_output():
    llm = FakeLLM(json_result=TripIntent(origin="Udayapalya", destination="CP", budget_inr=8000))
    res = ai_client(llm).post("/api/v1/copilot/intent", json={"text": "..."}).json()
    assert res["ai_mode"] == "gemini" and res["intent"]["budget_inr"] == 8000
    assert llm.json_calls[0][1] is TripIntent


def test_rate_limit():
    c = ai_client(None, copilot_rate_limit_per_min=2)
    codes = [c.post("/api/v1/copilot/chat", json={"message": "hi"}).status_code for _ in range(3)]
    assert codes == [200, 200, 429]


# ---------------- AI Reliability Copilot ----------------


def test_reliability_summary_fallback_and_gemini(client):
    container = client.app.state.container
    container.telemetry.event("booking_compensated", hold_id="H1")
    container.telemetry.event("hold_conflict", service_id="X")
    res = client.post("/api/v1/ops/reliability-summary").json()
    assert res["ai_mode"] == "fallback"
    severities = {f["title"]: f["severity"] for f in res["findings"]}
    assert severities["Booking saga compensations"] == "critical"
    assert "Hold conflicts" in severities
    container.copilot.llm = FakeLLM(text="One booking was rolled back; check the vendor.")
    res = client.post("/api/v1/ops/reliability-summary").json()
    assert res["ai_mode"] == "gemini" and "rolled back" in res["summary"]


def test_provider_health(client):
    body = client.get("/api/v1/ops/providers").json()
    assert body["data_mode"] == "mock"
    assert body["ai"]["gemini_configured"] is False
    assert len(body["providers"]) == 6
