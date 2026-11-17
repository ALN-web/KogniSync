"""AI Reliability Copilot: turns telemetry (hold conflicts, compensations, feed freshness,
AI errors) into an incident summary for the ops team.

Deterministic findings are always computed. Gemini, when configured, writes the narrative
from those findings only.
"""

import json
import logging
from typing import Any, Literal

from pydantic import BaseModel

log = logging.getLogger(__name__)

PROVIDERS = [
    ("airline-fare-api", "flight fares and seats"),
    ("irctc-availability", "train seats"),
    ("bus-aggregator", "intercity bus fares and seats"),
    ("gtfs-metro", "metro timetables"),
    ("gtfs-bus", "city bus timetables"),
    ("cab-fare-estimates", "cab and Rapido estimates"),
]


class Finding(BaseModel):
    severity: Literal["info", "warning", "critical"]
    title: str
    detail: str
    suggested_fix: str


class ReliabilityReport(BaseModel):
    summary: str
    ai_mode: Literal["gemini", "fallback"]
    findings: list[Finding]
    snapshot: dict[str, Any]


async def provider_health(c) -> dict[str, Any]:
    counters = c.telemetry.counters
    feed = await c.disruptions.feed_health()
    return {
        "data_mode": "mock",
        "providers": [
            {"name": f"mock:{name}", "covers": covers, "status": "ok"} for name, covers in PROVIDERS
        ],
        "disruption_feed": feed,
        "vendors": {
            "hold_conflicts": counters.get("hold_conflict", 0),
            "compensations": counters.get("booking_compensated", 0),
        },
        "ai": {
            "gemini_configured": c.copilot.llm is not None,
            "gemini_errors": counters.get("gemini_error", 0),
            "grounding_rejections": counters.get("grounding_rejected", 0),
        },
    }


def findings_from(health: dict[str, Any], counters: dict[str, int]) -> list[Finding]:
    out: list[Finding] = []
    v = health["vendors"]
    if v["compensations"]:
        out.append(
            Finding(
                severity="critical",
                title="Booking saga compensations",
                detail=f"{v['compensations']} booking(s) failed at ticketing and were rolled back "
                "(tickets cancelled, payment refunded).",
                suggested_fix="Check the failing vendor's ticketing API status; consider pausing "
                "it in search until it recovers.",
            )
        )
    if v["hold_conflicts"]:
        out.append(
            Finding(
                severity="warning",
                title="Hold conflicts",
                detail=f"{v['hold_conflicts']} hold attempt(s) failed (sold out or vendor "
                "rejection). Earlier legs were released each time.",
                suggested_fix="Refresh seat inventory more often for busy routes; show low-seat "
                "warnings earlier.",
            )
        )
    feed = health["disruption_feed"]
    if feed["stale"]:
        out.append(
            Finding(
                severity="warning",
                title="Stale disruption data",
                detail=f"{feed['stale']} of {feed['active']} active disruption(s) have not been "
                "updated for 30+ minutes.",
                suggested_fix="Check the live feed poller (Cloud Scheduler job) and source "
                "availability.",
            )
        )
    ai = health["ai"]
    if ai["gemini_errors"]:
        out.append(
            Finding(
                severity="warning",
                title="Gemini errors",
                detail=f"{ai['gemini_errors']} Gemini call(s) failed and fell back to the offline "
                "planner.",
                suggested_fix="Check quota and API key in Secret Manager; review error logs.",
            )
        )
    if ai["grounding_rejections"]:
        out.append(
            Finding(
                severity="warning",
                title="Ungrounded AI answers blocked",
                detail=f"{ai['grounding_rejections']} answer(s) quoted prices no tool returned and "
                "were replaced.",
                suggested_fix="Review prompts; add eval cases for price quoting.",
            )
        )
    replays = counters.get("idempotent_replays", 0)
    if replays:
        out.append(
            Finding(
                severity="info",
                title="Idempotent retries",
                detail=f"{replays} retried request(s) were answered from the idempotency store "
                "(no double holds or charges).",
                suggested_fix="None needed; high numbers can indicate client network issues.",
            )
        )
    if not out:
        out.append(
            Finding(
                severity="info",
                title="All clear",
                detail="No incidents in the current telemetry window.",
                suggested_fix="None.",
            )
        )
    return out


def plain_summary(findings: list[Finding]) -> str:
    worst = [f for f in findings if f.severity == "critical"] or [
        f for f in findings if f.severity == "warning"
    ]
    if not worst:
        return "All systems normal."
    return "; ".join(f"{f.title}: {f.detail}" for f in worst)


async def reliability_report(c) -> ReliabilityReport:
    health = await provider_health(c)
    snapshot = {**health, "telemetry": c.telemetry.snapshot()}
    findings = findings_from(health, dict(c.telemetry.counters))
    llm = c.copilot.llm
    if llm is not None:
        try:
            text = await llm.generate_text(
                "Summarize these reliability findings for an on-call engineer in 3-4 "
                "sentences: what happened, impact on travelers, what to do first. Use only "
                "these facts.\n\n" + json.dumps([f.model_dump() for f in findings]),
                system="You are an SRE assistant for KogniSync. Never invent numbers.",
            )
            if text.strip():
                return ReliabilityReport(
                    summary=text.strip(), ai_mode="gemini", findings=findings, snapshot=snapshot
                )
        except Exception:
            log.exception("Gemini reliability summary failed")
            c.telemetry.event("gemini_error", feature="reliability")
    return ReliabilityReport(
        summary=plain_summary(findings), ai_mode="fallback", findings=findings, snapshot=snapshot
    )
