from fastapi.testclient import TestClient

from app.ai.intent import TripIntent
from app.ai.omni import TicketExtraction, VoiceResult
from app.main import create_app
from app.services.kv import MemoryKV
from tests.conftest import FakeClock, make_settings
from tests.fakes import FakeLLM


def ai_client(llm) -> TestClient:
    return TestClient(create_app(make_settings(), clock=FakeClock(), kv=MemoryKV(), llm=llm))


AUDIO = {"audio": ("q.webm", b"\x1aE\xdf\xa3fake-webm", "audio/webm")}
IMAGE = {"image": ("ticket.jpg", b"\xff\xd8\xfffake-jpeg", "image/jpeg")}


def test_voice_and_vision_need_key(client):
    res = client.post("/api/v1/copilot/voice", files=AUDIO)
    assert res.status_code == 503 and res.json()["detail"]["code"] == "ai_not_configured"
    assert client.post("/api/v1/copilot/vision", files=IMAGE).status_code == 503


def test_voice_in_hindi_answers_in_hindi():
    heard = VoiceResult(
        transcript="Udayapalya se CP Delhi jaana hai, aath hazaar ke andar",
        language="Hindi",
        english="I want to go from Udayapalya to CP Delhi under 8000",
        intent=TripIntent(origin="Udayapalya", destination="CP Delhi", budget_inr=8000),
    )
    llm = FakeLLM(json_result=heard)
    res = ai_client(llm).post("/api/v1/copilot/voice", files=AUDIO, data={"language_hint": "Hindi"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["voice"]["language"] == "Hindi"
    assert body["chat"]["ai_mode"] == "gemini"
    parts, schema = llm.json_calls[0]
    assert schema is VoiceResult and parts[0].mime_type == "audio/webm"
    assert "Reply in Hindi" in llm.systems[0]


def test_vision_reads_ticket_and_suggests_search():
    doc = TicketExtraction(
        document_type="boarding_pass",
        mode="flight",
        operator="IndiGo",
        service_number="6E-2134",
        pnr="ABC123",
        origin="BLR",
        destination="DEL",
        depart="2026-11-23T11:15:00",
        confidence="high",
    )
    res = ai_client(FakeLLM(json_result=doc)).post("/api/v1/copilot/vision", files=IMAGE)
    body = res.json()
    assert body["extraction"]["pnr"] == "ABC123"
    assert body["suggested_search"] == {
        "origin": "BLR",
        "destination": "DEL",
        "depart_after": "2026-11-23T11:15:00",
    }


def test_upload_validation():
    c = ai_client(FakeLLM())
    bad_type = {"image": ("x.gif", b"GIF89a", "image/gif")}
    assert c.post("/api/v1/copilot/vision", files=bad_type).status_code == 415
    big = {"image": ("x.jpg", b"\xff" * (10 * 1024 * 1024 + 1), "image/jpeg")}
    assert c.post("/api/v1/copilot/vision", files=big).status_code == 413
    empty = {"audio": ("x.webm", b"", "audio/webm")}
    assert c.post("/api/v1/copilot/voice", files=empty).status_code == 400
