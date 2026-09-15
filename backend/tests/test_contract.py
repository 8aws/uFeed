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
}


def test_openapi_exposes_contract(client: TestClient) -> None:
    schema = client.get("/openapi.json").json()
    paths = set(schema["paths"].keys())
    missing = EXPECTED_PATHS - paths
    assert not missing, f"missing contract paths: {sorted(missing)}"


def test_stubs_return_501_with_error_shape(client: TestClient) -> None:
    # folders is still a stub (implemented in WS3) and needs no DB/auth.
    resp = client.get("/api/folders")
    assert resp.status_code == 501
    body = resp.json()
    assert body["error"]["code"] == "not_implemented"


def test_validation_error_shape(client: TestClient) -> None:
    resp = client.post("/api/auth/register", json={"email": "not-an-email"})
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"
