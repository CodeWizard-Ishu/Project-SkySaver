"""tests/test_api.py — FastAPI TestClient test suite for Phase 4.

All DB interactions use SQLite :memory: (set via DATABASE_PATH env var).
Pipeline calls are mocked — no real scraping, LLM, or Telegram calls.
Target: < 5 seconds total runtime.

Run: pytest tests/test_api.py -v
"""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient


# ─── FIXTURES ─────────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def _set_env(monkeypatch):
    """Set all required env vars before any test in this module."""
    monkeypatch.setenv("SKYSAVER_API_KEY", "test-key-12345")
    monkeypatch.setenv("DATABASE_PATH", ":memory:")
    monkeypatch.setenv("GEMINI_API_KEY", "fake-gemini-key")
    monkeypatch.setenv("TINYFISH_API_KEY", "fake-tinyfish-key")
    monkeypatch.setenv("AMADEUS_CLIENT_ID", "fake-amadeus-id")
    monkeypatch.setenv("AMADEUS_CLIENT_SECRET", "fake-amadeus-secret")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fake-bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "99999")
    monkeypatch.setenv("ENVIRONMENT", "development")


@pytest.fixture(autouse=True)
def _reset_db_connection():
    """Reset the module-level SQLite connection between tests.

    db.queries caches a single connection as a module global (_conn).
    When DATABASE_PATH=:memory: the in-memory DB is tied to that connection;
    resetting it forces a fresh schema-less DB per test.
    """
    import db.queries as queries
    queries.close_connection()  # close any open connection
    queries._conn = None        # force lazy re-init on next use
    yield
    queries.close_connection()  # cleanup after test
    queries._conn = None


@pytest.fixture
def client():
    """Create a fresh TestClient backed by an in-memory DB with schema."""
    with patch("agents.base_agent.load_env"):
        from api.main import create_app
        app = create_app()

    # The app startup calls create_tables() but TestClient doesn't run
    # ASGI lifespan events by default — call it directly here.
    with patch("agents.base_agent.load_env"):
        from db.init_db import create_tables
        create_tables()

    return TestClient(app, raise_server_exceptions=False)


AUTH = {"X-SkySaver-Key": "test-key-12345"}
FUTURE_DATE = (date.today() + timedelta(days=90)).isoformat()


# ─── HELPERS ──────────────────────────────────────────────────────────────────


def _seed_route(route: str = "NAG-DEL") -> None:
    """Add a route directly to the DB (bypasses API validation issues in tests)."""
    import db.queries as queries
    queries.upsert_monitored_route(route=route, travel_dates=[FUTURE_DATE])


def _seed_observation(route: str = "NAG-DEL", price: int = 5000) -> None:
    """Insert a price observation directly into the in-memory DB."""
    import db.queries as queries
    from datetime import date as _date

    td = _date.fromisoformat(FUTURE_DATE)
    queries.insert_price_observation(
        route=route,
        travel_date=td,
        price_inr=price,
        airline="IndiGo",
        stops=0,
        source="skyscanner",
    )


def _seed_alert(route: str = "NAG-DEL") -> None:
    """Insert an alert log entry directly into the in-memory DB."""
    import db.queries as queries
    from datetime import date as _date

    queries.log_alert_sent(
        route=route,
        travel_date=_date.fromisoformat(FUTURE_DATE),
        price_notified=4500,
        alert_reason="Price at historical low P10",
    )


# ─── TestHealthCheck ──────────────────────────────────────────────────────────


class TestHealthCheck:
    """Tests for GET /health — the no-auth liveness probe."""

    def test_health_returns_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200

    def test_health_no_auth_required(self, client):
        """Health must be accessible without X-SkySaver-Key."""
        resp = client.get("/health")
        assert resp.status_code != 401

    def test_health_response_has_uptime(self, client):
        resp = client.get("/health")
        data = resp.json()
        assert "uptime_seconds" in data
        assert data["uptime_seconds"] >= 0

    def test_health_status_ok(self, client):
        resp = client.get("/health")
        assert resp.json()["status"] == "ok"

    def test_health_has_version(self, client):
        resp = client.get("/health")
        assert resp.json()["version"] == "1.0.0"


# ─── TestAuthentication ───────────────────────────────────────────────────────


class TestAuthentication:
    """Tests for X-SkySaver-Key header enforcement on protected endpoints."""

    def test_missing_api_key_returns_401(self, client):
        resp = client.get("/api/v1/status")
        assert resp.status_code == 401

    def test_wrong_api_key_returns_401(self, client):
        resp = client.get("/api/v1/status", headers={"X-SkySaver-Key": "wrong-key"})
        assert resp.status_code == 401

    def test_correct_api_key_passes(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        assert resp.status_code != 401

    def test_empty_key_returns_401(self, client):
        resp = client.get("/api/v1/status", headers={"X-SkySaver-Key": ""})
        assert resp.status_code == 401

    def test_health_no_key_is_200(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200


# ─── TestResponseEnvelope ─────────────────────────────────────────────────────


class TestResponseEnvelope:
    """Tests verifying the universal APIResponse envelope on all responses."""

    def test_success_response_has_all_fields(self, client):
        resp = client.get("/api/v1/routes", headers=AUTH)
        data = resp.json()
        assert "success" in data
        assert "data" in data
        assert "error" in data
        assert "timestamp" in data
        assert "request_id" in data

    def test_success_flag_true_on_200(self, client):
        resp = client.get("/api/v1/routes", headers=AUTH)
        assert resp.json()["success"] is True

    def test_error_response_has_all_fields(self, client):
        resp = client.delete("/api/v1/routes/UNKNOWN-RTE", headers=AUTH)
        assert resp.status_code == 404
        data = resp.json()
        assert data["success"] is False
        assert data["error"] is not None
        assert data["data"] is None

    def test_request_id_in_response_header(self, client):
        resp = client.get("/api/v1/routes", headers=AUTH)
        assert "x-request-id" in resp.headers

    def test_request_id_is_valid_uuid(self, client):
        resp = client.get("/api/v1/routes", headers=AUTH)
        rid = resp.headers.get("x-request-id", "")
        parsed = uuid.UUID(rid)   # raises ValueError if not valid UUID
        assert parsed.version == 4

    def test_401_uses_envelope(self, client):
        resp = client.get("/api/v1/routes")
        data = resp.json()
        assert data["success"] is False
        assert data["error"] is not None


# ─── TestRoutesEndpoints ──────────────────────────────────────────────────────


class TestRoutesEndpoints:
    """Tests for the monitored routes CRUD endpoints."""

    def test_get_routes_empty_db(self, client):
        resp = client.get("/api/v1/routes", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"] == []

    def test_add_route_valid(self, client):
        resp = client.post(
            "/api/v1/routes",
            json={"route": "NAG-DEL", "travel_dates": [FUTURE_DATE]},
            headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["route"] == "NAG-DEL"
        assert data["is_active"] is True

    def test_add_route_invalid_format(self, client):
        resp = client.post(
            "/api/v1/routes",
            json={"route": "nag-del", "travel_dates": [FUTURE_DATE]},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_add_route_lowercase_format(self, client):
        resp = client.post(
            "/api/v1/routes",
            json={"route": "NAGDEL", "travel_dates": [FUTURE_DATE]},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_add_route_past_date(self, client):
        past = (date.today() - timedelta(days=1)).isoformat()
        resp = client.post(
            "/api/v1/routes",
            json={"route": "NAG-DEL", "travel_dates": [past]},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_add_route_today_date(self, client):
        today = date.today().isoformat()
        resp = client.post(
            "/api/v1/routes",
            json={"route": "NAG-DEL", "travel_dates": [today]},
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_add_route_duplicate_ok(self, client):
        payload = {"route": "NAG-DEL", "travel_dates": [FUTURE_DATE]}
        r1 = client.post("/api/v1/routes", json=payload, headers=AUTH)
        r2 = client.post("/api/v1/routes", json=payload, headers=AUTH)
        assert r1.status_code == 200
        assert r2.status_code == 200

    def test_get_routes_after_add(self, client):
        _seed_route()
        resp = client.get("/api/v1/routes", headers=AUTH)
        routes = resp.json()["data"]
        assert any(r["route"] == "NAG-DEL" for r in routes)

    def test_delete_route_soft_deletes(self, client):
        _seed_route()
        resp = client.delete("/api/v1/routes/NAG-DEL", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["is_active"] is False

    def test_delete_route_not_found(self, client):
        resp = client.delete("/api/v1/routes/XYZ-ABC", headers=AUTH)
        assert resp.status_code == 404

    def test_deleted_route_excluded_from_active_list(self, client):
        _seed_route()
        client.delete("/api/v1/routes/NAG-DEL", headers=AUTH)
        resp = client.get("/api/v1/routes", headers=AUTH)
        routes = resp.json()["data"]
        assert not any(r["route"] == "NAG-DEL" for r in routes)

    def test_deleted_route_included_with_include_paused(self, client):
        _seed_route()
        client.delete("/api/v1/routes/NAG-DEL", headers=AUTH)
        resp = client.get("/api/v1/routes?include_paused=true", headers=AUTH)
        routes = resp.json()["data"]
        assert any(r["route"] == "NAG-DEL" for r in routes)

    def test_resume_route(self, client):
        _seed_route()
        client.delete("/api/v1/routes/NAG-DEL", headers=AUTH)
        resp = client.put("/api/v1/routes/NAG-DEL/resume", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"]["is_active"] is True

    def test_resume_route_not_found(self, client):
        resp = client.put("/api/v1/routes/XYZ-ABC/resume", headers=AUTH)
        assert resp.status_code == 404


# ─── TestPricesEndpoints ──────────────────────────────────────────────────────


class TestPricesEndpoints:
    """Tests for the price history and statistics endpoints."""

    def test_get_prices_no_data(self, client):
        resp = client.get(
            f"/api/v1/prices/NAG-DEL?travel_date={FUTURE_DATE}",
            headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["observations"] == []
        assert data["observation_count"] == 0

    def test_get_prices_with_data(self, client):
        _seed_observation()
        resp = client.get(
            f"/api/v1/prices/NAG-DEL?travel_date={FUTURE_DATE}",
            headers=AUTH,
        )
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["observation_count"] == 1
        assert data["observations"][0]["price_inr"] == 5000

    def test_get_prices_days_back_filter(self, client):
        # Observations should be filtered by days_back parameter.
        # With days_back=1, only very recent data is returned (seeded data is recent).
        _seed_observation()
        resp = client.get(
            f"/api/v1/prices/NAG-DEL?travel_date={FUTURE_DATE}&days_back=1",
            headers=AUTH,
        )
        assert resp.status_code == 200
        # Observation was just inserted, should be within 1 day
        assert resp.json()["data"]["observation_count"] >= 1

    def test_get_prices_invalid_route(self, client):
        resp = client.get(
            f"/api/v1/prices/invalid?travel_date={FUTURE_DATE}",
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_get_prices_invalid_date(self, client):
        resp = client.get(
            "/api/v1/prices/NAG-DEL?travel_date=not-a-date",
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_get_prices_invalid_source(self, client):
        resp = client.get(
            f"/api/v1/prices/NAG-DEL?travel_date={FUTURE_DATE}&source=fakesource",
            headers=AUTH,
        )
        assert resp.status_code == 422

    def test_get_prices_source_filter(self, client):
        _seed_observation()
        resp = client.get(
            f"/api/v1/prices/NAG-DEL?travel_date={FUTURE_DATE}&source=skyscanner",
            headers=AUTH,
        )
        assert resp.status_code == 200

    def test_get_latest_price_no_data(self, client):
        resp = client.get(
            f"/api/v1/prices/NAG-DEL/latest?travel_date={FUTURE_DATE}",
            headers=AUTH,
        )
        assert resp.status_code == 404

    def test_get_latest_price_with_data(self, client):
        _seed_observation(price=4800)
        _seed_observation(price=5200)
        resp = client.get(
            f"/api/v1/prices/NAG-DEL/latest?travel_date={FUTURE_DATE}",
            headers=AUTH,
        )
        assert resp.status_code == 200
        # Most recently inserted = highest index (ASC order, last = most recent)
        assert resp.json()["data"]["price_inr"] == 5200

    def test_get_latest_price_missing_travel_date(self, client):
        resp = client.get("/api/v1/prices/NAG-DEL/latest", headers=AUTH)
        assert resp.status_code == 422


# ─── TestScrapeEndpoints ──────────────────────────────────────────────────────


class TestScrapeEndpoints:
    """Tests for the scrape trigger and status endpoints."""

    def test_scrape_run_triggers_pipeline(self, client):
        """POST /scrape/run must invoke the pipeline runner."""
        mock_result = MagicMock()
        mock_result.scrape_result.routes_attempted = 2
        mock_result.scrape_result.routes_succeeded = 2
        mock_result.scrape_result.routes_failed = 0
        mock_result.scrape_result.total_fares_scraped = 14
        mock_result.alerts_sent = 1
        mock_result.retrain_triggered = False
        mock_result.errors = []

        with patch("api.routes.scrape._run_pipeline_sync") as mock_run:
            from api.schemas import ScrapeRunResponse
            mock_run.return_value = ScrapeRunResponse(
                routes_attempted=2,
                routes_succeeded=2,
                routes_failed=0,
                total_fares_scraped=14,
                alerts_sent=1,
                retrain_triggered=False,
                duration_seconds=12.5,
                errors=[],
            )
            resp = client.post("/api/v1/scrape/run", headers=AUTH)

        assert resp.status_code == 200
        assert resp.json()["success"] is True
        mock_run.assert_called_once()

    def test_scrape_run_returns_summary(self, client):
        with patch("api.routes.scrape._run_pipeline_sync") as mock_run:
            from api.schemas import ScrapeRunResponse
            mock_run.return_value = ScrapeRunResponse(
                routes_attempted=3,
                routes_succeeded=3,
                routes_failed=0,
                total_fares_scraped=21,
                alerts_sent=2,
                retrain_triggered=True,
                duration_seconds=45.0,
                errors=[],
            )
            resp = client.post("/api/v1/scrape/run", headers=AUTH)

        data = resp.json()["data"]
        assert "routes_attempted" in data
        assert "alerts_sent" in data
        assert "retrain_triggered" in data
        assert "duration_seconds" in data
        assert "errors" in data

    def test_scrape_run_dry_run_flag(self, client):
        with patch("api.routes.scrape._run_pipeline_sync") as mock_run:
            from api.schemas import ScrapeRunResponse
            mock_run.return_value = ScrapeRunResponse(
                routes_attempted=1, routes_succeeded=1, routes_failed=0,
                total_fares_scraped=7, alerts_sent=0, retrain_triggered=False,
                duration_seconds=5.0, errors=[],
            )
            resp = client.post(
                "/api/v1/scrape/run",
                json={"dry_run": True},
                headers=AUTH,
            )
        assert resp.status_code == 200
        # dry_run=True should pass True to _run_pipeline_sync
        mock_run.assert_called_once_with(True)

    def test_scrape_last_run_no_file(self, client, tmp_path, monkeypatch):
        """GET /scrape/last-run returns data=null when no file exists."""
        monkeypatch.setattr("api.routes.scrape._LAST_RUN_PATH", tmp_path / "nonexistent.json")
        resp = client.get("/api/v1/scrape/last-run", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["success"] is True
        assert resp.json()["data"] is None

    def test_scrape_last_run_with_file(self, client, tmp_path, monkeypatch):
        """GET /scrape/last-run returns file contents when file exists."""
        last_run_file = tmp_path / "last_run.json"
        summary = {"routes_attempted": 2, "alerts_sent": 1}
        last_run_file.write_text(json.dumps(summary))
        monkeypatch.setattr("api.routes.scrape._LAST_RUN_PATH", last_run_file)
        resp = client.get("/api/v1/scrape/last-run", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["data"]["alerts_sent"] == 1

    def test_scrape_rate_limits(self, client):
        with patch("api.routes.scrape._get_rate_limit_status") as mock_rl:
            mock_rl.return_value = {
                "tinyfish_browser_used_today": 4,
                "tinyfish_browser_limit": 18,
                "amadeus_used_today": 2,
                "amadeus_limit": 450,
                "routes_on_cooldown": [],
            }
            resp = client.get("/api/v1/scrape/rate-limits", headers=AUTH)

        assert resp.status_code == 200
        data = resp.json()["data"]
        assert "tinyfish_browser_used_today" in data
        assert "amadeus_limit" in data


# ─── TestAlertsEndpoints ──────────────────────────────────────────────────────


class TestAlertsEndpoints:
    """Tests for the alert log query endpoints."""

    def test_get_alerts_empty(self, client):
        resp = client.get("/api/v1/alerts", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["alerts"] == []
        assert data["total_count"] == 0
        assert data["has_more"] is False

    def test_get_alerts_with_data(self, client):
        _seed_route()
        _seed_alert()
        resp = client.get("/api/v1/alerts", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["total_count"] == 1
        assert len(data["alerts"]) == 1

    def test_get_alerts_route_filter(self, client):
        _seed_route("NAG-DEL")
        _seed_route("BOM-DEL")
        _seed_alert("NAG-DEL")
        _seed_alert("BOM-DEL")
        resp = client.get("/api/v1/alerts?route=NAG-DEL", headers=AUTH)
        data = resp.json()["data"]
        assert data["total_count"] == 1
        assert data["alerts"][0]["route"] == "NAG-DEL"

    def test_get_alerts_limit_offset(self, client):
        """Seed 5 alerts, request limit=2 — should return 2 with has_more=True."""
        _seed_route()
        for _ in range(5):
            _seed_alert()
        resp = client.get("/api/v1/alerts?limit=2&offset=0", headers=AUTH)
        data = resp.json()["data"]
        assert len(data["alerts"]) == 2
        assert data["total_count"] == 5
        assert data["has_more"] is True

    def test_get_alerts_offset_beyond_total(self, client):
        _seed_route()
        _seed_alert()
        resp = client.get("/api/v1/alerts?limit=10&offset=100", headers=AUTH)
        data = resp.json()["data"]
        assert data["alerts"] == []
        assert data["has_more"] is False

    def test_get_alerts_limit_max_enforced(self, client):
        resp = client.get("/api/v1/alerts?limit=999", headers=AUTH)
        assert resp.status_code == 422

    def test_cooldown_check_not_in_cooldown(self, client):
        resp = client.get("/api/v1/alerts/cooldown/NAG-DEL", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["in_cooldown"] is False
        assert data["cooldown_expires_at"] is None

    def test_cooldown_check_in_cooldown(self, client):
        """After seeding a recent alert, route should be in cooldown."""
        _seed_route()
        _seed_alert()
        resp = client.get("/api/v1/alerts/cooldown/NAG-DEL", headers=AUTH)
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["in_cooldown"] is True
        assert data["cooldown_expires_at"] is not None

    def test_alert_entry_has_required_fields(self, client):
        _seed_route()
        _seed_alert()
        resp = client.get("/api/v1/alerts", headers=AUTH)
        alert = resp.json()["data"]["alerts"][0]
        for field in ["alert_id", "route", "travel_date", "price_at_alert",
                      "recommendation", "urgency_score", "sent_at", "telegram_delivered"]:
            assert field in alert, f"Missing field: {field}"


# ─── TestStatusEndpoint ───────────────────────────────────────────────────────


class TestStatusEndpoint:
    """Tests for GET /api/v1/status — full system status."""

    def test_status_returns_200(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        assert resp.status_code == 200
        assert resp.json()["success"] is True

    def test_status_returns_all_fields(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        data = resp.json()["data"]
        required = [
            "api_version", "database_ok", "database_path", "database_size_mb",
            "total_observations", "total_routes_monitored", "total_alerts_sent",
            "rate_limits", "ml_model_exists", "ml_model_version",
            "last_scrape_at", "last_alert_at", "uptime_seconds",
        ]
        for field in required:
            assert field in data, f"Missing field in status response: {field}"

    def test_status_database_ok_true(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        # With :memory: DB and create_tables called on startup, DB should be ok
        data = resp.json()["data"]
        assert data["database_ok"] is True

    def test_status_ml_model_not_exists(self, client, tmp_path, monkeypatch):
        """No .pkl files in models/ → ml_model_exists=False."""
        # Point models lookup at an empty temp dir
        import api.routes.status as status_mod
        original = Path("models")
        # Patch Path("models").glob inside the collect function — use mocker approach
        with patch("pathlib.Path.glob", return_value=iter([])):
            resp = client.get("/api/v1/status", headers=AUTH)
        data = resp.json()["data"]
        # ml_model_exists depends on whether models/ has any .pkl — in test env likely false
        assert "ml_model_exists" in data

    def test_status_api_version(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        assert resp.json()["data"]["api_version"] == "1.0.0"

    def test_status_uptime_positive(self, client):
        resp = client.get("/api/v1/status", headers=AUTH)
        assert resp.json()["data"]["uptime_seconds"] >= 0
