import time
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from pydantic import BaseModel, Field

from app.ai.copilot import ChatContext, ChatRequest, ChatResponse
from app.ai.intent import TripIntent
from app.ai.omni import (
    AUDIO_TYPES,
    IMAGE_TYPES,
    MAX_UPLOAD_BYTES,
    AINotConfigured,
    TicketExtraction,
    VoiceResult,
)
from app.api.v1.deps import ContainerDep, get_container

router = APIRouter(prefix="/copilot", tags=["copilot"])


def rate_limit(request: Request) -> None:
    """Per-client sliding window. Protects Gemini spend; Cloud Armor adds edge limits."""
    c = get_container(request)
    limit = c.settings.copilot_rate_limit_per_min
    client = request.headers.get("x-forwarded-for", "").split(",")[0].strip() or (
        request.client.host if request.client else "unknown"
    )
    now = time.monotonic()
    window = c.rate_hits[client]
    while window and now - window[0] > 60:
        window.popleft()
    if len(window) >= limit:
        raise HTTPException(429, "Too many copilot requests; try again in a minute")
    window.append(now)


Limited = Annotated[None, Depends(rate_limit)]


class StatusResponse(BaseModel):
    gemini_configured: bool
    model: str
    omni_model: str


@router.get("/status", response_model=StatusResponse)
async def status(c: ContainerDep) -> StatusResponse:
    return StatusResponse(
        gemini_configured=c.copilot.llm is not None,
        model=c.settings.gemini_model,
        omni_model=c.settings.gemini_omni_model,
    )


@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, c: ContainerDep, _: Limited) -> ChatResponse:
    return await c.copilot.chat(req)


class IntentRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class IntentResponse(BaseModel):
    intent: TripIntent
    ai_mode: str


@router.post("/intent", response_model=IntentResponse)
async def intent(req: IntentRequest, c: ContainerDep, _: Limited) -> IntentResponse:
    parsed, mode = await c.copilot.parse_intent(req.text)
    return IntentResponse(intent=parsed, ai_mode=mode)


async def _read(upload: UploadFile, allowed: set[str]) -> tuple[bytes, str]:
    mime = (upload.content_type or "").split(";")[0].strip().lower()
    if mime not in allowed:
        raise HTTPException(415, f"Unsupported file type {mime or 'unknown'}")
    data = await upload.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "File is larger than 10 MB")
    if not data:
        raise HTTPException(400, "Empty file")
    return data, mime


def _not_configured(e: AINotConfigured) -> HTTPException:
    return HTTPException(503, {"code": "ai_not_configured", "message": str(e)})


class VoiceResponse(BaseModel):
    voice: VoiceResult
    chat: ChatResponse


@router.post("/voice", response_model=VoiceResponse)
async def voice(
    c: ContainerDep,
    _: Limited,
    audio: UploadFile = File(...),
    language_hint: str | None = Form(None),
    trippass_id: str | None = Form(None),
    origin: str | None = Form(None),
) -> VoiceResponse:
    data, mime = await _read(audio, AUDIO_TYPES)
    try:
        heard = await c.omni.understand_voice(data, mime, c.clock().isoformat(), language_hint)
    except AINotConfigured as e:
        raise _not_configured(e) from e
    reply = await c.copilot.chat(
        ChatRequest(
            message=heard.transcript,
            context=ChatContext(
                trippass_id=trippass_id, origin=origin, reply_language=heard.language
            ),
        )
    )
    return VoiceResponse(voice=heard, chat=reply)


class VisionResponse(BaseModel):
    extraction: TicketExtraction
    suggested_search: dict[str, Any] | None = None


@router.post("/vision", response_model=VisionResponse)
async def vision(c: ContainerDep, _: Limited, image: UploadFile = File(...)) -> VisionResponse:
    data, mime = await _read(image, IMAGE_TYPES)
    try:
        doc = await c.omni.read_document(data, mime)
    except AINotConfigured as e:
        raise _not_configured(e) from e
    suggested = None
    if doc.destination:
        suggested = {
            "origin": doc.origin,
            "destination": doc.destination,
            "depart_after": doc.depart,
        }
    return VisionResponse(extraction=doc, suggested_search=suggested)
