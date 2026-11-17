"""Free text -> validated trip constraints.

With Gemini: structured JSON output against ``TripIntent``, then validated here.
Without Gemini: a deterministic rule-based parser that handles the common phrasings.
"""

import re
from datetime import datetime, time, timedelta
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.models import IST, as_ist

ModeName = Literal["flight", "train", "bus", "cab", "rapido", "metro", "walk"]


class TripIntent(BaseModel):
    origin: str | None = Field(None, description="Start place as the user said it")
    destination: str | None = Field(None, description="End place as the user said it")
    depart_after: str | None = Field(None, description="ISO 8601 local IST datetime")
    arrive_by: str | None = Field(None, description="ISO 8601 local IST datetime")
    budget_inr: int | None = Field(None, description="Total budget in rupees")
    passengers: int | None = None
    prefer_modes: list[ModeName] = Field(default_factory=list)
    avoid_modes: list[ModeName] = Field(default_factory=list)
    language: str | None = Field(None, description="Language the user wrote in, e.g. 'hi'")


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return as_ist(datetime.fromisoformat(value))
    except ValueError:
        return None


_MODES = "flight|train|bus|cab|taxi|metro|rapido|bike|walk"
_MODE_NORMAL = {
    "taxi": "cab",
    "bike": "rapido",
    "flights": "flight",
    "trains": "train",
    "buses": "bus",
    "cabs": "cab",
    "taxis": "cab",
}
_DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
_STOP = (
    r"(?=\s+(?:by|before|under|below|within|on|at|tomorrow|today|tonight|prefer|"
    r"preferably|avoid|no|without|with|leaving|leave|for|budget|max)\b|[,.?!;]|$)"
)


def _mode(word: str) -> str:
    word = word.lower()
    return _MODE_NORMAL.get(word, word.rstrip("s") if word.rstrip("s") in _MODES else word)


def _day(text: str, now: datetime) -> datetime | None:
    if "tomorrow" in text:
        return now + timedelta(days=1)
    if "today" in text or "tonight" in text:
        return now
    for i, name in enumerate(_DAYS):
        if re.search(rf"\b{name}\b", text):
            return now + timedelta(days=(i - now.weekday()) % 7)
    return None


def _clock(h: str, m: str | None, ampm: str | None) -> time | None:
    hour, minute = int(h), int(m or 0)
    if ampm:
        if hour == 12:
            hour = 0
        if ampm.lower() == "pm":
            hour += 12
    if hour > 23 or minute > 59:
        return None
    return time(hour, minute)


def _when(text: str, pattern: str, now: datetime) -> datetime | None:
    m = re.search(pattern + r"\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b(.*)", text)
    if not m:
        return None
    t = _clock(m.group(1), m.group(2), m.group(3))
    if t is None:
        return None
    day = _day(m.group(4)[:30] + " " + text[: m.start()], now) or now
    dt = datetime.combine(day.date(), t, IST)
    if dt <= now and "today" not in text and "tonight" not in text:
        # "by 9am" at 10am means tomorrow; "by 9am Monday" on a Monday means next week.
        named_day = any(re.search(r"\b" + d + r"\b", text) for d in _DAYS)
        dt += timedelta(days=7 if named_day else 1)
    return dt


def parse_rules(text: str, now: datetime) -> TripIntent:
    raw = " ".join(text.replace("₹", " ₹").split())
    low = raw.lower()

    budget = None
    m = re.search(
        r"(?:under|below|less than|within|budget(?: of| is)?|max(?:imum)?|upto|up to)"
        r"\s*(?:₹|rs\.?|inr|rupees)?\s*([\d,]+(?:\.\d+)?)\s*(k)?\b",
        low,
    )
    if m:
        budget = int(float(m.group(1).replace(",", "")) * (1000 if m.group(2) else 1))

    arrive_by = _when(low, r"\b(?:by|before|reach by|arrive by)", now)
    depart_after = _when(
        low, r"\b(?:leave|leaving|depart|departing|start|starting)\s+(?:at|after|around)?", now
    )

    prefer = [
        _mode(w)
        for w in re.findall(rf"\bprefer(?:ably|ring)?\s+(?:a\s+|the\s+|by\s+)?({_MODES})s?\b", low)
    ]
    prefer += [_mode(w) for w in re.findall(rf"\bby\s+({_MODES})s?\b", low)]
    avoid = [
        _mode(w)
        for w in re.findall(rf"\b(?:avoid|no|without|not by|skip)\s+(?:the\s+)?({_MODES})s?\b", low)
    ]

    origin = destination = None
    m = re.search(r"\bfrom\s+(.+?)\s+to\s+(.+?)" + _STOP, raw, re.IGNORECASE)
    if m:
        origin, destination = m.group(1), m.group(2)
    else:
        m = re.search(
            r"^(?:please\s+)?(?:plan\s+(?:a\s+)?(?:trip|journey|route)\s+)?"
            r"(?:get me\s+|take me\s+|go\s+|travel\s+|i want to go\s+)?(?:from\s+)?"
            r"([a-z][\w ,.'-]*?)\s+to\s+(.+?)" + _STOP,
            raw,
            re.IGNORECASE,
        )
        if m and not re.match(r"(?:how|what|is|can|reach|want)\b", m.group(1), re.IGNORECASE):
            origin, destination = m.group(1), m.group(2)
        else:
            m = re.search(
                r"\b(?:reach|get to|go to|travel to|to)\s+(.+?)" + _STOP, raw, re.IGNORECASE
            )
            if m:
                destination = m.group(1)
    clean = lambda s: s.strip(" ,.") if s else None  # noqa: E731
    return TripIntent(
        origin=clean(origin),
        destination=clean(destination),
        depart_after=depart_after.isoformat() if depart_after else None,
        arrive_by=arrive_by.isoformat() if arrive_by else None,
        budget_inr=budget,
        prefer_modes=[p for p in dict.fromkeys(prefer) if p in _MODES.split("|")],
        avoid_modes=[a for a in dict.fromkeys(avoid) if a in _MODES.split("|")],
    )
