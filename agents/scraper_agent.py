"""agents/scraper_agent.py — Phase 2 scraping layer for SkySaver.

Three-tier architecture:
  Tier 1 - ScraperOrchestrator: owns the full scrape run lifecycle.
  Tier 2 - RouteScraperAgent:   scrapes one route+date pair, tries all sources.
  Tier 3 - TinyFish/SkyScrapper clients: thin wrappers with retry logic.

External calls:
  • TinyFish Browser (Skyscanner)  — primary, DataDome bypass via headless Chromium
  • TinyFish Fetch  (Google Flights) — secondary, faster no-JS path
  • Sky Scrapper API (RapidAPI)    — Tier 3 fallback, structured JSON via REST

Never imports sqlite3 directly; all DB access via db.queries.
"""

from __future__ import annotations

import json
import logging
import os
import random
import re
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime, timezone
from typing import Optional

import requests

from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
    wait_random,
)

from agents.base_agent import get_logger, utcnow, to_iso
from agents.rate_limiter import RateLimiter
import db.queries as queries

# ─── MODULE LOGGERS ───────────────────────────────────────────────────────────

_log_orch = get_logger("flight_agent.scraper.orchestrator", "scraper.log")
_log_route = get_logger("flight_agent.scraper.route", "scraper.log")
_log_tf = get_logger("flight_agent.scraper.tinyfish", "scraper.log")
_log_ss = get_logger("flight_agent.scraper.skyscrapper", "scraper.log")

# ─── MODULE CONSTANTS ─────────────────────────────────────────────────────────

USD_TO_INR_FALLBACK: float = 83.0  # Fixed conversion rate (log WARNING when used)
_DEDUP_WINDOW_SECONDS: int = 1800  # 30 minutes

SCRAPER_SYSTEM_PROMPT: str = """
You are a flight fare extraction agent. Your ONLY job is to extract flight
price data from web page content and return it as a valid JSON array.

OUTPUT FORMAT:
Return ONLY a valid JSON array of objects. No explanation. No markdown prose.
No text before or after the array. Start with "[" and end with "]".

EACH OBJECT MUST HAVE EXACTLY THESE KEYS (use null if data is missing):
  "price_inr"      — integer, fare in Indian Rupees, no symbol, no commas
  "airline"        — string, carrier name (see normalisation rules below)
  "stops"          — integer: 0 for direct/non-stop, 1 for one stop, 2 for two+
  "departure_time" — string in HH:MM 24-hour format e.g. "06:30", or null

MISSING FIELD RULES:
  - If price is missing or unparseable → OMIT the entire object (do not guess)
  - If airline is missing → use null for "airline"
  - If stops is missing → default to 0
  - If departure_time is missing → use null

AIRLINE NORMALISATION RULES (map raw names to canonical):
  IndiGo, 6E, IndiGo Airlines, InterGlobe → "IndiGo"
  Air India, AI, Air India Limited         → "Air India"
  SpiceJet, SG, Spice Jet                 → "SpiceJet"
  Vistara, UK, Air Asia India              → "Vistara"
  Akasa, QP, Akasa Air                    → "Akasa Air"
  Go First, G8, Go Air, Go Airlines       → "Go First"
  Alliance Air, 9I                        → "Alliance Air"
  Star Air, S5                            → "Star Air"
  Any unrecognised airline → keep as-is, title-cased

PRICE EXTRACTION RULES:
  - Strip ₹, INR, Rs., USD prefixes
  - Remove all commas and spaces within the number
  - Truncate decimal part (fares are whole rupees)
  - Convert USD to INR at rate 83 if price is in USD
  - Never return 0 or negative prices

Return an empty array [] if no valid fares are found.
""".strip()

AIRLINE_NORMALISATION_MAP: dict[str, str] = {
    # IndiGo variants
    "indigo": "IndiGo",
    "6e": "IndiGo",
    "interglobe": "IndiGo",
    "indigo airlines": "IndiGo",
    # Air India variants
    "air india": "Air India",
    "ai": "Air India",
    "air india limited": "Air India",
    # SpiceJet variants
    "spicejet": "SpiceJet",
    "sg": "SpiceJet",
    "spice jet": "SpiceJet",
    # Vistara variants
    "vistara": "Vistara",
    "uk": "Vistara",
    "air asia india": "Vistara",
    # Akasa Air variants
    "akasa": "Akasa Air",
    "qp": "Akasa Air",
    "akasa air": "Akasa Air",
    # Go First variants
    "go first": "Go First",
    "g8": "Go First",
    "go air": "Go First",
    "go airlines": "Go First",
    # Alliance Air variants
    "alliance air": "Alliance Air",
    "9i": "Alliance Air",
    # Star Air variants
    "star air": "Star Air",
    "s5": "Star Air",
}

_ROUTE_PATTERN: re.Pattern[str] = re.compile(r"^[A-Z]{3}-[A-Z]{3}$")

# ─── CUSTOM EXCEPTIONS ────────────────────────────────────────────────────────


class ScraperError(Exception):
    """Base exception for all scraper layer errors."""


class RouteScrapeFailed(ScraperError):
    """All data sources exhausted for a route+date. No fares obtained."""

    def __init__(self, route: str, travel_date: date, reason: str) -> None:
        self.route = route
        self.travel_date = travel_date
        self.reason = reason
        super().__init__(
            f"Scrape failed for {route} on {travel_date}: {reason}"
        )


class TinyFishRateLimitError(ScraperError):
    """TinyFish returned HTTP 429."""


class TinyFishTimeoutError(ScraperError):
    """TinyFish call exceeded the timeout threshold."""


class TinyFishInvalidResponseError(ScraperError):
    """TinyFish returned a response that cannot be parsed as valid fare data."""


class SkyScrapprrAPIError(ScraperError):
    """Sky Scrapper API returned HTTP 5xx or irrecoverable error."""


class PriceParseError(ScraperError):
    """Could not extract a valid INR price from the raw string."""


# ─── DATACLASSES ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ScrapedFare:
    """One normalised flight fare from any data source."""

    route: str          # "NAG-DEL" — always uppercase
    travel_date: date
    price_inr: int      # whole INR
    airline: str        # canonical airline name
    stops: int          # 0=non-stop, 1=one-stop, 2=two-stop
    source: str         # "skyscanner" | "google_flights" | "skyscrapper"
    raw_price_str: str  # original price string e.g. "₹3,240"
    scraped_at: datetime


@dataclass
class RouteScapeResult:
    """Result of scraping one route+date pair."""

    route: str
    travel_date: date
    fares_found: int
    fares_stored: int
    source_used: str       # which source actually returned data
    fallback_used: bool    # True if Sky Scrapper fallback was triggered
    error: Optional[str]   # None if successful
    duration_seconds: float


@dataclass(frozen=True)
class ScrapeRunResult:
    """Aggregated result of a full scrape run across all routes."""

    started_at: datetime
    finished_at: datetime
    routes_attempted: int
    routes_succeeded: int
    routes_failed: int
    total_fares_scraped: int
    total_fares_stored: int
    fallback_triggered_count: int
    route_results: tuple[RouteScapeResult, ...]
    errors: tuple[str, ...]


# ─── VALIDATION HELPERS ───────────────────────────────────────────────────────


def _validate_route(route: str) -> tuple[str, str]:
    """Validate and parse a route string into (origin, destination).

    Valid format: exactly two 3-letter uppercase IATA codes separated by ``-``.

    Args:
        route: e.g. ``"NAG-DEL"``.

    Returns:
        Tuple ``(origin, destination)`` e.g. ``("NAG", "DEL")``.

    Raises:
        ValueError: If the route does not match ``^[A-Z]{3}-[A-Z]{3}$``.
    """
    if not _ROUTE_PATTERN.match(route):
        raise ValueError(
            f"Invalid route format: '{route}'. "
            "Expected 'XXX-YYY' with 3-letter uppercase IATA codes, e.g. 'NAG-DEL'."
        )
    origin, destination = route.split("-")
    return origin, destination


def _validate_travel_date(travel_date: date) -> None:
    """Validate that *travel_date* is in the future and within 365 days.

    Args:
        travel_date: Departure date to validate.

    Raises:
        ValueError: If today, in the past, or more than 365 days away.
    """
    today = date.today()  # local calendar date — consistent with date.today() in callers
    days_until = (travel_date - today).days
    if days_until <= 0:
        raise ValueError(
            f"Travel date {travel_date} must be in the future (today is {today})."
        )
    if days_until > 365:
        raise ValueError(
            f"Travel date {travel_date} is {days_until} days away; maximum is 365."
        )


# ─── PRICE PARSER ─────────────────────────────────────────────────────────────

# Matches digit groups (with optional Indian lakh-style commas) and an optional
# decimal part. E.g. "₹1,20,000.00" → groups ["1", "20", "000"], decimal ".00"
_DIGIT_RE: re.Pattern[str] = re.compile(r"[\d,]+(?:\.\d+)?")
_USD_RE: re.Pattern[str] = re.compile(r"^\s*usd\b", re.IGNORECASE)


def _parse_price_inr(raw: str) -> int:
    """Extract an integer INR fare from a raw price string.

    Handles every real-world format seen on Indian travel sites:
      ``"₹3,240"`` → 3240
      ``"INR 3,240"`` → 3240
      ``"Rs. 3240"`` → 3240
      ``"3,240.00"`` → 3240
      ``"3240"`` → 3240
      ``"₹1,20,000"`` → 120000  (Indian lakh format)
      ``"USD 42"`` → 3486  (42 × 83, logs WARNING)

    Args:
        raw: Raw price string as returned by scraper or API.

    Returns:
        Fare as a whole-number integer in INR.

    Raises:
        PriceParseError: If the string is empty, ``"N/A"``, ``"null"``, or
            contains no parseable digit group.
    """
    if not raw or not raw.strip():
        raise PriceParseError("Empty price string")

    stripped = raw.strip()
    lower = stripped.lower()

    _RESERVED = {"n/a", "null", "none", "na", "unavailable", "-"}
    if lower in _RESERVED:
        raise PriceParseError(f"Price unavailable: {stripped!r}")

    is_usd = bool(_USD_RE.match(stripped))

    match = _DIGIT_RE.search(stripped)
    if not match:
        raise PriceParseError(f"No numeric value found in price string: {stripped!r}")

    numeric_str = match.group(0)
    # Strip commas (handles both Western "3,240" and Indian "1,20,000" formats)
    numeric_str = numeric_str.replace(",", "")
    price_float = float(numeric_str)
    price_int = int(price_float)  # truncate decimals — fares are whole rupees

    if price_int <= 0:
        raise PriceParseError(f"Parsed price is non-positive: {price_int} from {stripped!r}")

    if is_usd:
        converted = int(price_int * USD_TO_INR_FALLBACK)
        _log_route.warning(
            json.dumps({
                "event": "usd_price_converted",
                "raw": stripped,
                "usd_amount": price_int,
                "inr_result": converted,
                "rate": USD_TO_INR_FALLBACK,
                "warning": "Price in USD detected; converted at fixed rate",
            })
        )
        return converted

    return price_int


# ─── AIRLINE NORMALISER ───────────────────────────────────────────────────────


def _normalise_airline(raw: str) -> str:
    """Map a raw airline name to its canonical form.

    Lookup is case-insensitive on the stripped raw name. Unknown names are
    title-cased and stored as-is after logging a WARNING.

    Args:
        raw: Airline name as returned by the scraper or API.

    Returns:
        Canonical airline name string.

    Raises:
        ValueError: If *raw* is empty after stripping.
    """
    if not raw or not raw.strip():
        raise ValueError("Airline name must not be empty.")

    key = raw.strip().lower()
    if key in AIRLINE_NORMALISATION_MAP:
        return AIRLINE_NORMALISATION_MAP[key]

    title_cased = raw.strip().title()
    _log_route.warning(
        json.dumps({
            "event": "unknown_airline",
            "raw": raw,
            "stored_as": title_cased,
            "warning": f"Unknown airline name: {raw!r} — stored as-is",
        })
    )
    return title_cased


# ─── TINYFISH GOAL BUILDERS ───────────────────────────────────────────────────


def _build_skyscanner_goal(
    origin: str, destination: str, travel_date: date
) -> str:
    """Construct the TinyFish Browser goal string for Skyscanner.

    Args:
        origin: 3-letter IATA code e.g. ``"NAG"``.
        destination: 3-letter IATA code e.g. ``"DEL"``.
        travel_date: Departure date.

    Returns:
        Imperative goal string for the TinyFish Browser endpoint.
    """
    date_str = travel_date.strftime("%d %B %Y")
    # Build a deep-link URL directly to search results (avoids landing-page CAPTCHA)
    date_param = travel_date.strftime("%Y-%m-%d")
    deep_url = (
        f"https://www.skyscanner.co.in/transport/flights/{origin.lower()}/{destination.lower()}/"
        f"{date_param.replace('-', '')}/"
        f"?adults=1&adultsv2=1&cabinclass=economy&children=0&inboundaltsenabled=false"
        f"&infants=0&outboundaltsenabled=false&preferdirects=false&ref=home&rtn=0"
    )
    return (
        f"Navigate to {deep_url} which is the Skyscanner India flight search page. "
        f"Wait up to 15 seconds for the flight results list to load (you will see price cards). "
        f"If a CAPTCHA appears, try refreshing once and waiting. "
        f"Extract the 5 cheapest one-way fares from the results list departing on {date_str}. "
        f"For each fare return a JSON object with these exact keys: "
        f"price_inr (integer in Indian Rupees, no symbol, no commas — if shown in USD convert at 83x), "
        f"airline (carrier name string), "
        f"stops (integer: 0 for direct/non-stop, 1 for one-stop, 2 for two or more stops), "
        f"departure_time (string HH:MM 24h format e.g. '06:30', or null if not shown). "
        f"Return ONLY a valid JSON array. No explanation text. "
        f"If fewer than 5 results are visible return what is available. "
        f"If no results appear at all return []."
    )


def _build_google_flights_goal(
    origin: str, destination: str, travel_date: date
) -> str:
    """Construct the TinyFish Fetch goal string for Google Flights.

    Uses a direct search URL with IATA codes and date embedded so TinyFish
    Fetch retrieves actual search result content, not just the homepage.

    Args:
        origin: 3-letter IATA code.
        destination: 3-letter IATA code.
        travel_date: Departure date.

    Returns:
        Target URL string for the TinyFish Fetch endpoint.
    """
    date_str = travel_date.strftime("%Y-%m-%d")
    date_compact = travel_date.strftime("%Y%m%d")  # YYYYMMDD for URL
    # Google Flights one-way deep link — include exact departure date in the path
    # Format: /travel/flights/flights-from-ORIG-to-DEST/ORIG-DEST-YYYYMMDD/
    search_url = (
        f"https://www.google.com/travel/flights/flights-from-{origin}-to-{destination}"
        f"/{origin}-{destination}-{date_compact}/"
        f"?hl=en&gl=IN&curr=INR"
    )
    return search_url



# ─── TINYFISH RESPONSE PARSER ─────────────────────────────────────────────────


def _strip_markdown_fences(text: str) -> str:
    """Remove leading/trailing markdown code fences from *text*.

    TinyFish sometimes wraps JSON in ```json ... ``` blocks.

    Args:
        text: Raw TinyFish response string.

    Returns:
        String with markdown fences stripped.
    """
    text = text.strip()
    # Remove opening fence: ```json or ```
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    # Remove closing fence
    text = re.sub(r"\s*```\s*$", "", text)
    return text.strip()


def _extract_json_array(text: str) -> str:
    """Extract the first JSON array substring from *text*.

    Finds the first ``[`` and the last ``]`` and returns the slice.

    Args:
        text: String potentially containing a JSON array.

    Returns:
        Substring from first ``[`` to last ``]`` (inclusive).

    Raises:
        TinyFishInvalidResponseError: If no ``[`` or ``]`` is found.
    """
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1 or end < start:
        raise TinyFishInvalidResponseError(
            f"No JSON array found in response. Snippet: {text[:200]!r}"
        )
    return text[start : end + 1]


def _parse_tinyfish_response(
    raw: str,
    route: str,
    travel_date: date,
    source: str,
) -> list[ScrapedFare]:
    """Parse a raw TinyFish response string into a list of ScrapedFare.

    Processing pipeline:
      1. Strip markdown code fences.
      2. Extract first JSON array substring (``[`` … ``]``).
      3. ``json.loads()`` the array.
      4. Validate it is a list.
      5. For each item: validate required keys, parse price and airline.
      6. Individual fare failures are logged at DEBUG and skipped.
      7. If zero valid fares remain → raise TinyFishInvalidResponseError.

    Args:
        raw: Raw string returned by TinyFish.
        route: Route string e.g. ``"NAG-DEL"`` (used in log events).
        travel_date: Departure date (used to construct ScrapedFare).
        source: ``"skyscanner"`` or ``"google_flights"``.

    Returns:
        List of valid :class:`ScrapedFare` objects (may be empty list for ``[]``).

    Raises:
        TinyFishInvalidResponseError: If the response cannot be decoded or all
            fares fail validation.
    """
    _log_tf.debug(
        json.dumps({
            "event": "tinyfish_response_raw",
            "route": route,
            "response_length": len(raw),
            "source": source,
        })
    )

    cleaned = _strip_markdown_fences(raw)
    array_str = _extract_json_array(cleaned)

    try:
        data = json.loads(array_str)
    except json.JSONDecodeError as exc:
        raise TinyFishInvalidResponseError(
            f"JSON decode failed for route {route}: {exc}. "
            f"Snippet: {array_str[:200]!r}"
        ) from exc

    if not isinstance(data, list):
        raise TinyFishInvalidResponseError(
            f"Expected JSON array, got {type(data).__name__} for route {route}."
        )

    if len(data) == 0:
        _log_tf.info(
            json.dumps({
                "event": "tinyfish_parse_success",
                "route": route,
                "fares_extracted": 0,
                "source": source,
            })
        )
        return []

    fares: list[ScrapedFare] = []
    now = utcnow()

    for idx, item in enumerate(data):
        fare = _parse_single_tinyfish_fare(item, idx, route, travel_date, source, now)
        if fare is not None:
            fares.append(fare)

    if not fares and len(data) > 0:
        raise TinyFishInvalidResponseError(
            f"All {len(data)} fares failed validation for route {route} "
            f"source {source}."
        )

    _log_tf.info(
        json.dumps({
            "event": "tinyfish_parse_success",
            "route": route,
            "fares_extracted": len(fares),
            "source": source,
        })
    )
    return fares


def _parse_single_tinyfish_fare(
    item: object,
    idx: int,
    route: str,
    travel_date: date,
    source: str,
    now: datetime,
) -> Optional[ScrapedFare]:
    """Attempt to parse one raw fare dict into a ScrapedFare.

    Args:
        item: Raw object from parsed JSON array.
        idx: Index in the array (for log context).
        route: Route string.
        travel_date: Departure date.
        source: Data source name.
        now: Timestamp to use as scraped_at.

    Returns:
        :class:`ScrapedFare` on success, ``None`` if validation fails.
    """
    if not isinstance(item, dict):
        _log_tf.debug(
            json.dumps({
                "event": "fare_validation_failed",
                "route": route,
                "index": idx,
                "reason": "fare is not a dict",
                "raw_value": str(item)[:200],
            })
        )
        return None

    # Price is mandatory — skip fare if missing or unparseable
    raw_price = item.get("price_inr")
    if raw_price is None:
        _log_tf.debug(
            json.dumps({
                "event": "fare_validation_failed",
                "route": route,
                "index": idx,
                "field": "price_inr",
                "raw_value": None,
                "reason": "price_inr key missing",
            })
        )
        return None

    raw_price_str = str(raw_price)
    try:
        price_inr = _parse_price_inr(raw_price_str)
    except PriceParseError as exc:
        _log_tf.debug(
            json.dumps({
                "event": "fare_validation_failed",
                "route": route,
                "index": idx,
                "field": "price_inr",
                "raw_value": raw_price_str,
                "reason": str(exc),
            })
        )
        return None

    # Airline — nullable, but normalise if present
    raw_airline = item.get("airline") or ""
    try:
        airline = _normalise_airline(raw_airline) if raw_airline else "Unknown"
    except ValueError:
        airline = "Unknown"

    # Stops — default to 0 if missing
    stops_raw = item.get("stops", 0)
    try:
        stops = int(stops_raw)
    except (TypeError, ValueError):
        stops = 0

    return ScrapedFare(
        route=route,
        travel_date=travel_date,
        price_inr=price_inr,
        airline=airline,
        stops=stops,
        source=source,
        raw_price_str=raw_price_str,
        scraped_at=now,
    )


# ─── DEDUP HELPER ─────────────────────────────────────────────────────────────


def _make_dedup_key(fare: ScrapedFare) -> str:
    """Create a deduplication key from a fare's identifying fields."""
    return f"{fare.route}|{fare.travel_date}|{fare.price_inr}|{fare.airline}"


# ─── TINYFISH CLIENT (TIER 3) ────────────────────────────────────────────────


class TinyFishClient:
    """Thin wrapper around the TinyFish API with per-endpoint retry logic.

    Retry strategies:
      Browser: 3 attempts, exponential backoff 10–60s + jitter, retries on
               RateLimit and Timeout only.
      Fetch:   2 attempts, exponential backoff 5–30s, same retry conditions.

    Raises:
        TinyFishRateLimitError: On HTTP 429.
        TinyFishTimeoutError: On request timeout.
        TinyFishInvalidResponseError: On HTTP 422 (bad goal string).
        ScraperError: On HTTP 503 (service unavailable).
    """

    def __init__(self) -> None:
        self._api_key = os.getenv("TINYFISH_API_KEY", "")
        self._logger = _log_tf

    def call_browser(self, goal: str, route: str) -> str:
        """Call TinyFish Browser endpoint (headless Chromium, DataDome bypass).

        Args:
            goal: Imperative goal string for the browser agent.
            route: Route string for logging context.

        Returns:
            Raw response string from TinyFish.

        Raises:
            TinyFishRateLimitError: If HTTP 429 persists after all retries.
            TinyFishTimeoutError: If timeout persists after all retries.
            TinyFishInvalidResponseError: If goal string is rejected (HTTP 422).
            ScraperError: If service is unavailable (HTTP 503).
        """
        self._logger.debug(
            json.dumps({
                "event": "tinyfish_call_made",
                "endpoint": "browser",
                "route": route,
                "goal_length": len(goal),
            })
        )
        return self._call_browser_with_retry(goal, route)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=10, max=60) + wait_random(0, 5),
        retry=retry_if_exception_type((TinyFishRateLimitError, TinyFishTimeoutError)),
        reraise=True,
        before_sleep=before_sleep_log(_log_tf, logging.WARNING),
    )
    def _call_browser_with_retry(self, goal: str, route: str) -> str:
        return self._execute_tinyfish_request("browser", goal, route)

    def call_fetch(self, goal: str, route: str) -> str:
        """Call TinyFish Fetch endpoint (lighter, no JS rendering).

        Args:
            goal: Imperative goal string.
            route: Route string for logging context.

        Returns:
            Raw response string from TinyFish.
        """
        self._logger.debug(
            json.dumps({
                "event": "tinyfish_call_made",
                "endpoint": "fetch",
                "route": route,
                "goal_length": len(goal),
            })
        )
        return self._call_fetch_with_retry(goal, route)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=1, min=5, max=30),
        retry=retry_if_exception_type((TinyFishRateLimitError, TinyFishTimeoutError)),
        reraise=True,
        before_sleep=before_sleep_log(_log_tf, logging.WARNING),
    )
    def _call_fetch_with_retry(self, goal: str, route: str) -> str:
        return self._execute_tinyfish_request("fetch", goal, route)

    def _execute_tinyfish_request(
        self, endpoint: str, goal: str, route: str
    ) -> str:
        """Perform the actual HTTP call to TinyFish.

        Routing (new API architecture — api.tinyfish.io is dead):
          browser → POST agent.tinyfish.ai/v1/automation/run
                    payload: {url, goal, browser_profile: "stealth"}
                    response: {status, result: <object>, error}
                    The ``result`` value is serialised back to a JSON string
                    so the existing _parse_tinyfish_response() works unchanged.

          fetch   → POST api.fetch.tinyfish.ai
                    payload: {urls: [<extracted-url>]}
                    response: [{url, content: <markdown>}]
                    Returns the ``content`` markdown string directly; the LLM
                    parser in _parse_tinyfish_response will extract fares from it.

        Args:
            endpoint: ``"browser"`` or ``"fetch"``.
            goal: Goal/instruction string (also encodes the target URL).
            route: Route string for error context.

        Returns:
            Raw text response (JSON array string for browser; markdown for fetch).

        Raises:
            TinyFishRateLimitError: On HTTP 429.
            TinyFishInvalidResponseError: On HTTP 422 / bad input.
            TinyFishTimeoutError: On request timeout / connection error.
            ScraperError: On HTTP 5xx or other unexpected errors.
        """
        import re
        import urllib.error
        import urllib.request

        headers = {
            "X-API-Key": self._api_key,
            "Content-Type": "application/json",
        }

        if endpoint == "browser":
            # Build a deep-link URL that goes directly to search results (less CAPTCHA exposure).
            # Use skyscanner.co.in + India residential proxy for minimal bot detection.
            url_match = re.search(r"https?://[^\s]+", goal)
            start_url = url_match.group(0).split("?")[0] if url_match else "https://www.skyscanner.co.in"
            api_url = "https://agent.tinyfish.ai/v1/automation/run"
            payload = json.dumps({
                "url": start_url,
                "goal": goal,
                "browser_profile": "stealth",
                "proxy_config": {
                    "enabled": True,
                    "type": "tetra",
                    "country_code": "US",   # US proxy — IN not supported by TinyFish
                },
            }).encode("utf-8")
            timeout = 180
        else:
            # fetch: extract the URL from the goal and hand it to the fetch API
            url_match = re.search(r"https?://[^\s]+", goal)
            target_url = url_match.group(0).rstrip(".") if url_match else "https://www.google.com/travel/flights"
            api_url = "https://api.fetch.tinyfish.ai"
            payload = json.dumps({"urls": [target_url]}).encode("utf-8")
            timeout = 35

        url = "https://api.fetch.tinyfish.ai/v1/agent"
        req = urllib.request.Request(
            api_url,
            data=payload,
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            match exc.code:
                case 429:
                    self._logger.warning(
                        json.dumps({
                            "event": "tinyfish_rate_limited",
                            "route": route,
                            "endpoint": endpoint,
                        })
                    )
                    raise TinyFishRateLimitError(
                        f"TinyFish {endpoint} HTTP 429 for route {route}"
                    ) from exc
                case 422 | 400:
                    body = exc.read().decode("utf-8", errors="replace")[:300]
                    self._logger.error(
                        json.dumps({
                            "event": "tinyfish_invalid_goal",
                            "route": route,
                            "endpoint": endpoint,
                            "response": body,
                        })
                    )
                    raise TinyFishInvalidResponseError(
                        f"TinyFish rejected request (HTTP {exc.code}) for route {route}: {body}"
                    ) from exc
                case 503:
                    raise ScraperError(
                        f"TinyFish service unavailable (HTTP 503) for route {route}"
                    ) from exc
                case _:
                    raise ScraperError(
                        f"TinyFish HTTP {exc.code} for route {route}"
                    ) from exc
        except TimeoutError as exc:
            raise TinyFishTimeoutError(
                f"TinyFish {endpoint} timed out for route {route}"
            ) from exc
        except OSError as exc:
            raise TinyFishTimeoutError(
                f"TinyFish {endpoint} connection error for route {route}: {exc}"
            ) from exc

        # ── post-process response into the string format _parse_tinyfish_response expects ──
        if endpoint == "browser":
            # Agent API returns: {"status": "COMPLETED", "result": {...}, ...}
            # result may be a dict (structured output) or a string (raw LLM output).
            try:
                data = json.loads(raw)
                status = data.get("status", "")
                # TinyFish returns blocked status as a JSON object, not FAILED
                if status == "FAILED":
                    err = data.get("error") or {}
                    raise ScraperError(
                        f"TinyFish agent run FAILED for route {route}: {err}"
                    )
                if status == "blocked":
                    raise TinyFishInvalidResponseError(
                        f"TinyFish browser BLOCKED (CAPTCHA) for route {route}: {data.get('reason', '')}"
                    )
                result = data.get("result")
                if result is None:
                    return raw  # pass through so parser can handle/raise
                # If result is already a list or dict, serialise it as JSON string
                if isinstance(result, (list, dict)):
                    return json.dumps(result)
                return str(result)
            except (json.JSONDecodeError, KeyError):
                return raw  # pass raw through; _parse_tinyfish_response will handle

        else:
            # Fetch API returns: {"results": [{"url": ..., "text": "<markdown>", ...}], "errors": []}
            # Older versions returned: [{"url": ..., "content": "<markdown>"}]
            # We handle both. Extract 'text' first (new), then 'content'/'markdown' (old).
            try:
                data = json.loads(raw)
                # New format: {"results": [...]}
                if isinstance(data, dict) and "results" in data:
                    results = data["results"]
                    if results:
                        first = results[0]
                        content = first.get("text") or first.get("content") or first.get("markdown") or raw
                        return content
                # Old format: [{...}]
                elif isinstance(data, list) and data:
                    first = data[0]
                    content = first.get("text") or first.get("content") or first.get("markdown") or raw
                    return content
            except (json.JSONDecodeError, IndexError, KeyError):
                pass
            return raw




class SkyScrappperClient:
    """Thin wrapper around the Sky Scrapper API (RapidAPI).

    Implements a two-step call pattern:
      Step 1: searchAirport — resolve IATA code to skyId + entityId (cached).
      Step 2: searchFlightsComplete — fetch itineraries and parse fares.

    Retry strategy: 2 attempts, 30s fixed wait, retries on SkyScrapprrAPIError.
    entity_cache is instance-level (not module-level) for thread safety.
    """

    _BASE_HOST = "sky-scrapper.p.rapidapi.com"
    _BASE_URL = f"https://{_BASE_HOST}"

    def __init__(self) -> None:
        self._api_key = os.getenv("RAPIDAPI_KEY", "")
        self._logger = _log_ss
        self.entity_cache: dict[str, dict[str, str]] = {}  # IATA → {skyId, entityId}

    def fetch_fares(
        self,
        route: str,
        travel_date: date,
        max_results: int = 5,
    ) -> list[ScrapedFare]:
        """Fetch flight offers from Sky Scrapper and return normalised ScrapedFare list.

        Args:
            route: Route string e.g. ``"NAG-DEL"``.
            travel_date: Departure date.
            max_results: Maximum fares to return (cheapest first).

        Returns:
            List of :class:`ScrapedFare` objects. May be empty if no flights found.

        Raises:
            SkyScrapprrAPIError: On HTTP 5xx after retries.
        """
        origin, destination = _validate_route(route)
        self._logger.info(
            json.dumps({
                "event": "skyscrapper_call_made",
                "route": route,
                "travel_date": travel_date.isoformat(),
            })
        )
        return self._fetch_with_retry(origin, destination, travel_date, route, max_results)

    @retry(
        stop=stop_after_attempt(2),
        wait=wait_fixed(30),
        retry=retry_if_exception_type(SkyScrapprrAPIError),
        reraise=True,
        before_sleep=before_sleep_log(_log_ss, logging.WARNING),
    )
    def _fetch_with_retry(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        route: str,
        max_results: int,
    ) -> list[ScrapedFare]:
        return self._execute_skyscrapper_request(
            origin, destination, travel_date, route, max_results
        )

    def _resolve_airport(self, iata: str) -> dict[str, str]:
        """Resolve IATA code to skyId + entityId via searchAirport endpoint.

        Results are cached on the instance so the same IATA is never looked up
        twice within the lifetime of this client instance.

        Args:
            iata: 3-letter uppercase IATA code.

        Returns:
            Dict with ``skyId`` and ``entityId`` keys.

        Raises:
            SkyScrapprrAPIError: On 5xx from searchAirport.
            ScraperError: On 4xx (bad IATA) or network failure.
        """
        if iata in self.entity_cache:
            return self.entity_cache[iata]

        url = f"{self._BASE_URL}/api/v1/flights/searchAirport"
        headers = {
            "x-rapidapi-host": self._BASE_HOST,
            "x-rapidapi-key": self._api_key,
        }
        params = {"query": iata, "locale": "en-IN"}

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=20)
        except requests.exceptions.Timeout as exc:
            raise ScraperError(
                f"Sky Scrapper searchAirport timed out for IATA {iata}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ScraperError(
                f"Sky Scrapper searchAirport network error for IATA {iata}: {exc}"
            ) from exc

        if resp.status_code == 429:
            self._logger.warning(
                json.dumps({
                    "event": "skyscrapper_rate_limited",
                    "step": "searchAirport",
                    "iata": iata,
                })
            )
            time.sleep(5)  # brief pause before retry (60s was excessive for already-exhausted quota)
            # Retry once
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=20)
            except requests.exceptions.RequestException as exc:
                raise ScraperError(
                    f"Sky Scrapper searchAirport retry failed for IATA {iata}: {exc}"
                ) from exc
            if resp.status_code == 429:
                raise ScraperError(
                    f"Sky Scrapper searchAirport still 429 after retry for IATA {iata}"
                )

        if resp.status_code >= 500:
            raise SkyScrapprrAPIError(
                f"Sky Scrapper searchAirport HTTP {resp.status_code} for IATA {iata}"
            )
        if not resp.ok:
            self._logger.error(
                json.dumps({
                    "event": "skyscrapper_airport_error",
                    "iata": iata,
                    "status": resp.status_code,
                })
            )
            raise ScraperError(
                f"Sky Scrapper searchAirport HTTP {resp.status_code} for IATA {iata}"
            )

        try:
            data = resp.json()
        except ValueError as exc:
            raise ScraperError(
                f"Sky Scrapper searchAirport non-JSON response for IATA {iata}"
            ) from exc

        # Extract first result with a valid entityId
        places = data.get("data", [])
        for place in places:
            entity_id = str(place.get("entityId", ""))
            sky_id = str(place.get("skyId", "") or iata)
            if entity_id:
                result = {"skyId": sky_id, "entityId": entity_id}
                self.entity_cache[iata] = result
                self._logger.debug(
                    json.dumps({
                        "event": "skyscrapper_airport_resolved",
                        "iata": iata,
                        "skyId": sky_id,
                        "entityId": entity_id,
                    })
                )
                return result

        raise ScraperError(
            f"Sky Scrapper searchAirport returned no valid entityId for IATA {iata}. "
            f"Data: {str(places)[:200]}"
        )

    def _execute_skyscrapper_request(
        self,
        origin: str,
        destination: str,
        travel_date: date,
        route: str,
        max_results: int,
    ) -> list[ScrapedFare]:
        """Perform the two-step Sky Scrapper API call and parse fares.

        Args:
            origin: 3-letter IATA origin code.
            destination: 3-letter IATA destination code.
            travel_date: Departure date.
            route: Full route string for logging.
            max_results: Max fares to return.

        Returns:
            List of :class:`ScrapedFare` objects (up to *max_results*, cheapest first).

        Raises:
            SkyScrapprrAPIError: On 5xx from flight search endpoint.
            ScraperError: On 4xx or resolution failure.
        """
        # Step 1: resolve airport entity IDs
        try:
            origin_info = self._resolve_airport(origin)
            dest_info = self._resolve_airport(destination)
        except (SkyScrapprrAPIError, ScraperError):
            raise

        # Step 2: search flights
        url = f"{self._BASE_URL}/api/v2/flights/searchFlightsComplete"
        headers = {
            "x-rapidapi-host": self._BASE_HOST,
            "x-rapidapi-key": self._api_key,
        }
        params = {
            "originSkyId": origin_info["skyId"],
            "destinationSkyId": dest_info["skyId"],
            "originEntityId": origin_info["entityId"],
            "destinationEntityId": dest_info["entityId"],
            "date": travel_date.isoformat(),
            "cabinClass": "economy",
            "adults": 1,
            "currency": "INR",
            "countryCode": "IN",
            "market": "en-IN",
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.exceptions.Timeout as exc:
            raise SkyScrapprrAPIError(
                f"Sky Scrapper searchFlights timed out for route {route}"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise ScraperError(
                f"Sky Scrapper searchFlights network error for route {route}: {exc}"
            ) from exc

        if resp.status_code == 429:
            self._logger.warning(
                json.dumps({
                    "event": "skyscrapper_rate_limited",
                    "step": "searchFlights",
                    "route": route,
                })
            )
            time.sleep(5)  # brief pause before retry
            try:
                resp = requests.get(url, headers=headers, params=params, timeout=30)
            except requests.exceptions.RequestException as exc:
                raise ScraperError(
                    f"Sky Scrapper searchFlights retry failed for route {route}: {exc}"
                ) from exc
            if resp.status_code == 429:
                self._logger.warning(
                    json.dumps({
                        "event": "skyscrapper_rate_limit_retry_failed",
                        "route": route,
                    })
                )
                return []

        if resp.status_code >= 500:
            raise SkyScrapprrAPIError(
                f"Sky Scrapper searchFlights HTTP {resp.status_code} for route {route}"
            )
        if not resp.ok:
            self._logger.error(
                json.dumps({
                    "event": "skyscrapper_client_error",
                    "route": route,
                    "status": resp.status_code,
                })
            )
            return []

        try:
            body = resp.json()
        except ValueError as exc:
            raise ScraperError(
                f"Sky Scrapper non-JSON response for route {route}"
            ) from exc

        itineraries = (body.get("data") or {}).get("itineraries", [])
        if not itineraries:
            self._logger.info(
                json.dumps({
                    "event": "skyscrapper_no_flights",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                })
            )
            return []

        self._logger.info(
            json.dumps({
                "event": "skyscrapper_response",
                "route": route,
                "itineraries_received": len(itineraries),
            })
        )
        return self._parse_itineraries(itineraries, route, travel_date, max_results)

    def _parse_itineraries(
        self,
        itineraries: list[object],
        route: str,
        travel_date: date,
        max_results: int,
    ) -> list[ScrapedFare]:
        """Parse Sky Scrapper itinerary objects into sorted ScrapedFare list.

        Args:
            itineraries: Raw itinerary dicts from response["data"]["itineraries"].
            route: Route string.
            travel_date: Departure date.
            max_results: Return at most this many fares (cheapest first).

        Returns:
            Up to *max_results* valid :class:`ScrapedFare` objects.
        """
        fares: list[ScrapedFare] = []
        now = utcnow()

        for itin in itineraries:
            fare = self._parse_single_itinerary(itin, route, travel_date, now)
            if fare is not None:
                fares.append(fare)

        # Sort cheapest first, return top N
        fares.sort(key=lambda f: f.price_inr)
        return fares[:max_results]

    def _parse_single_itinerary(
        self,
        itin: object,
        route: str,
        travel_date: date,
        now: datetime,
    ) -> Optional[ScrapedFare]:
        """Convert one Sky Scrapper itinerary dict to a ScrapedFare.

        Returns ``None`` on any parse failure (logs DEBUG).
        """
        try:
            if not isinstance(itin, dict):
                return None

            raw_price = itin.get("price", {}).get("raw")
            if raw_price is None:
                return None
            price_inr = int(float(raw_price))
            if price_inr <= 0:
                return None

            legs = itin.get("legs", [])
            if not legs:
                return None
            leg = legs[0]

            marketing = (leg.get("carriers") or {}).get("marketing", [])
            raw_airline = (marketing[0].get("name", "") if marketing else "") or ""
            try:
                airline = _normalise_airline(raw_airline) if raw_airline else "Unknown"
            except ValueError:
                airline = "Unknown"

            stops = int(leg.get("stopCount", 0))

            return ScrapedFare(
                route=route,
                travel_date=travel_date,
                price_inr=price_inr,
                airline=airline,
                stops=stops,
                source="skyscrapper",
                raw_price_str=str(raw_price),
                scraped_at=now,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            self._logger.debug(
                json.dumps({
                    "event": "fare_validation_failed",
                    "route": route,
                    "source": "skyscrapper",
                    "reason": str(exc),
                })
            )
            return None


# ─── GEMINI MARKDOWN FARE EXTRACTOR ─────────────────────────────────────────


def _extract_fares_from_markdown(
    markdown: str,
    route: str,
    travel_date: date,
) -> str:
    """Use Gemini Flash to extract a JSON fare array from raw markdown content.

    Called when TinyFish Fetch returns markdown page content (not a JSON array).
    Sends the content to Gemini 2.5 Flash with the SCRAPER_SYSTEM_PROMPT and
    returns the raw JSON array string for downstream parsing.

    Args:
        markdown: Raw markdown/text content from TinyFish Fetch.
        route: Route string for logging context.
        travel_date: Departure date (embedded in prompt for context).

    Returns:
        A JSON array string e.g. '[{"price_inr": 3240, ...}]' or '[]'.

    Raises:
        TinyFishInvalidResponseError: If Gemini fails or returns no usable content.
    """
    from google import genai as google_genai
    import os

    _log_tf.info(
        json.dumps({
            "event": "gemini_fare_extraction_started",
            "route": route,
            "markdown_length": len(markdown),
        })
    )

    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise TinyFishInvalidResponseError(
            "GEMINI_API_KEY not set; cannot extract fares from markdown."
        )

    client = google_genai.Client(api_key=api_key)

    date_str = travel_date.strftime("%d %B %Y")
    full_prompt = (
        f"{SCRAPER_SYSTEM_PROMPT}\n\n"
        f"Extract flight fares for route {route} departing {date_str} "
        f"from the following page content. "
        f"Return ONLY a valid JSON array.\n\n"
        f"PAGE CONTENT:\n{markdown[:12000]}"
    )

    # Try models in order — fall back if primary is overloaded (503) or quota-exhausted (429)
    _models_to_try = ["gemini-2.5-flash", "gemini-2.0-flash"]
    last_exc: Exception = Exception("No models tried")

    for model_name in _models_to_try:
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=full_prompt,
            )
            raw_text = response.text.strip()
            _log_tf.info(
                json.dumps({
                    "event": "gemini_fare_extraction_complete",
                    "route": route,
                    "model": model_name,
                    "response_length": len(raw_text),
                })
            )
            return raw_text
        except Exception as exc:
            _log_tf.warning(
                json.dumps({
                    "event": "gemini_model_failed",
                    "route": route,
                    "model": model_name,
                    "error": str(exc)[:200],
                    "action": "trying_next_model",
                })
            )
            last_exc = exc
            import time as _time
            _time.sleep(2)

    raise TinyFishInvalidResponseError(
        f"All Gemini models failed for route {route}: {last_exc}"
    ) from last_exc




# ─── ROUTE SCRAPER AGENT (TIER 2) ────────────────────────────────────────────



class RouteScraperAgent:
    """Responsible for scraping ONE route+date pair.

    Priority order:
      1. TinyFish Browser  → Skyscanner       (if daily browser limit not reached)
      2. TinyFish Fetch    → Google Flights   (if daily fetch limit not reached)
      3. Sky Scrapper API  → RapidAPI fallback (if daily limit not reached)
      4. All sources exhausted → return error result, do NOT raise

    After getting fares from any source:
      - Filter fares where travel_date < today (stale data)
      - Filter duplicates via in-memory dedup set
      - Insert surviving fares via queries.insert_price_observation()
    """

    def __init__(
        self,
        rate_limiter: RateLimiter,
        tinyfish_client: Optional[TinyFishClient] = None,
        skyscrapper_client: Optional[SkyScrappperClient] = None,
        # Legacy alias kept for test injection compatibility
        amadeus_client: Optional[SkyScrappperClient] = None,
        dedup_set: Optional[set[str]] = None,
    ) -> None:
        self._rl = rate_limiter
        self._tf = tinyfish_client or TinyFishClient()
        # Support both kwarg names: skyscrapper_client takes precedence
        self._ss = skyscrapper_client or amadeus_client or SkyScrappperClient()
        self._dedup: set[str] = dedup_set if dedup_set is not None else set()
        self._logger = _log_route

    def scrape_route(
        self, route: str, travel_date: date
    ) -> RouteScapeResult:
        """Attempt to scrape one route+date pair, trying all sources in order.

        Args:
            route: Route string e.g. ``"NAG-DEL"``.
            travel_date: Departure date.

        Returns:
            :class:`RouteScapeResult` — always returns, never raises.

        Side effects:
            Inserts valid fares into the database via
            ``queries.insert_price_observation()``.
        """
        t_start = time.perf_counter()
        self._logger.info(
            json.dumps({
                "event": "route_scrape_started",
                "route": route,
                "travel_date": travel_date.isoformat(),
            })
        )

        try:
            _validate_route(route)
            _validate_travel_date(travel_date)
        except ValueError as exc:
            return self._error_result(route, travel_date, str(exc), t_start)

        fares, source_used, fallback_used = self._try_all_sources(route, travel_date)

        if fares is None:
            reason = "All data sources exhausted — no fares obtained."
            self._logger.error(
                json.dumps({
                    "event": "route_scrape_failed",
                    "route": route,
                    "travel_date": travel_date.isoformat(),
                    "reason": reason,
                    "all_sources_tried": True,
                })
            )
            return self._error_result(route, travel_date, reason, t_start)

        valid_fares = self._filter_fares(fares, route, travel_date)
        fares_stored = self._store_fares(valid_fares, route)

        duration = time.perf_counter() - t_start
        self._logger.info(
            json.dumps({
                "event": "route_scrape_complete",
                "route": route,
                "travel_date": travel_date.isoformat(),
                "fares_found": len(valid_fares),
                "fares_stored": fares_stored,
                "source": source_used,
                "fallback_used": fallback_used,
                "duration_seconds": round(duration, 2),
            })
        )
        return RouteScapeResult(
            route=route,
            travel_date=travel_date,
            fares_found=len(valid_fares),
            fares_stored=fares_stored,
            source_used=source_used,
            fallback_used=fallback_used,
            error=None,
            duration_seconds=duration,
        )

    def _try_all_sources(
        self, route: str, travel_date: date
    ) -> tuple[Optional[list[ScrapedFare]], str, bool]:
        """Try each source in priority order.

        Args:
            route: Route string.
            travel_date: Departure date.

        Returns:
            Tuple of (fares_or_None, source_name, fallback_used).
            Returns ``(None, "", False)`` if all sources exhausted.
        """
        origin, destination = route.split("-")

        # ── Source 1: TinyFish Browser (Skyscanner) ──────────────────────────
        if self._rl.can_use_tinyfish_browser():
            fares = self._try_tinyfish_browser(origin, destination, travel_date, route)
            if fares is not None:
                self._rl.record_tinyfish_call("browser")
                return fares, "skyscanner", False
        else:
            self._logger.info(
                json.dumps({
                    "event": "tinyfish_browser_limit_reached",
                    "route": route,
                    "action": "skipping_to_fetch",
                })
            )

        # ── Source 2: TinyFish Fetch (Google Flights) ─────────────────────────
        if self._rl.can_use_tinyfish_fetch():
            fares = self._try_tinyfish_fetch(origin, destination, travel_date, route)
            if fares is not None:
                self._rl.record_tinyfish_call("fetch")
                return fares, "google_flights", False
        else:
            self._logger.info(
                json.dumps({
                    "event": "tinyfish_fetch_limit_reached",
                    "route": route,
                    "action": "skipping_to_skyscrapper",
                })
            )

        # ── Source 3: Sky Scrapper fallback ────────────────────────────────────
        self._logger.info(
            json.dumps({
                "event": "tinyfish_exhausted",
                "route": route,
                "fallback": "skyscrapper",
            })
        )
        if self._rl.can_use_skyscrapper():
            fares = self._try_skyscrapper(route, travel_date)
            if fares is not None:
                self._rl.record_skyscrapper_call()
                self._logger.info(
                    json.dumps({
                        "event": "skyscrapper_fallback_used",
                        "route": route,
                        "reason": "TinyFish sources exhausted",
                    })
                )
                return fares, "skyscrapper", True

        return None, "", False

    def _try_tinyfish_browser(
        self, origin: str, destination: str, travel_date: date, route: str
    ) -> Optional[list[ScrapedFare]]:
        """Attempt Skyscanner scrape via TinyFish Browser.

        Returns:
            List of fares on success, ``None`` on any failure.
        """
        goal = _build_skyscanner_goal(origin, destination, travel_date)
        try:
            raw = self._tf.call_browser(goal, route)
            fares = _parse_tinyfish_response(raw, route, travel_date, "skyscanner")
            return fares
        except (
            TinyFishRateLimitError,
            TinyFishTimeoutError,
            TinyFishInvalidResponseError,
            ScraperError,
        ) as exc:
            self._logger.warning(
                json.dumps({
                    "event": "tinyfish_browser_failed",
                    "route": route,
                    "error": str(exc),
                    "next": "trying_fetch",
                })
            )
            return None

    def _try_tinyfish_fetch(
        self, origin: str, destination: str, travel_date: date, route: str
    ) -> Optional[list[ScrapedFare]]:
        """Attempt Google Flights scrape via TinyFish Fetch.

        TinyFish Fetch returns raw markdown page content — NOT a JSON array.
        We pass that markdown to Gemini Flash which extracts fare data as JSON.

        Returns:
            List of fares on success, ``None`` on any failure.
        """
        goal = _build_google_flights_goal(origin, destination, travel_date)
        try:
            markdown_content = self._tf.call_fetch(goal, route)

            # Fetch returns markdown — use Gemini Flash to extract fares
            fare_json_str = _extract_fares_from_markdown(
                markdown_content, route, travel_date
            )
            fares = _parse_tinyfish_response(
                fare_json_str, route, travel_date, "google_flights"
            )
            return fares
        except (
            TinyFishRateLimitError,
            TinyFishTimeoutError,
            TinyFishInvalidResponseError,
            ScraperError,
        ) as exc:
            self._logger.warning(
                json.dumps({
                    "event": "tinyfish_fetch_failed",
                    "route": route,
                    "error": str(exc),
                    "next": "trying_skyscrapper",
                })
            )
            return None
        except Exception as exc:
            self._logger.warning(
                json.dumps({
                    "event": "tinyfish_fetch_llm_extraction_failed",
                    "route": route,
                    "error": str(exc),
                    "next": "trying_skyscrapper",
                })
            )
            return None

    def _try_skyscrapper(
        self, route: str, travel_date: date
    ) -> Optional[list[ScrapedFare]]:
        """Attempt Sky Scrapper API fallback fetch.

        Returns:
            List of fares on success, ``None`` on total failure.
        """
        try:
            return self._ss.fetch_fares(route, travel_date)
        except (SkyScrapprrAPIError, ScraperError) as exc:
            self._logger.error(
                json.dumps({
                    "event": "skyscrapper_failed",
                    "route": route,
                    "error": str(exc),
                })
            )
            return None

    def _filter_fares(
        self, fares: list[ScrapedFare], route: str, travel_date: date
    ) -> list[ScrapedFare]:
        """Remove past-date fares and in-memory duplicates.

        Args:
            fares: Raw fares from a source.
            route: Route string (for logging).
            travel_date: Expected departure date.

        Returns:
            Filtered list of valid, non-duplicate fares.
        """
        today = datetime.now(UTC).date()
        valid: list[ScrapedFare] = []

        for fare in fares:
            if fare.travel_date < today:
                self._logger.warning(
                    json.dumps({
                        "event": "past_fare_dropped",
                        "route": route,
                        "fare_travel_date": fare.travel_date.isoformat(),
                        "today": today.isoformat(),
                    })
                )
                continue

            key = _make_dedup_key(fare)
            if key in self._dedup:
                self._logger.debug(
                    json.dumps({
                        "event": "duplicate_fare_dropped",
                        "route": route,
                        "price_inr": fare.price_inr,
                        "airline": fare.airline,
                    })
                )
                continue

            self._dedup.add(key)
            valid.append(fare)

        return valid

    def _store_fares(self, fares: list[ScrapedFare], route: str) -> int:
        """Insert fares into the database.

        Args:
            fares: Validated, deduplicated fares.
            route: Route string for logging.

        Returns:
            Number of fares successfully inserted.
        """
        stored = 0
        for fare in fares:
            try:
                row_id = queries.insert_price_observation(
                    route=fare.route,
                    travel_date=fare.travel_date,
                    price_inr=fare.price_inr,
                    airline=fare.airline,
                    stops=fare.stops,
                    source=fare.source,
                )
                self._logger.debug(
                    json.dumps({
                        "event": "fare_stored",
                        "route": route,
                        "price_inr": fare.price_inr,
                        "airline": fare.airline,
                        "row_id": row_id,
                    })
                )
                stored += 1
            except Exception as exc:
                self._logger.error(
                    json.dumps({
                        "event": "fare_store_failed",
                        "route": route,
                        "price_inr": fare.price_inr,
                        "airline": fare.airline,
                        "error": str(exc),
                    })
                )
        return stored

    def _error_result(
        self, route: str, travel_date: date, reason: str, t_start: float
    ) -> RouteScapeResult:
        return RouteScapeResult(
            route=route,
            travel_date=travel_date,
            fares_found=0,
            fares_stored=0,
            source_used="",
            fallback_used=False,
            error=reason,
            duration_seconds=time.perf_counter() - t_start,
        )


# ─── SCRAPER ORCHESTRATOR (TIER 1) ────────────────────────────────────────────


class ScraperOrchestrator:
    """Manages a complete scrape run across all active monitored routes.

    Lifecycle:
      1. ``__init__``: load active routes from DB.
      2. ``run()``: iterate all route+date pairs, scrape each, collect results.
      3. After all routes: call ``queries.update_price_stats()`` for routes
         that received at least 1 new fare.
      4. Return :class:`ScrapeRunResult`.

    Key behaviours:
      - Routes where ``can_scrape_route()`` returns ``False`` are skipped (DEBUG).
      - A failed route must NOT stop other routes from running.
      - After a successful scrape: ``record_scrape()`` is called immediately.
      - Between each route: random 8–15s jitter sleep (anti-detection).
      - Fares with past ``travel_date`` are silently dropped in RouteScraperAgent.
      - Duplicate fares are deduped via a shared in-memory set.
    """

    def __init__(self) -> None:
        self._rl = RateLimiter()
        self._dedup: set[str] = set()
        self._route_agent = RouteScraperAgent(
            rate_limiter=self._rl, dedup_set=self._dedup
        )
        self._routes: list[dict] = []
        self._logger = _log_orch

    def run(self) -> ScrapeRunResult:
        """Execute a full scrape run across all active routes.

        Returns:
            :class:`ScrapeRunResult` with aggregated counts and per-route results.

        Side effects:
            Inserts price observations into DB. Recalculates price_stats for
            routes that received new data. Updates rate limiter state file.
        """
        started_at = utcnow()
        self._logger.info(
            json.dumps({
                "event": "scrape_run_started",
                "started_at": to_iso(started_at),
            })
        )

        self._routes = queries.get_all_active_routes()
        self._logger.info(
            json.dumps({
                "event": "routes_loaded",
                "routes_count": len(self._routes),
            })
        )

        route_results: list[RouteScapeResult] = []
        routes_succeeded = 0
        routes_failed = 0
        total_fares_scraped = 0
        total_fares_stored = 0
        fallback_count = 0
        errors: list[str] = []
        routes_with_new_data: list[tuple[str, date]] = []

        all_pairs = self._expand_route_date_pairs()

        for idx, (route, travel_date) in enumerate(all_pairs):
            if not self._rl.can_scrape_route(route, travel_date):
                self._logger.debug(
                    json.dumps({
                        "event": "route_on_cooldown_skipped",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                    })
                )
                continue

            result = self._route_agent.scrape_route(route, travel_date)
            route_results.append(result)

            if result.error is None:
                routes_succeeded += 1
                self._rl.record_scrape(route, travel_date)
                if result.fares_stored > 0:
                    routes_with_new_data.append((route, travel_date))
            else:
                routes_failed += 1
                errors.append(result.error)

            total_fares_scraped += result.fares_found
            total_fares_stored += result.fares_stored
            if result.fallback_used:
                fallback_count += 1

            # Anti-detection jitter between routes
            if idx < len(all_pairs) - 1:
                sleep_sec = random.uniform(2.0, 4.0)  # reduced: Fetch API, not browser
                self._logger.debug(
                    json.dumps({
                        "event": "inter_route_sleep",
                        "sleep_seconds": round(sleep_sec, 1),
                    })
                )
                time.sleep(sleep_sec)

        self._recalculate_stats(routes_with_new_data)

        finished_at = utcnow()
        duration = (finished_at - started_at).total_seconds()

        self._logger.info(
            json.dumps({
                "event": "scrape_run_complete",
                "routes_attempted": len(route_results),
                "routes_succeeded": routes_succeeded,
                "total_fares_stored": total_fares_stored,
                "duration_seconds": round(duration, 1),
            })
        )

        return ScrapeRunResult(
            started_at=started_at,
            finished_at=finished_at,
            routes_attempted=len(route_results),
            routes_succeeded=routes_succeeded,
            routes_failed=routes_failed,
            total_fares_scraped=total_fares_scraped,
            total_fares_stored=total_fares_stored,
            fallback_triggered_count=fallback_count,
            route_results=tuple(route_results),
            errors=tuple(errors),
        )

    def _expand_route_date_pairs(self) -> list[tuple[str, date]]:
        """Flatten active routes × travel_dates into a list of (route, date) pairs.

        Returns:
            List of tuples for iteration, skipping invalid date strings.
        """
        pairs: list[tuple[str, date]] = []
        for route_cfg in self._routes:
            route = route_cfg["route"]
            for date_str in route_cfg.get("travel_dates", []):
                try:
                    travel_date = date.fromisoformat(date_str)
                    pairs.append((route, travel_date))
                except ValueError:
                    self._logger.warning(
                        json.dumps({
                            "event": "invalid_travel_date_in_config",
                            "route": route,
                            "date_str": date_str,
                        })
                    )
        return pairs

    def _recalculate_stats(
        self, routes_with_new_data: list[tuple[str, date]]
    ) -> None:
        """Recalculate price_stats for each route+date that received new fares.

        Args:
            routes_with_new_data: List of (route, travel_date) tuples.

        Side effects:
            Upserts rows in the price_stats table.
        """
        for route, travel_date in routes_with_new_data:
            try:
                stats = queries.update_price_stats(route, travel_date)
                self._logger.info(
                    json.dumps({
                        "event": "stats_recalculated",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "new_p10": stats.p10_price,
                        "new_observation_count": stats.observation_count,
                    })
                )
            except Exception as exc:
                self._logger.error(
                    json.dumps({
                        "event": "stats_recalculation_failed",
                        "route": route,
                        "travel_date": travel_date.isoformat(),
                        "error": str(exc),
                    })
                )
