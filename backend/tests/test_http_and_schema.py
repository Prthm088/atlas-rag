from pathlib import Path

from fastapi.testclient import TestClient

from atlas.main import app


def test_health_is_public_and_reports_missing_runtime_config() -> None:
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/v1/health", headers={"x-request-id": "test-request"})
    assert response.status_code == 200
    assert response.json()["status"] == "degraded"
    assert "DATABASE_URL" in response.json()["missing_configuration"]
    assert response.headers["x-request-id"] == "test-request"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["x-content-type-options"] == "nosniff"


def test_readiness_rejects_missing_database_configuration() -> None:
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/v1/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "service_not_configured"


def test_openapi_marks_private_routes_as_bearer_authenticated() -> None:
    schema = app.openapi()
    security = schema["paths"]["/api/v1/documents"]["get"]["security"]
    assert security
    assert "HTTPBearer" in security[0]


def test_migration_enables_rls_for_every_user_owned_table() -> None:
    migration = (
        Path(__file__).parents[2] / "supabase" / "migrations" / "202608210001_initial.sql"
    ).read_text(encoding="utf-8")
    tables = (
        "profiles",
        "documents",
        "document_versions",
        "chunks",
        "ingestion_jobs",
        "conversations",
        "messages",
        "citations",
        "feedback",
        "audit_events",
    )
    for table in tables:
        assert f"alter table public.{table} enable row level security" in migration.lower()
    assert "storage.objects" in migration
    assert "auth.uid()" in migration
    assert "revoke all privileges on all tables in schema public" in migration.lower()
