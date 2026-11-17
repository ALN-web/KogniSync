"""M7: Gemini Omni multimodal input.

- Voice: audio in Hindi, Kannada, Tamil, Telugu or English -> transcript + trip intent; the
  copilot then answers in the same language (the browser speaks the reply).
- Vision: photo of a ticket, boarding pass, PNR SMS screenshot or departure board -> structured
  trip data validated against a schema.

Both need GEMINI_API_KEY. Without it they raise ``AINotConfigured`` (HTTP 503), and the web app
falls back to the browser's own speech recognition for voice.
"""

from typing import Literal

from pydantic import BaseModel, Field

from app.ai.intent import ModeName, TripIntent
from app.ai.llm import LLM, Media

AUDIO_TYPES = {
    "audio/webm",
    "audio/ogg",
    "audio/wav",
    "audio/x-wav",
    "audio/mpeg",
    "audio/mp4",
    "audio/aac",
    "audio/flac",
}
IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/heic"}
MAX_UPLOAD_BYTES = 10 * 1024 * 1024


class AINotConfigured(Exception):
    pass


class VoiceResult(BaseModel):
    transcript: str
    language: str = Field(description="Language name, e.g. Hindi")
    english: str = Field(description="English translation of the request")
    intent: TripIntent


class BoardRow(BaseModel):
    service: str
    destination: str | None = None
    time: str | None = None
    platform_or_gate: str | None = None
    status: str | None = None


class TicketExtraction(BaseModel):
    document_type: Literal["ticket", "boarding_pass", "pnr_sms", "departure_board", "other"]
    mode: ModeName | None = None
    operator: str | None = None
    service_number: str | None = None
    pnr: str | None = None
    origin: str | None = None
    destination: str | None = None
    depart: str | None = Field(None, description="ISO 8601 local datetime if visible")
    arrive: str | None = None
    seat: str | None = None
    platform_or_gate: str | None = None
    status: str | None = None
    board_rows: list[BoardRow] = Field(default_factory=list)
    confidence: Literal["high", "medium", "low"] = "medium"
    notes: str | None = None


VOICE_PROMPT = """Current time: {now} (IST). The audio is a traveler in India speaking
(possibly Hindi, Kannada, Tamil, Telugu, English or a mix). Transcribe it exactly, name the
language, translate it to English, and extract the trip request. Leave intent fields null if
not said."""

VISION_PROMPT = """Read this travel document or departure board photo. Extract only what is
clearly visible; use null when unsure and set confidence accordingly. Do not include passenger
names or phone numbers. For departure boards, list each row in board_rows."""


class Omni:
    def __init__(self, llm: LLM | None, model: str):
        self.llm, self.model = llm, model

    def _require(self) -> LLM:
        if self.llm is None:
            raise AINotConfigured("Voice and photo input need GEMINI_API_KEY")
        return self.llm

    async def understand_voice(
        self, audio: bytes, mime: str, now: str, language_hint: str | None = None
    ) -> VoiceResult:
        llm = self._require()
        prompt = VOICE_PROMPT.format(now=now)
        if language_hint:
            prompt += f" The traveler said they speak {language_hint}."
        return await llm.generate_json([Media(audio, mime), prompt], VoiceResult, model=self.model)

    async def read_document(self, image: bytes, mime: str) -> TicketExtraction:
        llm = self._require()
        return await llm.generate_json(
            [Media(image, mime), VISION_PROMPT], TicketExtraction, model=self.model
        )
