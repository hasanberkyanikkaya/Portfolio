from httpx import ASGITransport, AsyncClient

from app.core.database import get_db
from app.main import app


class FakeSession:
    async def execute(self, *args, **kwargs):
        return None


class BrokenSession:
    async def execute(self, *args, **kwargs):
        raise ConnectionError("db is down")


def override_with(session):
    async def _get_db():
        yield session

    return _get_db


async def request_health():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/health")


async def test_health_ok_when_db_is_up():
    app.dependency_overrides[get_db] = override_with(FakeSession())
    try:
        response = await request_health()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok"}


async def test_health_503_when_db_is_down():
    app.dependency_overrides[get_db] = override_with(BrokenSession())
    try:
        response = await request_health()
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json() == {"status": "ok", "database": "error"}
