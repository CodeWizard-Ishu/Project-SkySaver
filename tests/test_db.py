"""tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.py.

Every test uses a fresh isolated SQLite file via tmp_path + monkeypatch.
Never touches the real flight_prices.db. Covers happy paths, edge cases,
validation errors, concurrency, and cooldown expiry.
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime, timedelta
from typing import Optional

import pytest

import db.queries as Q
from db.init_db import create_tables


# ─── FIXTURES ────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def fresh_db(tmp_path, monkeypatch):
    """Provide an isolated database for every single test."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)

    # Reset module-level connection so each test starts clean
    Q._conn = None
    create_tables()

    yield

    Q.close_connection()
    Q._conn = None


def _insert(
    route: str = "NAG-DEL",
    travel_date: date = date(2026, 12, 15),
    price: int = 4500,
    airline: str = "IndiGo",
    stops: int = 0,
    source: str = "skyscanner",
) -> int:
    """Shortcut to insert one observation with sensible defaults."""
    return Q.insert_price_observation(route, travel_date, price, airline, stops, source)


# ─── TestInsertPriceObservation ───────────────────────────────────────────────

class TestInsertPriceObservation:

    def test_insert_valid_observation(self):
        row_id = _insert()
        assert row_id > 0

    def test_insert_calculates_days_advance(self):
        travel = date(2026, 12, 15)
        _insert(travel_date=travel)
        history = Q.get_price_history("NAG-DEL", travel)
        assert len(history) == 1
        expected_advance = (travel - datetime.now(UTC).date()).days
        assert history[0].days_advance == expected_advance

    def test_insert_invalid_route_format_lowercase(self):
        with pytest.raises(ValueError, match="Invalid route format"):
            Q.insert_price_observation("nag-del", date(2026, 12, 15), 4500, "IndiGo", 0, "skyscanner")

    def test_insert_invalid_route_format_no_hyphen(self):
        with pytest.raises(ValueError, match="Invalid route format"):
            Q.insert_price_observation("NAGDEL", date(2026, 12, 15), 4500, "IndiGo", 0, "skyscanner")

    def test_insert_invalid_source(self):
        with pytest.raises(ValueError, match="Invalid source"):
            Q.insert_price_observation("NAG-DEL", date(2026, 12, 15), 4500, "IndiGo", 0, "kayak")

    def test_insert_negative_price(self):
        with pytest.raises(ValueError, match="price_inr must be > 0"):
            Q.insert_price_observation("NAG-DEL", date(2026, 12, 15), -100, "IndiGo", 0, "skyscanner")

    def test_insert_zero_price(self):
        with pytest.raises(ValueError, match="price_inr must be > 0"):
            Q.insert_price_observation("NAG-DEL", date(2026, 12, 15), 0, "IndiGo", 0, "skyscanner")

    def test_insert_multiple_observations(self):
        travel = date(2026, 12, 15)
        for price in [3000, 3500, 4000, 4500, 5000]:
            _insert(price=price, travel_date=travel)
        history = Q.get_price_history("NAG-DEL", travel)
        assert len(history) == 5

    def test_concurrent_inserts(self):
        """10 threads each insert 5 rows — total must be 50, no corruption."""
        errors: list[Exception] = []
        travel = date(2026, 12, 20)

        def worker():
            try:
                for price in range(1000, 6000, 1000):
                    Q.insert_price_observation(
                        "NAG-DEL", travel, price, "AirIndia", 0, "google_flights"
                    )
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrency errors: {errors}"
        history = Q.get_price_history("NAG-DEL", travel)
        assert len(history) == 50


# ─── TestUpdatePriceStats ─────────────────────────────────────────────────────

class TestUpdatePriceStats:

    def test_stats_with_single_observation(self):
        travel = date(2026, 12, 15)
        _insert(price=5000, travel_date=travel)
        stats = Q.update_price_stats("NAG-DEL", travel)
        assert stats.p10_price == 5000
        assert stats.p25_price == 5000
        assert stats.median_price == 5000
        assert stats.all_time_low == 5000
        assert stats.all_time_high == 5000
        assert stats.observation_count == 1

    def test_stats_with_ten_observations(self):
        travel = date(2026, 12, 15)
        prices = [1000, 2000, 3000, 4000, 5000, 6000, 7000, 8000, 9000, 10000]
        for p in prices:
            _insert(price=p, travel_date=travel)
        stats = Q.update_price_stats("NAG-DEL", travel)
        assert stats.observation_count == 10
        assert stats.all_time_low == 1000
        assert stats.all_time_high == 10000
        # nearest-rank P50 of 10 items: index floor(0.5*10)-1 = 4 → prices[4] = 5000
        assert stats.median_price == 5000

    def test_p10_is_correct(self):
        """Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)."""
        travel = date(2026, 12, 16)
        prices = list(range(100, 2100, 100))  # [100,200,...,2000], n=20
        for p in prices:
            _insert(price=p, travel_date=travel)
        stats = Q.update_price_stats("NAG-DEL", travel)
        # nearest-rank: floor(0.10*20)-1 = 1 → prices[1] = 200
        assert stats.p10_price == 200

    def test_all_time_low_updates_correctly(self):
        travel = date(2026, 12, 15)
        _insert(price=9000, travel_date=travel)
        _insert(price=2000, travel_date=travel)
        stats = Q.update_price_stats("NAG-DEL", travel)
        assert stats.all_time_low == 2000
        assert stats.all_time_high == 9000

    def test_insufficient_data_raises(self):
        with pytest.raises(Q.InsufficientDataError):
            Q.update_price_stats("NAG-DEL", date(2026, 12, 15))

    def test_stats_upsert_not_duplicate(self):
        travel = date(2026, 12, 15)
        _insert(price=4500, travel_date=travel)
        Q.update_price_stats("NAG-DEL", travel)
        Q.update_price_stats("NAG-DEL", travel)
        conn = Q.get_connection()
        count = conn.execute(
            "SELECT COUNT(*) FROM price_stats WHERE route='NAG-DEL' AND travel_date=?",
            (travel.isoformat(),),
        ).fetchone()[0]
        assert count == 1


# ─── TestGetAlertDecision ─────────────────────────────────────────────────────

class TestGetAlertDecision:

    def _seed_stats(
        self,
        travel: date = date(2026, 12, 15),
        prices: Optional[list[int]] = None,
    ) -> None:
        if prices is None:
            prices = list(range(1000, 11000, 500))  # 20 observations, P10 ≈ low prices
        for p in prices:
            _insert(price=p, travel_date=travel)
        Q.update_price_stats("NAG-DEL", travel)

    def test_no_stats_yet(self):
        decision = Q.get_alert_decision("NAG-DEL", date(2026, 12, 15), 3000)
        assert decision.should_alert is False
        assert "No statistics" in decision.reason

    def test_insufficient_observations(self):
        travel = date(2026, 12, 15)
        for p in [3000, 4000, 5000]:
            _insert(price=p, travel_date=travel)
        Q.update_price_stats("NAG-DEL", travel)
        decision = Q.get_alert_decision("NAG-DEL", travel, 3000, min_observations=10)
        assert decision.should_alert is False
        assert "observations" in decision.reason

    def test_price_above_p10(self):
        travel = date(2026, 12, 15)
        self._seed_stats(travel)
        stats = Q.get_price_stats("NAG-DEL", travel)
        above_p10 = stats.p10_price + 500
        decision = Q.get_alert_decision("NAG-DEL", travel, above_p10)
        assert decision.should_alert is False
        assert "above P10" in decision.reason

    def test_alert_triggered_correctly(self):
        travel = date(2026, 12, 15)
        self._seed_stats(travel)
        stats = Q.get_price_stats("NAG-DEL", travel)
        # Use a price at or below P10
        decision = Q.get_alert_decision(
            "NAG-DEL", travel, stats.p10_price, min_observations=5
        )
        assert decision.should_alert is True
        assert "P10" in decision.reason

    def test_cooldown_blocks_second_alert(self):
        travel = date(2026, 12, 15)
        self._seed_stats(travel)
        stats = Q.get_price_stats("NAG-DEL", travel)
        price = stats.p10_price
        Q.log_alert_sent("NAG-DEL", travel, price, "test alert")
        decision = Q.get_alert_decision("NAG-DEL", travel, price, min_observations=5)
        assert decision.should_alert is False
        assert "cooldown" in decision.reason.lower() or "ago" in decision.reason

    def test_cooldown_expires(self, monkeypatch):
        travel = date(2026, 12, 15)
        self._seed_stats(travel)
        stats = Q.get_price_stats("NAG-DEL", travel)
        price = stats.p10_price

        # Manually insert an old alert (25h ago)
        old_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat(timespec="seconds").replace("+00:00", "Z")
        conn = Q.get_connection()
        with Q._write_lock:
            with conn:
                conn.execute(
                    "INSERT INTO alert_log (route, travel_date, price_notified, alert_reason, alerted_at) VALUES (?,?,?,?,?)",
                    ("NAG-DEL", travel.isoformat(), price, "old alert", old_time),
                )

        decision = Q.get_alert_decision("NAG-DEL", travel, price, min_observations=5, cooldown_hours=24)
        assert decision.should_alert is True

    def test_percentile_rank_calculated(self):
        travel = date(2026, 12, 15)
        prices = [1000, 2000, 3000, 4000, 5000]
        for p in prices:
            _insert(price=p, travel_date=travel)
        Q.update_price_stats("NAG-DEL", travel)
        # At price=1000, 4 out of 5 prices are above → rank = 80%
        decision = Q.get_alert_decision("NAG-DEL", travel, 1000, min_observations=3)
        assert decision.percentile_rank is not None
        assert abs(decision.percentile_rank - 80.0) < 1.0

    def test_pct_below_median_negative(self):
        travel = date(2026, 12, 15)
        for p in [2000, 3000, 4000, 5000, 6000]:
            _insert(price=p, travel_date=travel)
        Q.update_price_stats("NAG-DEL", travel)
        # Median is 4000; price 2000 is 50% below
        decision = Q.get_alert_decision("NAG-DEL", travel, 2000, min_observations=3)
        assert decision.pct_below_median is not None
        assert decision.pct_below_median < 0


# ─── TestAlertLog ─────────────────────────────────────────────────────────────

class TestAlertLog:

    def test_log_alert_stores_correctly(self):
        travel = date(2026, 12, 15)
        row_id = Q.log_alert_sent("NAG-DEL", travel, 3500, "Price hit P10")
        assert row_id > 0
        alerts = Q.get_recent_alerts(limit=5)
        assert len(alerts) == 1
        assert alerts[0]["route"] == "NAG-DEL"
        assert alerts[0]["price_notified"] == 3500

    def test_cooldown_check_no_prior_alert(self):
        is_cd, hours = Q.check_alert_cooldown("NAG-DEL", date(2026, 12, 15))
        assert is_cd is False
        assert hours is None

    def test_cooldown_check_active(self):
        travel = date(2026, 12, 15)
        Q.log_alert_sent("NAG-DEL", travel, 3500, "test")
        is_cd, hours = Q.check_alert_cooldown("NAG-DEL", travel, cooldown_hours=24)
        assert is_cd is True
        assert hours is not None
        assert hours < 1.0  # just inserted, less than 1 hour ago

    def test_cooldown_check_expired(self):
        travel = date(2026, 12, 15)
        old_time = (datetime.now(UTC) - timedelta(hours=25)).isoformat(timespec="seconds").replace("+00:00", "Z")
        conn = Q.get_connection()
        with Q._write_lock:
            with conn:
                conn.execute(
                    "INSERT INTO alert_log (route, travel_date, price_notified, alert_reason, alerted_at) VALUES (?,?,?,?,?)",
                    ("NAG-DEL", travel.isoformat(), 3500, "old", old_time),
                )
        is_cd, hours = Q.check_alert_cooldown("NAG-DEL", travel, cooldown_hours=24)
        assert is_cd is False
        assert hours is not None
        assert hours > 24.0


# ─── TestMonitoredRoutes ──────────────────────────────────────────────────────

class TestMonitoredRoutes:

    def test_upsert_new_route(self):
        Q.upsert_monitored_route("NAG-DEL", ["2026-12-15", "2026-12-20"])
        routes = Q.get_all_active_routes()
        assert any(r["route"] == "NAG-DEL" for r in routes)

    def test_upsert_updates_existing(self):
        Q.upsert_monitored_route("NAG-DEL", ["2026-12-15"])
        Q.upsert_monitored_route("NAG-DEL", ["2026-12-15", "2026-12-25"])
        routes = Q.get_all_active_routes()
        nag_del = next(r for r in routes if r["route"] == "NAG-DEL")
        assert "2026-12-25" in nag_del["travel_dates"]
        assert len(nag_del["travel_dates"]) == 2

    def test_invalid_route_format(self):
        with pytest.raises(ValueError, match="Invalid route format"):
            Q.upsert_monitored_route("nag-del", ["2026-12-15"])

    def test_empty_travel_dates(self):
        with pytest.raises(ValueError, match="travel_dates must not be empty"):
            Q.upsert_monitored_route("NAG-DEL", [])

    def test_paused_route_excluded(self):
        Q.upsert_monitored_route("NAG-BOM", ["2026-12-15"], active=False)
        routes = Q.get_all_active_routes()
        assert not any(r["route"] == "NAG-BOM" for r in routes)


# ─── TestGetPriceHistory ──────────────────────────────────────────────────────

class TestGetPriceHistory:

    def test_returns_empty_for_unknown_route(self):
        result = Q.get_price_history("DEL-BOM", date(2026, 12, 15))
        assert result == []

    def test_days_back_filter_works(self):
        travel = date(2026, 12, 15)
        # Insert a recent observation
        _insert(price=4000, travel_date=travel)

        # Manually insert an old observation (100 days ago)
        old_time = (datetime.now(UTC) - timedelta(days=100)).isoformat(timespec="seconds").replace("+00:00", "Z")
        conn = Q.get_connection()
        with Q._write_lock:
            with conn:
                conn.execute(
                    """INSERT INTO flight_prices
                       (observed_at, route, travel_date, price_inr, airline, stops, days_advance, source)
                       VALUES (?,?,?,?,?,?,?,?)""",
                    (old_time, "NAG-DEL", travel.isoformat(), 3000, "IndiGo", 0, 200, "skyscanner"),
                )

        recent = Q.get_price_history("NAG-DEL", travel, days_back=90)
        assert all(obs.price_inr == 4000 for obs in recent)
        assert len(recent) == 1

    def test_source_filter_works(self):
        travel = date(2026, 12, 15)
        _insert(price=4000, travel_date=travel, source="skyscanner")
        _insert(price=4200, travel_date=travel, source="amadeus")
        sky_only = Q.get_price_history("NAG-DEL", travel, source="skyscanner")
        assert len(sky_only) == 1
        assert sky_only[0].source == "skyscanner"

    def test_ordered_by_observed_at_asc(self):
        travel = date(2026, 12, 15)
        for price in [5000, 3000, 4000]:
            _insert(price=price, travel_date=travel)
        history = Q.get_price_history("NAG-DEL", travel)
        timestamps = [obs.observed_at for obs in history]
        assert timestamps == sorted(timestamps)


# ─── TestGetObservationCountByRoute ──────────────────────────────────────────

class TestGetObservationCountByRoute:

    def test_empty_db_returns_empty_dict(self):
        result = Q.get_observation_count_by_route()
        assert result == {}

    def test_counts_correct_per_route(self):
        travel = date(2026, 12, 15)
        for _ in range(3):
            _insert(route="NAG-DEL", travel_date=travel)
        for _ in range(5):
            _insert(route="NAG-BOM", travel_date=travel)
        counts = Q.get_observation_count_by_route()
        assert counts["NAG-DEL"] == 3
        assert counts["NAG-BOM"] == 5

    def test_only_counts_inserted_routes(self):
        travel = date(2026, 12, 15)
        _insert(route="DEL-BOM", travel_date=travel)
        counts = Q.get_observation_count_by_route()
        assert "NAG-DEL" not in counts
        assert counts.get("DEL-BOM") == 1
