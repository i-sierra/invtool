import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.mark.anyio
async def test_flash_redirect_non_htmx() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Trigger message and normal redirect
        r1 = await ac.get("/demo/flash", follow_redirects=False)
        assert r1.status_code in (302, 303)
        assert r1.headers.get("location") == "/"

        # Follow redirect: message should be present once
        r2 = await ac.get("/")
        assert "Operation completed" in r2.text

        # Reload: message should be gone
        r3 = await ac.get("/")
        assert "Operation completed" not in r3.text


@pytest.mark.anyio
async def test_flash_hx_redirect_header() -> None:
    app = create_app()
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r1 = await ac.get("/demo/flash?msg=Hello HX", headers={"HX-Request": "true"})
        assert r1.status_code == 204
        assert r1.headers.get("HX-Redirect") == "/"

        # After redirect (simulated), message should appear once
        r2 = await ac.get("/")
        assert "Hello HX" in r2.text
