"""Dependency checks for the readiness endpoint.

M1 checks only that Postgres and Redis accept TCP connections, so no database drivers are
needed yet. Real driver-level checks arrive with the data layer in M2/M4.
"""

import asyncio
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, SecretStr

Status = Literal["ok", "error", "not_configured"]

_DEFAULT_PORTS = {"postgresql": 5432, "postgres": 5432, "redis": 6379, "rediss": 6380}


class DependencyStatus(BaseModel):
    name: str
    status: Status
    detail: str | None = None


async def check_tcp(name: str, url: SecretStr | None, timeout: float = 1.0) -> DependencyStatus:
    if url is None:
        return DependencyStatus(name=name, status="not_configured")

    parts = urlsplit(url.get_secret_value())
    scheme = parts.scheme.split("+")[0]
    host = parts.hostname
    port = parts.port or _DEFAULT_PORTS.get(scheme)
    if not host or not port:
        return DependencyStatus(name=name, status="error", detail="invalid URL")

    try:
        _, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout)
    except (TimeoutError, OSError):
        # Never echo the URL: it may contain credentials.
        return DependencyStatus(name=name, status="error", detail="unreachable")
    writer.close()
    try:
        await writer.wait_closed()
    except OSError:
        pass
    return DependencyStatus(name=name, status="ok")


def check_secret_present(name: str, secret: SecretStr | None) -> DependencyStatus:
    return DependencyStatus(name=name, status="ok" if secret else "not_configured")
