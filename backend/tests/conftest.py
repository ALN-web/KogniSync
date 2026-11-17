from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.domain.models import IST
from app.main import create_app
from app.services.kv import MemoryKV

# Monday morning, so tests see a normal weekday schedule.
NOW = datetime(2026, 11, 23, 6, 0, tzinfo=IST)


class FakeClock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        from datetime import timedelta

        self.now += timedelta(**kwargs)


def make_settings(**overrides) -> Settings:
    # _env_file=None keeps a developer's local .env from leaking into tests.
    return Settings(_env_file=None, **overrides)


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def client(clock: FakeClock) -> TestClient:
    return TestClient(create_app(make_settings(), clock=clock, kv=MemoryKV()))


@pytest.fixture
def container(client: TestClient):
    return client.app.state.container
