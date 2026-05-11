"""tests/test_scraper.py â€” Comprehensive pytest suite for Phase 2 scraping layer.

All external APIs (TinyFish, SkyScrapper) are fully mocked â€” zero real API calls.
Uses isolated SQLite DB via tmp_path + monkeypatch (same pattern as test_db.py).
"""

from __future__ import annotations

import json
import threading
from datetime import UTC, date, datetime, timedelta
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import db.queries as Q
from db.init_db import create_tables
from agents.rate_limiter import RateLimiter
from agents.scraper_agent import (
    AIRLINE_NORMALISATION_MAP,
    SkyScrappperClient,
    SkyScrapprrAPIError,
    PriceParseError,
    RouteScapeResult,
    RouteScraperAgent,
    ScrapedFare,
    ScraperOrchestrator,
    ScrapeRunResult,
    TinyFishClient,
    TinyFishInvalidResponseError,
    TinyFishRateLimitError,
    _build_skyscanner_goal,
    _normalise_airline,
    _parse_price_inr,
    _parse_tinyfish_response,
    _validate_route,
    _validate_travel_date,
)

# â”€â”€â”€ CONSTANTS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

_FUTURE_DATE = date.today() + timedelta(days=60)
_ROUTE = "NAG-DEL"

_VALID_TF_JSON = json.dumps([
    {"price_inr": 3240, "airline": "IndiGo", "stops": 0, "departure_time": "06:30"},
    {"price_inr": 3680, "airline": "Air India", "stops": 1, "departure_time": "09:15"},
    {"price_inr": 4100, "airline": "SpiceJet", "stops": 0, "departure_time": "14:00"},
])

_VALID_SKYSCRAPPER_ITINERARY = {
    "price": {"raw": 3240},
    "legs": [{
        "carriers": {"marketing": [{"name": "IndiGo"}]},
        "stopCount": 0,
        "departure": "06:30",
    }],
}


# â”€â”€â”€ DB FIXTURE â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.fixture(autouse=True)
def fresh_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    """Isolated SQLite DB per test â€” never touches the real flight_prices.db."""
    db_path = str(tmp_path / "test_scraper.db")
    monkeypatch.setenv("DATABASE_PATH", db_path)
    Q._conn = None
    create_tables()
    yield
    Q.close_connection()
    Q._conn = None


@pytest.fixture()
def tmp_state(tmp_path: Path) -> Path:
    """Return a temporary path for the rate limiter state file."""
    return tmp_path / "rate_limiter_state.json"


# â”€â”€â”€ TINYFISH MOCK FIXTURES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.fixture()
def mock_tinyfish_success() -> MagicMock:
    """TinyFishClient that returns 3 valid fares on browser and fetch calls."""
    mock = MagicMock(spec=TinyFishClient)
    mock.call_browser.return_value = _VALID_TF_JSON
    mock.call_fetch.return_value = _VALID_TF_JSON
    return mock


@pytest.fixture()
def mock_tinyfish_rate_limited() -> MagicMock:
    """TinyFishClient that raises TinyFishRateLimitError on first call."""
    mock = MagicMock(spec=TinyFishClient)
    mock.call_browser.side_effect = [
        TinyFishRateLimitError("429"),
        _VALID_TF_JSON,
    ]
    mock.call_fetch.return_value = _VALID_TF_JSON
    return mock


@pytest.fixture()
def mock_tinyfish_always_fails() -> MagicMock:
    """TinyFishClient that always raises TinyFishRateLimitError."""
    mock = MagicMock(spec=TinyFishClient)
    mock.call_browser.side_effect = TinyFishRateLimitError("429")
    mock.call_fetch.side_effect = TinyFishRateLimitError("429")
    return mock


# â”€â”€â”€ SKY SCRAPPER MOCK FIXTURES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.fixture()
def mock_skyscrapper_success() -> MagicMock:
    """SkyScrappperClient that returns 3 valid ScrapedFare objects."""
    mock = MagicMock(spec=SkyScrappperClient)
    mock.fetch_fares.return_value = [
        ScrapedFare(
            route=_ROUTE,
            travel_date=_FUTURE_DATE,
            price_inr=3240,
            airline="IndiGo",
            stops=0,
            source="skyscrapper",
            raw_price_str="3240",
            scraped_at=datetime.now(UTC),
        ),
        ScrapedFare(
            route=_ROUTE,
            travel_date=_FUTURE_DATE,
            price_inr=3680,
            airline="Air India",
            stops=1,
            source="skyscrapper",
            raw_price_str="3680",
            scraped_at=datetime.now(UTC),
        ),
        ScrapedFare(
            route=_ROUTE,
            travel_date=_FUTURE_DATE,
            price_inr=4100,
            airline="SpiceJet",
            stops=0,
            source="skyscrapper",
            raw_price_str="4100",
            scraped_at=datetime.now(UTC),
        ),
    ]
    return mock


@pytest.fixture()
def mock_skyscrapper_always_fails() -> MagicMock:
    """SkyScrappperClient that raises SkyScrapprrAPIError on every call."""
    mock = MagicMock(spec=SkyScrappperClient)
    mock.fetch_fares.side_effect = SkyScrapprrAPIError("500")
    return mock


# â”€â”€â”€ RATE LIMITER MOCK FIXTURES â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


@pytest.fixture()
def mock_rate_limiter_all_ok() -> MagicMock:
    """RateLimiter where all can_use_* return True."""
    mock = MagicMock(spec=RateLimiter)
    mock.can_scrape_route.return_value = True
    mock.can_use_tinyfish_browser.return_value = True
    mock.can_use_tinyfish_fetch.return_value = True
    mock.can_use_skyscrapper.return_value = True
    return mock


@pytest.fixture()
def mock_rate_limiter_tinyfish_exhausted() -> MagicMock:
    """RateLimiter where TinyFish is exhausted, Sky Scrapper still available."""
    mock = MagicMock(spec=RateLimiter)
    mock.can_scrape_route.return_value = True
    mock.can_use_tinyfish_browser.return_value = False
    mock.can_use_tinyfish_fetch.return_value = False
    mock.can_use_skyscrapper.return_value = True
    return mock


# â”€â”€â”€ TestParsePriceInr â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestParsePriceInr:

    def test_rupee_symbol_with_commas(self) -> None:
        assert _parse_price_inr("â‚¹3,240") == 3240

    def test_inr_prefix(self) -> None:
        assert _parse_price_inr("INR 3,240") == 3240

    def test_rs_prefix(self) -> None:
        assert _parse_price_inr("Rs. 3240") == 3240

    def test_plain_integer(self) -> None:
        assert _parse_price_inr("3240") == 3240

    def test_decimal_truncated(self) -> None:
        assert _parse_price_inr("3240.00") == 3240

    def test_usd_conversion(self) -> None:
        result = _parse_price_inr("USD 42")
        assert result == 42 * 83

    def test_empty_string_raises(self) -> None:
        with pytest.raises(PriceParseError, match="Empty"):
            _parse_price_inr("")

    def test_na_raises(self) -> None:
        with pytest.raises(PriceParseError):
            _parse_price_inr("N/A")

    def test_null_string_raises(self) -> None:
        with pytest.raises(PriceParseError):
            _parse_price_inr("null")

    def test_very_large_price_lakh_format(self) -> None:
        assert _parse_price_inr("â‚¹1,20,000") == 120000

    def test_whitespace_only_raises(self) -> None:
        with pytest.raises(PriceParseError):
            _parse_price_inr("   ")


# â”€â”€â”€ TestNormaliseAirline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestNormaliseAirline:

    def test_indigo_lowercase(self) -> None:
        assert _normalise_airline("indigo") == "IndiGo"

    def test_indigo_iata_code(self) -> None:
        assert _normalise_airline("6e") == "IndiGo"

    def test_indigo_full_name(self) -> None:
        assert _normalise_airline("IndiGo Airlines") == "IndiGo"

    def test_air_india_variants(self) -> None:
        assert _normalise_airline("air india") == "Air India"
        assert _normalise_airline("AI") == "Air India"
        assert _normalise_airline("Air India Limited") == "Air India"

    def test_unknown_airline_titlecased(self) -> None:
        result = _normalise_airline("xyzmystery air")
        assert result == "Xyzmystery Air"

    def test_iata_code_uppercase_lookup(self) -> None:
        # IATA codes in the map are lowercase; input "6E" should normalise
        assert _normalise_airline("6E") == "IndiGo"

    def test_empty_string_raises(self) -> None:
        with pytest.raises(ValueError):
            _normalise_airline("")

    def test_spicejet_variants(self) -> None:
        assert _normalise_airline("spicejet") == "SpiceJet"
        assert _normalise_airline("sg") == "SpiceJet"
        assert _normalise_airline("Spice Jet") == "SpiceJet"

    def test_akasa_variants(self) -> None:
        assert _normalise_airline("akasa") == "Akasa Air"
        assert _normalise_airline("QP") == "Akasa Air"


# â”€â”€â”€ TestParseTinyFishResponse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestParseTinyFishResponse:

    def test_clean_json_array(self) -> None:
        fares = _parse_tinyfish_response(_VALID_TF_JSON, _ROUTE, _FUTURE_DATE, "skyscanner")
        assert len(fares) == 3
        assert fares[0].price_inr == 3240
        assert fares[0].airline == "IndiGo"

    def test_markdown_code_fence_stripped(self) -> None:
        wrapped = f"```json\n{_VALID_TF_JSON}\n```"
        fares = _parse_tinyfish_response(wrapped, _ROUTE, _FUTURE_DATE, "skyscanner")
        assert len(fares) == 3

    def test_partial_json_after_text(self) -> None:
        with_preamble = f"Here are results:\n{_VALID_TF_JSON}"
        fares = _parse_tinyfish_response(with_preamble, _ROUTE, _FUTURE_DATE, "skyscanner")
        assert len(fares) == 3

    def test_empty_array_returns_empty(self) -> None:
        fares = _parse_tinyfish_response("[]", _ROUTE, _FUTURE_DATE, "skyscanner")
        assert fares == []

    def test_invalid_json_raises(self) -> None:
        with pytest.raises(TinyFishInvalidResponseError):
            _parse_tinyfish_response("{not json}", _ROUTE, _FUTURE_DATE, "skyscanner")

    def test_missing_price_key_skips_fare(self) -> None:
        data = json.dumps([
            {"airline": "IndiGo", "stops": 0},
            {"price_inr": 4000, "airline": "SpiceJet", "stops": 0},
        ])
        fares = _parse_tinyfish_response(data, _ROUTE, _FUTURE_DATE, "skyscanner")
        assert len(fares) == 1
        assert fares[0].price_inr == 4000

    def test_stops_defaults_to_zero(self) -> None:
        data = json.dumps([{"price_inr": 3000, "airline": "IndiGo"}])
        fares = _parse_tinyfish_response(data, _ROUTE, _FUTURE_DATE, "skyscanner")
        assert fares[0].stops == 0

    def test_all_fares_invalid_raises(self) -> None:
        data = json.dumps([
            {"airline": "IndiGo"},
            {"airline": "SpiceJet"},
        ])
        with pytest.raises(TinyFishInvalidResponseError):
            _parse_tinyfish_response(data, _ROUTE, _FUTURE_DATE, "skyscanner")


# â”€â”€â”€ TestValidateRoute â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestValidateRoute:

    def test_valid_route(self) -> None:
        origin, dest = _validate_route("NAG-DEL")
        assert origin == "NAG"
        assert dest == "DEL"

    def test_lowercase_raises(self) -> None:
        with pytest.raises(ValueError, match="Invalid route format"):
            _validate_route("nag-del")

    def test_full_name_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_route("NAGPUR-DELHI")

    def test_no_hyphen_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_route("NAGDEL")

    def test_extra_hyphen_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_route("NAG-DE-L")


# â”€â”€â”€ TestValidateTravelDate â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestValidateTravelDate:

    def test_future_date_valid(self) -> None:
        _validate_travel_date(date.today() + timedelta(days=1))

    def test_today_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_travel_date(date.today())

    def test_past_date_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_travel_date(date.today() - timedelta(days=1))

    def test_over_365_days_raises(self) -> None:
        with pytest.raises(ValueError):
            _validate_travel_date(date.today() + timedelta(days=366))

    def test_exactly_365_days_valid(self) -> None:
        _validate_travel_date(date.today() + timedelta(days=365))


# â”€â”€â”€ TestRouteScraperAgent â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


def _make_agent(
    rl: Any,
    tf: Any = None,
    am: Any = None,
    dedup: set | None = None,
) -> RouteScraperAgent:
    """Helper: build a RouteScraperAgent with injected mocks."""
    return RouteScraperAgent(
        rate_limiter=rl,
        tinyfish_client=tf or MagicMock(spec=TinyFishClient),
        amadeus_client=am or MagicMock(spec=SkyScrappperClient),
        dedup_set=dedup if dedup is not None else set(),
    )


class TestRouteScraperAgent:

    def test_tinyfish_browser_success(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        agent = _make_agent(
            mock_rate_limiter_all_ok, mock_tinyfish_success, mock_skyscrapper_success
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result.error is None
        assert result.fares_found == 3
        assert result.fares_stored == 3
        assert result.source_used == "skyscanner"
        assert result.fallback_used is False
        # Verify DB was written
        obs = Q.get_price_history(_ROUTE, _FUTURE_DATE)
        assert len(obs) == 3

    def test_tinyfish_browser_falls_to_fetch(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        mock_rate_limiter_all_ok.can_use_tinyfish_browser.return_value = True
        # Browser call fails, fetch succeeds
        mock_tinyfish_success.call_browser.side_effect = TinyFishRateLimitError("429")
        agent = _make_agent(
            mock_rate_limiter_all_ok, mock_tinyfish_success, mock_skyscrapper_success
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result.error is None
        assert result.source_used == "google_flights"
        assert result.fares_stored == 3

    def test_tinyfish_all_fail_skyscrapper(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_always_fails: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        agent = _make_agent(
            mock_rate_limiter_all_ok, mock_tinyfish_always_fails, mock_skyscrapper_success
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result.error is None
        assert result.source_used == "skyscrapper"
        assert result.fallback_used is True
        assert result.fares_stored == 3

    def test_all_sources_fail_returns_error(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_always_fails: MagicMock,
        mock_skyscrapper_always_fails: MagicMock,
    ) -> None:
        agent = _make_agent(
            mock_rate_limiter_all_ok, mock_tinyfish_always_fails, mock_skyscrapper_always_fails
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result.error is not None
        assert result.fares_found == 0
        assert result.fares_stored == 0

    def test_fallback_flag_set(
        self,
        mock_rate_limiter_tinyfish_exhausted: MagicMock,
        mock_tinyfish_always_fails: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        agent = _make_agent(
            mock_rate_limiter_tinyfish_exhausted,
            mock_tinyfish_always_fails,
            mock_skyscrapper_success,
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result.fallback_used is True

    def test_past_fares_filtered(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        past_date = date.today() - timedelta(days=1)
        # TinyFish returns fare with past travel_date
        past_fare_json = json.dumps([
            {"price_inr": 3000, "airline": "IndiGo", "stops": 0},
        ])
        tf_mock = MagicMock(spec=TinyFishClient)
        tf_mock.call_browser.return_value = past_fare_json

        agent = _make_agent(mock_rate_limiter_all_ok, tf_mock, mock_skyscrapper_success)
        # Scrape for the past date; validation will fail in _validate_travel_date
        result = agent.scrape_route(_ROUTE, past_date)
        assert result.error is not None  # travel date validation catches it

    def test_duplicate_fare_skipped(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        shared_dedup: set[str] = set()
        agent = _make_agent(
            mock_rate_limiter_all_ok,
            mock_tinyfish_success,
            mock_skyscrapper_success,
            dedup=shared_dedup,
        )
        # First scrape â€” 3 fares stored
        result1 = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result1.fares_stored == 3

        # Second scrape same fares â€” all duplicates, nothing stored
        result2 = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        assert result2.fares_stored == 0

    def test_rate_limit_triggers_skyscrapper(
        self,
        mock_rate_limiter_tinyfish_exhausted: MagicMock,
        mock_tinyfish_always_fails: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        agent = _make_agent(
            mock_rate_limiter_tinyfish_exhausted,
            mock_tinyfish_always_fails,
            mock_skyscrapper_success,
        )
        result = agent.scrape_route(_ROUTE, _FUTURE_DATE)
        # TinyFish was skipped (limit), Sky Scrapper should have been called
        mock_skyscrapper_success.fetch_fares.assert_called_once()
        assert result.source_used == "skyscrapper"


# â”€â”€â”€ TestScraperOrchestrator â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestScraperOrchestrator:

    def _make_orchestrator(
        self,
        routes: list[dict],
        tf_mock: Any,
        am_mock: Any,
        rl_mock: Any,
    ) -> ScraperOrchestrator:
        """Build an orchestrator with mocked internals."""
        orch = ScraperOrchestrator.__new__(ScraperOrchestrator)
        orch._rl = rl_mock
        orch._dedup: set[str] = set()
        orch._routes = routes
        orch._route_agent = RouteScraperAgent(
            rate_limiter=rl_mock,
            tinyfish_client=tf_mock,
            amadeus_client=am_mock,  # legacy alias accepted by RouteScraperAgent
            dedup_set=orch._dedup,
        )
        import logging
        from agents.base_agent import get_logger
        orch._logger = get_logger("flight_agent.scraper.orchestrator")
        return orch

    def _patch_sleep(self) -> Any:
        return patch("agents.scraper_agent.time.sleep")

    def test_run_no_routes_returns_empty(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        orch = self._make_orchestrator(
            [], mock_tinyfish_success, mock_skyscrapper_success, mock_rate_limiter_all_ok
        )
        with self._patch_sleep():
            result = orch.run()
        assert result.routes_attempted == 0
        assert result.total_fares_stored == 0

    def test_run_multiple_routes(
        self,
        mocker: Any,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        routes = [
            {"route": "NAG-DEL", "travel_dates": [_FUTURE_DATE.isoformat()], "check_every_hours": 6},
            {"route": "NAG-BOM", "travel_dates": [_FUTURE_DATE.isoformat()], "check_every_hours": 6},
        ]
        mocker.patch("agents.scraper_agent.queries.get_all_active_routes", return_value=routes)
        orch = self._make_orchestrator(
            routes, mock_tinyfish_success, mock_skyscrapper_success, mock_rate_limiter_all_ok
        )
        with self._patch_sleep():
            result = orch.run()
        assert result.routes_attempted == 2
        assert len(result.route_results) == 2

    def test_one_route_fail_others_continue(
        self,
        mocker: Any,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_always_fails: MagicMock,
        mock_skyscrapper_always_fails: MagicMock,
    ) -> None:
        routes = [
            {"route": "NAG-DEL", "travel_dates": [_FUTURE_DATE.isoformat()], "check_every_hours": 6},
            {"route": "NAG-BOM", "travel_dates": [_FUTURE_DATE.isoformat()], "check_every_hours": 6},
        ]
        mocker.patch("agents.scraper_agent.queries.get_all_active_routes", return_value=routes)
        orch = self._make_orchestrator(
            routes, mock_tinyfish_always_fails, mock_skyscrapper_always_fails, mock_rate_limiter_all_ok
        )
        with self._patch_sleep():
            result = orch.run()
        # Both routes attempted even though both failed
        assert result.routes_attempted == 2
        assert result.routes_failed == 2
        assert result.routes_succeeded == 0

    def test_cooldown_routes_skipped(
        self,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        rl_mock = MagicMock(spec=RateLimiter)
        rl_mock.can_scrape_route.return_value = False  # all routes on cooldown
        routes = [
            {"route": "NAG-DEL", "travel_dates": [_FUTURE_DATE.isoformat()]},
        ]
        orch = self._make_orchestrator(
            routes, mock_tinyfish_success, mock_skyscrapper_success, rl_mock
        )
        with self._patch_sleep():
            result = orch.run()
        assert result.routes_attempted == 0

    def test_stats_recalculated_after_scrape(
        self,
        mocker: Any,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        routes = [{"route": "NAG-DEL", "travel_dates": [_FUTURE_DATE.isoformat()], "check_every_hours": 6}]
        mocker.patch("agents.scraper_agent.queries.get_all_active_routes", return_value=routes)
        orch = self._make_orchestrator(
            routes, mock_tinyfish_success, mock_skyscrapper_success, mock_rate_limiter_all_ok
        )
        with self._patch_sleep():
            orch.run()
        stats = Q.get_price_stats("NAG-DEL", _FUTURE_DATE)
        assert stats is not None
        assert stats.observation_count == 3

    def test_scrape_run_result_accurate(
        self,
        mock_rate_limiter_all_ok: MagicMock,
        mock_tinyfish_success: MagicMock,
        mock_skyscrapper_success: MagicMock,
    ) -> None:
        routes = [{"route": "NAG-DEL", "travel_dates": [_FUTURE_DATE.isoformat()]}]
        orch = self._make_orchestrator(
            routes, mock_tinyfish_success, mock_skyscrapper_success, mock_rate_limiter_all_ok
        )
        with self._patch_sleep():
            result = orch.run()
        # ScrapeRunResult counts must reflect actual DB inserts
        db_count = len(Q.get_price_history("NAG-DEL", _FUTURE_DATE))
        assert result.total_fares_stored == db_count


# â”€â”€â”€ TestRateLimiter â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€


class TestRateLimiter:

    def test_first_scrape_always_allowed(self, tmp_state: Path) -> None:
        rl = RateLimiter(state_file=tmp_state)
        assert rl.can_scrape_route("NAG-DEL", _FUTURE_DATE) is True

    def test_cooldown_blocks_too_soon(self, tmp_state: Path) -> None:
        rl = RateLimiter(state_file=tmp_state)
        rl.record_scrape("NAG-DEL", _FUTURE_DATE)
        # Check immediately â€” should be blocked (0 minutes elapsed < 300)
        assert rl.can_scrape_route("NAG-DEL", _FUTURE_DATE, min_interval_minutes=300) is False

    def test_cooldown_clears_after_interval(self, tmp_state: Path) -> None:
        rl = RateLimiter(state_file=tmp_state)
        # Manually write a last_scraped timestamp that is 301 minutes ago
        old_time = (
            datetime.now(UTC) - timedelta(minutes=301)
        ).isoformat(timespec="seconds").replace("+00:00", "Z")
        state = rl._read_state()
        from agents.rate_limiter import _route_key
        state["last_scraped"][_route_key("NAG-DEL", _FUTURE_DATE)] = old_time
        rl._write_state(state)
        assert rl.can_scrape_route("NAG-DEL", _FUTURE_DATE, min_interval_minutes=300) is True

    def test_tinyfish_counter_increments(self, tmp_state: Path) -> None:
        rl = RateLimiter(state_file=tmp_state)
        for _ in range(3):
            rl.record_tinyfish_call("browser")
        state = rl._read_state()
        assert state["tinyfish_calls_today"]["browser"] == 3

    def test_tinyfish_limit_blocks(self, tmp_state: Path) -> None:
        from agents.rate_limiter import TINYFISH_BROWSER_LIMIT
        rl = RateLimiter(state_file=tmp_state)
        for _ in range(TINYFISH_BROWSER_LIMIT):
            rl.record_tinyfish_call("browser")
        assert rl.can_use_tinyfish_browser() is False

    def test_tinyfish_counter_resets_next_day(self, tmp_state: Path) -> None:
        rl = RateLimiter(state_file=tmp_state)
        for _ in range(5):
            rl.record_tinyfish_call("browser")
        # Write yesterday's date into the state to simulate day rollover
        state = rl._read_state()
        yesterday = (date.today() - timedelta(days=1)).isoformat()
        state["tinyfish_calls_today"]["date"] = yesterday
        rl._write_state(state)
        # Counter should reset
        assert rl.can_use_tinyfish_browser() is True
        state_after = rl._read_state()
        # After calling can_use_tinyfish_browser the state is read-only;
        # the reset only persists on the next write (record_tinyfish_call)
        rl.record_tinyfish_call("browser")
        state_after = rl._read_state()
        assert state_after["tinyfish_calls_today"]["browser"] == 1

    def test_skyscrapper_limit_blocks(self, tmp_state: Path) -> None:
        from agents.rate_limiter import SKYSCRAPPER_DAILY_LIMIT
        rl = RateLimiter(state_file=tmp_state)
        state = rl._read_state()
        state["skyscrapper_calls_today"]["count"] = SKYSCRAPPER_DAILY_LIMIT
        rl._write_state(state)
        assert rl.can_use_skyscrapper() is False

    def test_state_persists_across_instances(self, tmp_state: Path) -> None:
        rl1 = RateLimiter(state_file=tmp_state)
        rl1.record_tinyfish_call("browser")
        rl1.record_tinyfish_call("browser")

        rl2 = RateLimiter(state_file=tmp_state)
        state = rl2._read_state()
        assert state["tinyfish_calls_today"]["browser"] == 2

    def test_concurrent_state_writes(self, tmp_state: Path) -> None:
        """10 threads each call record_scrape â€” no file corruption."""
        rl = RateLimiter(state_file=tmp_state)
        errors: list[Exception] = []

        def worker(idx: int) -> None:
            try:
                route_date = _FUTURE_DATE + timedelta(days=idx)
                rl.record_scrape("NAG-DEL", route_date)
            except Exception as exc:
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Concurrency errors: {errors}"

        # Verify file is valid JSON with all 10 entries
        state = rl._read_state()
        assert len(state["last_scraped"]) == 10

