"""TripPass tokens and QR codes.

The QR encodes a compact signed token (HMAC-SHA256), so a gate or conductor app can check a
TripPass offline with the shared key, and a forged or edited pass fails verification.
"""

import base64
import hashlib
import hmac
import io
import json

import segno


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


class TripPassSigner:
    def __init__(self, key: bytes):
        self.key = key

    def sign(self, claims: dict) -> str:
        body = _b64(json.dumps(claims, separators=(",", ":"), sort_keys=True).encode())
        sig = _b64(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
        return f"{body}.{sig}"

    def verify(self, token: str) -> dict | None:
        try:
            body, sig = token.split(".")
            expected = _b64(hmac.new(self.key, body.encode(), hashlib.sha256).digest())
            if not hmac.compare_digest(sig, expected):
                return None
            return json.loads(_unb64(body))
        except (ValueError, json.JSONDecodeError):
            return None


def qr_svg(payload: str) -> str:
    buf = io.BytesIO()
    segno.make(payload, error="m").save(
        buf, kind="svg", scale=6, border=2, dark="#1f2328", light="#ffffff", xmldecl=False
    )
    return buf.getvalue().decode()
