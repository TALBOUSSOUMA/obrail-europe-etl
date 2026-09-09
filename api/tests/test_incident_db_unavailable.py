"""
Regression test for the incident documented in
docs/INCIDENT_POSTMORTEM.md.

Before the fix: an unreachable database surfaced as a bare 500 Internal
Server Error (raw Python trace, no actionable message for the client).
After the fix (see the `database_unavailable_handler` handler in
main.py): a clear 503 response.

The outage is simulated by replacing the get_db dependency with a
version that fails immediately, rather than stopping the real database
(which would make this test fragile and dependent on the Docker
environment) - the real scenario itself was reproduced manually (see
the postmortem).
"""

from sqlalchemy.exc import DBAPIError

from database import get_db
from main import app


def _panne_db_simulee():
    raise DBAPIError("SELECT 1", {}, Exception("connexion refusee (simulee)"))
    yield  # pragma: no cover - never reached; keeps the generator shape FastAPI expects


def _avec_db_en_panne(client, path):
    """Run a request with get_db forced to fail, then properly restore
    the dependency (the `client` fixture is shared across tests, so the
    override must never stay active after the test)."""
    app.dependency_overrides[get_db] = _panne_db_simulee
    try:
        return client.get(path)
    finally:
        app.dependency_overrides.pop(get_db, None)


def test_health_returns_503_not_bare_500_when_db_is_down(client):
    resp = _avec_db_en_panne(client, "/health")
    assert resp.status_code == 503
    assert "indisponible" in resp.json()["detail"].lower()


def test_dessertes_returns_503_not_bare_500_when_db_is_down(client):
    resp = _avec_db_en_panne(client, "/dessertes")
    assert resp.status_code == 503


def test_service_recovers_once_db_override_is_removed(client):
    """Verifies the override doesn't "leak" into other tests: once the
    simulated outage is over, the service responds normally again."""
    resp = client.get("/health")
    assert resp.status_code == 200
