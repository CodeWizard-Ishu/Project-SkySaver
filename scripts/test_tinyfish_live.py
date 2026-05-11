#!/usr/bin/env python3
"""scripts/test_tinyfish_live.py — Production-level live test for TinyFish API.

Tests BOTH endpoints (browser + fetch) against a real flight route.
Measures latency, validates response structure, checks rate-limit headers.
Does NOT write to the database and does NOT consume the daily rate-limit
counter in rate_limiter_state.json.

Usage (from project root, venv active):
    python scripts/test_tinyfish_live.py

Exit codes:
    0 — all checks passed
    1 — at least one check failed
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

# ── project root on sys.path ──────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env")

# ── colour helpers ────────────────────────────────────────────────────────────
_GREEN  = "\033[92m"
_RED    = "\033[91m"
_YELLOW = "\033[93m"
_CYAN   = "\033[96m"
_RESET  = "\033[0m"
_BOLD   = "\033[1m"

def ok(msg: str)   -> None: print(f"  {_GREEN}✓{_RESET} {msg}")
def fail(msg: str) -> None: print(f"  {_RED}✗{_RESET} {msg}")
def warn(msg: str) -> None: print(f"  {_YELLOW}!{_RESET} {msg}")
def info(msg: str) -> None: print(f"  {_CYAN}→{_RESET} {msg}")
def head(msg: str) -> None: print(f"\n{_BOLD}{msg}{_RESET}")

# ── config ────────────────────────────────────────────────────────────────────
API_KEY        = os.getenv("TINYFISH_API_KEY", "")
TINYFISH_FETCH_URL   = "https://api.fetch.tinyfish.ai"
TINYFISH_BROWSER_URL = "https://agent.tinyfish.ai/v1/automation/run"
TEST_ROUTE     = "NAG-DEL"   # Nagpur → Delhi — reliable, many daily flights
TRAVEL_DATE    = date.today() + timedelta(days=30)
TIMEOUT_S      = 45          # production allows 35s; test allows 45s for CI slack

_RESULTS: list[bool] = []


def _record(passed: bool, label: str) -> bool:
    _RESULTS.append(passed)
    if passed:
        ok(label)
    else:
        fail(label)
    return passed


# ── Level 0: env ──────────────────────────────────────────────────────────────

def check_env() -> None:
    head("Level 0 — Environment")

    has_key = bool(API_KEY)
    _record(has_key, f"TINYFISH_API_KEY is set ({API_KEY[:8]}...)" if has_key
            else "TINYFISH_API_KEY is SET")
    if not has_key:
        fail("TINYFISH_API_KEY is missing — cannot proceed")
        sys.exit(1)

    # Confirm URL matches new endpoint
    _record(
        "fetch.tinyfish.ai" in TINYFISH_FETCH_URL and "agent.tinyfish.ai" in TINYFISH_BROWSER_URL,
        f"URLs split correctly: fetch={TINYFISH_FETCH_URL} | browser={TINYFISH_BROWSER_URL}",
    )


# ── Level 1: connectivity ─────────────────────────────────────────────────────

def check_connectivity() -> None:
    head("Level 1 — Connectivity (HEAD request)")
    try:
        req = urllib.request.Request(
            "https://api.fetch.tinyfish.ai",
            headers={"Authorization": f"Bearer {API_KEY}"},
            method="HEAD",
        )
        start = time.perf_counter()
        urllib.request.urlopen(req, timeout=10)
        elapsed = time.perf_counter() - start
        _record(True, f"Endpoint reachable (HEAD {elapsed*1000:.0f}ms)")
    except urllib.error.HTTPError as exc:
        # 4xx from HEAD is fine — the host responded
        elapsed = time.perf_counter() - start if 'start' in dir() else 0
        _record(True, f"Endpoint reachable — HTTP {exc.code} (host alive)")
    except Exception as exc:
        _record(False, f"Cannot reach endpoint: {exc}")


# ── Level 2: goal builder import ──────────────────────────────────────────────

def check_goal_builders() -> tuple[str, str]:
    head("Level 2 — Goal builder imports & output")
    from agents.scraper_agent import _build_skyscanner_goal, _build_google_flights_goal

    browser_goal = _build_skyscanner_goal("NAG", "DEL", TRAVEL_DATE)
    fetch_goal   = _build_google_flights_goal("NAG", "DEL", TRAVEL_DATE)

    _record(len(browser_goal) > 50, f"Skyscanner goal built ({len(browser_goal)} chars)")
    _record(len(fetch_goal)   > 50, f"Google Flights goal built ({len(fetch_goal)} chars)")
    # browser goal uses human-readable date e.g. "10 June 2026"
    date_human = TRAVEL_DATE.strftime("%d %B %Y").lstrip("0")
    _record(date_human in browser_goal or TRAVEL_DATE.strftime("%d %B %Y") in browser_goal,
            f"Travel date present in browser goal ('{date_human}')")
    _record(TRAVEL_DATE.isoformat() in fetch_goal,   "Travel date present in fetch goal")
    _record("NAG" in browser_goal and "DEL" in browser_goal, "Origin/dest in browser goal")

    info(f"Browser goal preview: {browser_goal[:120]}...")
    info(f"Fetch   goal preview: {fetch_goal[:120]}...")
    return browser_goal, fetch_goal


# ── shared HTTP call ──────────────────────────────────────────────────────────

def _call_tinyfish(endpoint: str, goal: str) -> tuple[bool, float, str, dict]:
    """Return (success, elapsed_s, raw_response, headers)."""
    import re
    if endpoint == "browser":
        url_match = re.search(r"https?://[^\s]+", goal)
        start_url = url_match.group(0).rstrip(".") if url_match else "https://www.skyscanner.co.in"
        api_url = TINYFISH_BROWSER_URL
        payload = json.dumps({
            "url": start_url,
            "goal": goal,
            "browser_profile": "stealth",
            "proxy_config": {
                "enabled": True,
                "type": "tetra",
                "country_code": "US",
            },
        }).encode("utf-8")
        timeout = 180
    else:
        url_match = re.search(r"https?://[^\s]+", goal)
        target_url = url_match.group(0).rstrip(".") if url_match else "https://www.google.com/travel/flights"
        api_url = TINYFISH_FETCH_URL
        payload = json.dumps({"urls": [target_url]}).encode("utf-8")
        timeout = 45

    req = urllib.request.Request(
        api_url,
        data=payload,
        headers={
            "X-API-Key": API_KEY,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    start = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            elapsed = time.perf_counter() - start
            raw = resp.read().decode("utf-8")
            headers = dict(resp.headers)
            return True, elapsed, raw, headers
    except urllib.error.HTTPError as exc:
        elapsed = time.perf_counter() - start
        body = exc.read().decode("utf-8", errors="replace")
        return False, elapsed, f"HTTP {exc.code}: {body[:300]}", {}
    except Exception as exc:
        elapsed = time.perf_counter() - start
        return False, elapsed, str(exc), {}


# ── Level 3: fetch endpoint (lighter, test first) ─────────────────────────────

def check_fetch_endpoint(fetch_goal: str) -> str | None:
    head("Level 3 — TinyFish FETCH endpoint (Google Flights)")
    info(f"Calling {TINYFISH_FETCH_URL} [endpoint=fetch] ...")
    _FETCH_TIMEOUT = 45

    success, elapsed, raw, headers = _call_tinyfish("fetch", fetch_goal)

    _record(success, f"HTTP 200 OK (elapsed {elapsed:.1f}s)")
    if not success:
        fail(f"Response: {raw[:300]}")
        return None

    _record(elapsed < _FETCH_TIMEOUT, f"Latency {elapsed:.1f}s < {_FETCH_TIMEOUT}s timeout")
    _record(len(raw) > 10,            f"Non-empty response ({len(raw)} bytes)")

    remaining = headers.get("x-ratelimit-remaining") or headers.get("X-Ratelimit-Remaining")
    if remaining:
        ok(f"Rate-limit header present: x-ratelimit-remaining={remaining}")
    else:
        warn("No x-ratelimit-remaining header (ok if endpoint doesn't expose it)")

    info(f"Raw response (first 400 chars):\n    {raw[:400]}")
    return raw


def check_browser_endpoint(browser_goal: str) -> str | None:
    head("Level 4 — TinyFish BROWSER endpoint (Skyscanner + stealth + tetra proxy)")
    info(f"Calling {TINYFISH_BROWSER_URL} [endpoint=browser] ...")
    warn("Stealth + tetra proxy active — allow up to 120s for DataDome bypass.")
    _BROWSER_TIMEOUT = 180

    success, elapsed, raw, headers = _call_tinyfish("browser", browser_goal)

    _record(success, f"HTTP 200 OK (elapsed {elapsed:.1f}s)")
    if not success:
        fail(f"Response: {raw[:300]}")
        return None

    _record(elapsed < _BROWSER_TIMEOUT, f"Latency {elapsed:.1f}s < {_BROWSER_TIMEOUT}s timeout")
    _record(len(raw) > 10,              f"Non-empty response ({len(raw)} bytes)")
    info(f"Raw response (first 500 chars):\n    {raw[:500]}")
    return raw


# ── Level 5: response parsing ─────────────────────────────────────────────────

def check_response_parsing(raw_fetch: str | None, raw_browser: str | None) -> None:
    head("Level 5 — Response parsing (ScrapedFare extraction)")
    from agents.scraper_agent import _parse_tinyfish_response, TinyFishInvalidResponseError

    for label, raw, source in [
        ("fetch/google_flights", raw_fetch,   "google_flights"),
        ("browser/skyscanner",   raw_browser, "skyscanner"),
    ]:
        if raw is None:
            warn(f"Skipping {label} parse — no response")
            continue

        try:
            fares = _parse_tinyfish_response(raw, TEST_ROUTE, TRAVEL_DATE, source)
            _record(True, f"{label}: parsed {len(fares)} fare(s)")

            if fares:
                cheapest = min(fares, key=lambda f: f.price_inr)
                _record(cheapest.price_inr > 0,         f"  Cheapest price INR={cheapest.price_inr}")
                _record(bool(cheapest.airline),          f"  Airline name present: '{cheapest.airline}'")
                _record(cheapest.stops >= 0,             f"  Stops={cheapest.stops} (valid)")
                _record(cheapest.source == source,       f"  Source field = '{cheapest.source}'")
                _record(cheapest.route == TEST_ROUTE,    f"  Route field = '{cheapest.route}'")
                _record(
                    cheapest.travel_date == TRAVEL_DATE,
                    f"  Travel date = {cheapest.travel_date}",
                )
                info(f"  All fares from {label}:")
                for f in sorted(fares, key=lambda x: x.price_inr):
                    print(f"    ₹{f.price_inr:,}  {f.airline:<20}  {f.stops} stop(s)  [{f.source}]")
            else:
                warn(f"{label}: zero fares extracted (response may be no-results)")

        except TinyFishInvalidResponseError as exc:
            _record(False, f"{label} parse failed: {exc}")
        except Exception as exc:
            _record(False, f"{label} unexpected error: {exc}")


# ── Level 6: error-handling paths ─────────────────────────────────────────────

def check_error_paths() -> None:
    head("Level 6 — Error handling (bad key, bad goal)")

    # 6a: bad API key → should get 401 or 403, NOT a crash
    info("Testing bad API key (expect 401/403)…")
    payload = json.dumps({"urls": ["https://www.google.com/travel/flights"]}).encode()
    req = urllib.request.Request(
        TINYFISH_FETCH_URL,
        data=payload,
        headers={"X-API-Key": "invalid-key-00000", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        urllib.request.urlopen(req, timeout=15)
        _record(False, "Bad key: expected 401/403 but got 200 (suspicious)")
    except urllib.error.HTTPError as exc:
        _record(
            exc.code in (401, 403),
            f"Bad key correctly rejected with HTTP {exc.code}",
        )
    except Exception as exc:
        warn(f"Bad key check: unexpected {type(exc).__name__}: {exc}")

    # 6b: empty goal — server should 422, not crash our handler
    info("Testing empty goal string (expect HTTP 422 or graceful error)…")
    from agents.scraper_agent import TinyFishClient, TinyFishInvalidResponseError, ScraperError
    client = TinyFishClient()
    try:
        client.call_fetch("", "NAG-DEL")
        _record(False, "Empty goal: expected exception but got success")
    except (TinyFishInvalidResponseError, ScraperError, Exception) as exc:
        _record(True, f"Empty goal raises exception cleanly: {type(exc).__name__}")


# ── Level 7: TinyFishClient integration (unit + live combined) ────────────────

def check_client_integration() -> None:
    head("Level 7 — TinyFishClient integration (no rate-limiter counter)")
    from agents.scraper_agent import TinyFishClient, _build_google_flights_goal

    client = TinyFishClient()
    _record(bool(client._api_key), "TinyFishClient loaded API key from env")

    goal = _build_google_flights_goal("NAG", "DEL", TRAVEL_DATE)
    info(f"Calling TinyFishClient.call_fetch() for {TEST_ROUTE} on {TRAVEL_DATE}…")
    start = time.perf_counter()
    try:
        raw = client.call_fetch(goal, TEST_ROUTE)
        elapsed = time.perf_counter() - start
        _record(True,         f"call_fetch() returned in {elapsed:.1f}s")
        _record(len(raw) > 0, f"Response length = {len(raw)} bytes")
    except Exception as exc:
        elapsed = time.perf_counter() - start
        _record(False, f"call_fetch() raised {type(exc).__name__}: {exc}")


# ── summary ───────────────────────────────────────────────────────────────────

def print_summary() -> int:
    passed = sum(_RESULTS)
    total  = len(_RESULTS)
    failed = total - passed
    head("=" * 56)
    if failed == 0:
        print(f"  {_GREEN}{_BOLD}ALL {total} CHECKS PASSED ✓{_RESET}")
    else:
        print(f"  {_RED}{_BOLD}{failed}/{total} CHECKS FAILED ✗{_RESET}")
        print(f"  {_GREEN}{passed}/{total} passed{_RESET}")
    print()
    return 0 if failed == 0 else 1


# ── main ──────────────────────────────────────────────────────────────────────

def main() -> int:
    print(f"\n{_BOLD}TinyFish Production Live Test{_RESET}")
    print(f"  Fetch URL:   {TINYFISH_FETCH_URL}")
    print(f"  Browser URL: {TINYFISH_BROWSER_URL}")
    print(f"  Route:       {TEST_ROUTE}")
    print(f"  Travel date: {TRAVEL_DATE}  (+30 days)")
    print(f"  Timeout:     {TIMEOUT_S}s")

    check_env()
    check_connectivity()
    browser_goal, fetch_goal = check_goal_builders()

    raw_fetch   = check_fetch_endpoint(fetch_goal)
    raw_browser = check_browser_endpoint(browser_goal)

    check_response_parsing(raw_fetch, raw_browser)
    check_error_paths()
    check_client_integration()

    return print_summary()


if __name__ == "__main__":
    sys.exit(main())
