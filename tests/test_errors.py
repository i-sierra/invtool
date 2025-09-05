import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.anyio
async def test_404_custom_page() -> None:
    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as ac:
        resp = await ac.get("/this-does-not-exist")

    assert resp.status_code == 404
    assert "Page not found" in resp.text


@pytest.mark.anyio
async def test_500_custom_page_non_prod(monkeypatch) -> None:
    monkeypatch.setenv("INV_ENV", "test")
    monkeypatch.setenv("INV_DEBUG", "false")

    app = create_app()
    async with AsyncClient(
        transport=ASGITransport(app=app, raise_app_exceptions=False), base_url="http://test"
    ) as ac:
        resp = await ac.get("/debug/error")

    assert resp.status_code == 500
    assert "Server error" in resp.text
