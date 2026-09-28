from __future__ import annotations

from fastapi.testclient import TestClient

# A representative slice of the frozen contract (see docs/AI_BRIEF.md A.7).
EXPECTED_PATHS = {
    "/api/auth/register",
    "/api/auth/login",
    "/api/auth/refresh",
    "/api/me",
    "/api/keys",
    "/api/folders",
    "/api/sources",
    "/api/discover",
    "/api/opml/import",
    "/api/opml/export",
    "/api/articles",
    "/api/articles/mark-all-read",
    "/api/v1/articles",
    "/api/v1/sources",
    "/api/v1/articles/{article_id}/read",
    "/api/v1/articles/{article_id}/save",
    "/api/v1/articles/{article_id}/favorite",
    "/api/site",
    "/api/admin/settings",
    "/api/admin/users",
    "/api/admin/maintenance",
    "/api/me/password",
    "/api/admin/bans",
    "/api/admin/users/{user_id}/ban",
    "/api/admin/users/{user_id}/suspend",
    "/api/sources/health",
    "/api/sync",
    "/api/filters/keywords",
    "/api/admin/plans",
    "/api/admin/sources",
}


def test_openapi_exposes_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"].keys())
    missing = EXPECTED_PATHS - paths
    assert not missing, f"missing contract paths: {sorted(missing)}"


def test_error_envelope_on_unauthorized(client: TestClient) -> None:
    # All endpoints are implemented now; check the {error:{code,message}}
    # envelope on a real error path (missing auth).
    resp = client.get("/api/me")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"]["code"] == "unauthorized"
    assert "message" in body["error"]


def test_validation_error_shape(client: TestClient) -> None:
    resp = client.post("/api/auth/register", json={"email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
