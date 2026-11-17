"""M6: traveler copilot.

Gemini decides which tools to call; KogniSync's deterministic services produce every number.
Guardrails:
- tools are run by us after schema validation (automatic function calling is off);
- ``create_hold`` only proposes; booking needs the traveler's consent in the app;
- a grounding check rejects any rupee amount in the answer that no tool returned, and falls
  back to a templated answer built from the tool results.
"""

import logging
import re
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.ai.intent import TripIntent, parse_rules
from app.ai.llm import LLM, Msg, ToolResult
from app.ai.tools import ProposedAction, ToolContext, ToolRegistry, journey_summary
from app.domain.models import Journey

log = logging.getLogger(__name__)
MAX_STEPS = 5

SYSTEM = """You are KogniSync, a door-to-door travel copilot for India.
Current time: {now} (IST). Covered cities: Bengaluru, Delhi NCR, Mumbai, Hyderabad, Chennai,
Pune, Kolkata, Ahmedabad, Jaipur, Kochi, Lucknow, Chandigarh, Goa, Bhubaneswar.

Rules:
- Use tools for every fact about routes, fares, times, seats and disruptions. Never invent or
  estimate a fare, time or seat count yourself. Quote numbers exactly as tools return them.
- When you mention a fare or total, say whether it is live, scheduled or estimated.
- Budgets and deadlines are hard limits. If a tool says nothing fits, explain the gap; never
  suggest silently exceeding them.
- You cannot book or hold anything. To help the traveler book, call create_hold; the app then
  asks them to confirm. Never say a trip is booked or held.
- Data is from demo (mock) providers; say so if asked about accuracy.
- Be brief: 2-5 sentences. Use ISO 8601 IST datetimes in tool arguments.
- Reply in {language}.
{context}"""


class HistoryItem(BaseModel):
    role: Literal["user", "model"]
    text: str = Field(max_length=4000)


class ChatContext(BaseModel):
    trippass_id: str | None = None
    journey_id: str | None = None
    origin: str | None = Field(None, description="Default start, e.g. from GPS")
    reply_language: str | None = Field(None, description="e.g. 'Hindi'")


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    history: list[HistoryItem] = Field(default_factory=list, max_length=20)
    context: ChatContext = Field(default_factory=ChatContext)


class ToolTrace(BaseModel):
    name: str
    args: dict[str, Any]
    ok: bool


class Grounding(BaseModel):
    verified: bool
    ungrounded_amounts: list[int] = Field(default_factory=list)


class ChatResponse(BaseModel):
    answer: str
    ai_mode: Literal["gemini", "fallback"]
    tool_calls: list[ToolTrace] = Field(default_factory=list)
    journeys: list[dict[str, Any]] = Field(default_factory=list)
    proposed_action: ProposedAction | None = None
    grounding: Grounding
    notice: str | None = None


_AMOUNT = re.compile(r"(?:₹|rs\.?|inr|rupees)\s*([\d,]+)", re.IGNORECASE)


def _numbers(obj: Any, out: set[int]) -> set[int]:
    if isinstance(obj, bool):
        return out
    if isinstance(obj, int | float):
        out.add(int(obj))
    elif isinstance(obj, str):
        out.update(int(m.replace(",", "")) for m in re.findall(r"\d[\d,]*", obj))
    elif isinstance(obj, dict):
        for v in obj.values():
            _numbers(v, out)
    elif isinstance(obj, list):
        for v in obj:
            _numbers(v, out)
    return out


def check_grounding(answer: str, payloads: list[dict[str, Any]], user_text: str = "") -> Grounding:
    """Every rupee amount in the answer must come from a tool result (or the user's own
    words, e.g. their budget)."""
    known = _numbers(payloads, set()) | _numbers(user_text, set())
    amounts = [int(a.replace(",", "")) for a in _AMOUNT.findall(answer) if a.strip(",")]
    bad = [a for a in amounts if a not in known]
    return Grounding(verified=not bad, ungrounded_amounts=bad)


def template_answer(journeys: list[Journey], hints: list[str], origin: str, dest: str) -> str:
    if not journeys:
        return " ".join(hints) or f"I couldn't find a route from {origin} to {dest}."
    best = next((j for j in journeys if "recommended" in j.labels), journeys[0])
    s = journey_summary(best)
    lines = [
        f"I found {len(journeys)} options from {origin} to {dest} (demo data).",
        f"Recommended: {s['route']}. Leave {s['depart']}, arrive {s['arrive']} "
        f"({s['duration']}), {s['cost_display']} ({s['cost_provenance']}), "
        f"about {s['carbon_kg']} kg CO2.",
    ]
    for label, name in (("fastest", "Fastest"), ("cheapest", "Cheapest")):
        j = next((j for j in journeys if label in j.labels and j is not best), None)
        if j:
            js = journey_summary(j)
            lines.append(
                f"{name}: arrives {js['arrive']} for {js['cost_display']} "
                f"({js['cost_provenance']})."
            )
    return " ".join(lines)


class Copilot:
    def __init__(self, container, llm: LLM | None):
        self.c = container
        self.llm = llm
        self.tools = ToolRegistry(container)

    async def chat(self, req: ChatRequest) -> ChatResponse:
        if self.llm is None:
            return await self._fallback(req)
        try:
            return await self._gemini(req)
        except Exception:  # network, quota, safety block, bad output...
            log.exception("Gemini copilot failed; using fallback")
            self.c.telemetry.event("gemini_error", feature="copilot")
            resp = await self._fallback(req)
            resp.notice = "Gemini was unavailable, so the offline planner answered."
            return resp

    async def parse_intent(self, text: str) -> tuple[TripIntent, str]:
        now = self.c.clock()
        if self.llm is not None:
            try:
                intent = await self.llm.generate_json(
                    [
                        f"Current time: {now.isoformat()} (IST). Extract the trip request. "
                        f"Leave fields null if not stated.\n\nRequest: {text}"
                    ],
                    TripIntent,
                )
                return intent, "gemini"
            except Exception:
                log.exception("Gemini intent parsing failed; using rules")
                self.c.telemetry.event("gemini_error", feature="intent")
        return parse_rules(text, now), "fallback"

    # ---------------- Gemini path ----------------

    async def _gemini(self, req: ChatRequest) -> ChatResponse:
        ctx_lines = []
        if req.context.trippass_id:
            ctx_lines.append(f"The traveler's booked TripPass id is {req.context.trippass_id}.")
        if req.context.journey_id:
            ctx_lines.append(f"They are looking at journey id {req.context.journey_id}.")
        if req.context.origin:
            ctx_lines.append(f"If no start is given, start from: {req.context.origin}.")
        system = SYSTEM.format(
            now=self.c.clock().strftime("%A %d %B %Y %H:%M"),
            language=req.context.reply_language or "the language the traveler used",
            context="\n".join(ctx_lines),
        )
        messages = [Msg(role=h.role, text=h.text) for h in req.history]
        messages.append(Msg(role="user", text=req.message))
        ctx, trace = ToolContext(), []
        answer = None
        for _ in range(MAX_STEPS):
            turn = await self.llm.tool_turn(system, messages, self.tools.specs)
            if not turn.tool_calls:
                answer = (turn.text or "").strip()
                break
            messages.append(Msg(role="model", tool_calls=turn.tool_calls, raw=turn.raw))
            results = []
            for call in turn.tool_calls:
                result = await self.tools.execute(call.name, call.args, ctx)
                trace.append(ToolTrace(name=call.name, args=call.args, ok="error" not in result))
                results.append(ToolResult(name=call.name, result=result, id=call.id))
            messages.append(Msg(role="tool", tool_results=results))
        if not answer:
            answer = "Sorry, I couldn't finish that. Please try rephrasing."

        grounding = check_grounding(answer, ctx.payloads, req.message)
        notice = None
        if not grounding.verified:
            self.c.telemetry.event("grounding_rejected", amounts=grounding.ungrounded_amounts)
            notice = "The AI answer quoted a price no tool returned, so it was replaced."
            answer = self._from_payloads(ctx) or (
                "I can't confirm that price from live data. Please run a search."
            )
        return ChatResponse(
            answer=answer,
            ai_mode="gemini",
            tool_calls=trace,
            journeys=[journey_summary(j) for j in ctx.journeys],
            proposed_action=ctx.proposed_action,
            grounding=grounding,
            notice=notice,
        )

    def _from_payloads(self, ctx: ToolContext) -> str | None:
        if ctx.journeys:
            first = ctx.journeys[0]
            return template_answer(
                ctx.journeys, [], first.legs[0].origin.name, first.legs[-1].destination.name
            )
        return None

    # ---------------- offline fallback ----------------

    async def _fallback(self, req: ChatRequest) -> ChatResponse:
        text, low = req.message, req.message.lower()
        ctx, trace = ToolContext(), []

        async def call(name: str, args: dict) -> dict:
            result = await self.tools.execute(name, args, ctx)
            trace.append(ToolTrace(name=name, args=args, ok="error" not in result))
            return result

        def done(answer: str) -> ChatResponse:
            return ChatResponse(
                answer=answer,
                ai_mode="fallback",
                tool_calls=trace,
                journeys=[journey_summary(j) for j in ctx.journeys],
                proposed_action=ctx.proposed_action,
                grounding=check_grounding(answer, ctx.payloads, text),
            )

        if re.search(r"\b(disrupt\w*|delay\w*|cancel\w*|late|status|on time)\b", low):
            args = {"trippass_id": req.context.trippass_id} if req.context.trippass_id else {}
            r = await call("get_disruptions", args)
            if "impact" in r:
                return done(r["impact"]["summary"])
            n = len(r["disruptions"])
            return done(
                f"There {'is' if n == 1 else 'are'} {n} active disruption(s)."
                if n
                else "No active disruptions right now."
            )

        if re.search(r"\b(book|hold|reserve)\b", low) and req.context.journey_id:
            r = await call("create_hold", {"journey_id": req.context.journey_id})
            if "error" in r:
                return done("That journey has expired. Please search again.")
            return done(
                f"Ready to hold this trip for ₹{r['cost_inr']:,} in total. Review it "
                "and tap Confirm to hold seats; nothing is booked until you confirm."
            )

        intent = parse_rules(text, self.c.clock())
        origin = intent.origin or req.context.origin
        if intent.destination and origin:
            args = {
                k: v
                for k, v in {
                    "origin": origin,
                    "destination": intent.destination,
                    "depart_after": intent.depart_after,
                    "arrive_by": intent.arrive_by,
                    "budget_inr": intent.budget_inr,
                    "prefer_modes": intent.prefer_modes,
                    "avoid_modes": intent.avoid_modes,
                }.items()
                if v
            }
            r = await call("search_journeys", args)
            if "error" in r:
                return done(
                    f"{r['error']}. Try a locality or city name, e.g. 'Koramangala, Bengaluru'."
                )
            return done(
                template_answer(ctx.journeys, r["relaxation_hints"], r["origin"], r["destination"])
            )
        if intent.destination:
            return done(
                f"Where are you starting from? I'll plan a door-to-door route to "
                f"{intent.destination}."
            )
        return done(
            "I plan door-to-door trips across flights, trains, buses, cabs, Rapido, "
            "metro and walking. Try: 'Udayapalya, Bengaluru to CP Delhi by 10am Monday "
            "under 8000 rupees, prefer train'."
        )
