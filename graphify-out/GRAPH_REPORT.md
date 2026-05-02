# Graph Report - .  (2026-05-03)

## Corpus Check
- Corpus is ~14,395 words - fits in a single context window. You may not need a graph.

## Summary
- 398 nodes · 938 edges · 21 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 379 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Database Core & Alerts|Database Core & Alerts]]
- [[_COMMUNITY_Database Testing & Mocks|Database Testing & Mocks]]
- [[_COMMUNITY_Scraper Orchestration|Scraper Orchestration]]
- [[_COMMUNITY_Rate Limiting & Web Automation|Rate Limiting & Web Automation]]
- [[_COMMUNITY_Configuration & Logging|Configuration & Logging]]
- [[_COMMUNITY_Rate Limiter Logic|Rate Limiter Logic]]
- [[_COMMUNITY_Route Scraping Strategy|Route Scraping Strategy]]
- [[_COMMUNITY_Price Parsing & Errors|Price Parsing & Errors]]
- [[_COMMUNITY_Amadeus API Integration|Amadeus API Integration]]
- [[_COMMUNITY_Data Normalization|Data Normalization]]
- [[_COMMUNITY_Database Setup & Migration|Database Setup & Migration]]
- [[_COMMUNITY_TinyFish Response Parsing|TinyFish Response Parsing]]
- [[_COMMUNITY_Date Validation|Date Validation]]
- [[_COMMUNITY_Project Vision & Core Concepts|Project Vision & Core Concepts]]
- [[_COMMUNITY_Tech Stack & Dependencies|Tech Stack & Dependencies]]
- [[_COMMUNITY_Token Reset Logic (TinyFish)|Token Reset Logic (TinyFish)]]
- [[_COMMUNITY_Token Reset Logic (Amadeus)|Token Reset Logic (Amadeus)]]
- [[_COMMUNITY_Logger Utility|Logger Utility]]
- [[_COMMUNITY_AI Config (Flash)|AI Config (Flash)]]
- [[_COMMUNITY_AI Config (Pro)|AI Config (Pro)]]
- [[_COMMUNITY_Alert Decision logic|Alert Decision logic]]

## God Nodes (most connected - your core abstractions)
1. `RateLimiter` - 104 edges
2. `RouteScraperAgent` - 36 edges
3. `AmadeusClient` - 31 edges
4. `TinyFishRateLimitError` - 29 edges
5. `TinyFishClient` - 29 edges
6. `TinyFishInvalidResponseError` - 28 edges
7. `ScraperOrchestrator` - 28 edges
8. `AmadeusServerError` - 27 edges
9. `ScrapedFare` - 27 edges
10. `PriceParseError` - 26 edges

## Surprising Connections (you probably didn't know these)
- `RateLimiter` --uses--> `TinyFish returned HTTP 429.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Amadeus returned HTTP 5xx.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Could not extract a valid INR price from the raw string.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `One normalised flight fare from any data source.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Result of scraping one route+date pair.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py

## Hyperedges (group relationships)
- **Scraping Orchestration Pattern** — scraper_agent_scraperorchestrator, scraper_agent_routescraperagent, rate_limiter_ratelimiter [EXTRACTED 1.00]
- **Multi-Source Fallback Strategy** — scraper_agent_tinyfishclient, scraper_agent_amadeusclient, scraper_agent_routescraperagent [EXTRACTED 1.00]
- **Data Integrity and Persistence** — queries_insert_price_observation, queries_update_price_stats, rate_limiter_ratelimiter [INFERRED 0.85]

## Communities

### Community 0 - "Database Core & Alerts"
Cohesion: 0.07
Nodes (53): AlertCooldownError, AlertDecision, check_alert_cooldown(), close_connection(), _compute_percentile_rank(), DatabaseError, get_alert_decision(), get_all_active_routes() (+45 more)

### Community 1 - "Database Testing & Mocks"
Cohesion: 0.05
Nodes (12): _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)., Shortcut to insert one observation with sensible defaults., 10 threads each insert 5 rows — total must be 50, no corruption., TestAlertLog, TestGetAlertDecision, TestGetObservationCountByRoute (+4 more)

### Community 2 - "Scraper Orchestration"
Cohesion: 0.12
Nodes (36): AmadeusClient, AmadeusServerError, Manages a complete scrape run across all active monitored routes.      Lifecycle, TinyFish returned HTTP 429., Amadeus returned HTTP 5xx., One normalised flight fare from any data source., Aggregated result of a full scrape run across all routes., Thin wrapper around the TinyFish API with per-endpoint retry logic.      Retry s (+28 more)

### Community 3 - "Rate Limiting & Web Automation"
Cohesion: 0.08
Nodes (30): RateLimiter, Thread-safe rate limiter with JSON persistence across restarts.      All public, _build_google_flights_goal(), _build_skyscanner_goal(), _call_browser_with_retry(), _call_fetch_with_retry(), _extract_json_array(), _make_dedup_key() (+22 more)

### Community 4 - "Configuration & Logging"
Cohesion: 0.06
Nodes (31): get_claude_sonnet_config(), get_gemini_flash_config(), get_gemini_pro_config(), get_logger(), _JsonFormatter, load_env(), agents/base_agent.py — Shared base utilities for all SkySaver agents.  Provides:, Return a configured logger with JSON formatter.      Idempotent — calling this t (+23 more)

### Community 5 - "Rate Limiter Logic"
Cohesion: 0.08
Nodes (23): _empty_state(), agents/rate_limiter.py — Per-route and per-API rate limit enforcement.  Persists, Return ``True`` if enough time has elapsed since this route+date was scraped., Return ``True`` if TinyFish Browser calls today are below the safe limit., Return ``True`` if TinyFish Fetch calls today are below the safe limit., Return ``True`` if Amadeus API calls today are below the safe limit.          Au, Record that a scrape attempt just completed for this route+date.          Update, Increment the TinyFish call counter for *endpoint*.          Args:             e (+15 more)

### Community 6 - "Route Scraping Strategy"
Cohesion: 0.15
Nodes (11): Responsible for scraping ONE route+date pair.      Priority order:       1. Tiny, Attempt to scrape one route+date pair, trying all sources in order.          Arg, Try each source in priority order.          Args:             route: Route strin, Attempt Amadeus fallback fetch.          Returns:             List of fares on s, Remove past-date fares and in-memory duplicates.          Args:             fare, Insert fares into the database.          Args:             fares: Validated, ded, Result of scraping one route+date pair., RouteScapeResult (+3 more)

### Community 7 - "Price Parsing & Errors"
Cohesion: 0.22
Nodes (5): _parse_price_inr(), PriceParseError, Could not extract a valid INR price from the raw string., Extract an integer INR fare from a raw price string.      Handles every real-wor, TestParsePriceInr

### Community 8 - "Amadeus API Integration"
Cohesion: 0.17
Nodes (7): _fetch_with_retry(), Validate and parse a route string into (origin, destination).      Valid format:, Fetch flight offers from Amadeus and return normalised ScrapedFare list., Perform the Amadeus API call and parse the response.          Args:, Map Amadeus SDK exceptions to scraper exceptions or safe empty lists.          A, _validate_route(), TestValidateRoute

### Community 9 - "Data Normalization"
Cohesion: 0.23
Nodes (5): _normalise_airline(), _parse_single_tinyfish_fare(), Map a raw airline name to its canonical form.      Lookup is case-insensitive on, Attempt to parse one raw fare dict into a ScrapedFare.      Args:         item:, TestNormaliseAirline

### Community 10 - "Database Setup & Migration"
Cohesion: 0.18
Nodes (12): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), load_routes_from_config(), db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Parse config/routes.yaml and upsert every route into monitored_routes.      Args, Check that all 5 tables exist with all expected columns.      Returns:         T (+4 more)

### Community 11 - "TinyFish Response Parsing"
Cohesion: 0.31
Nodes (3): _parse_tinyfish_response(), Parse a raw TinyFish response string into a list of ScrapedFare.      Processing, TestParseTinyFishResponse

### Community 12 - "Date Validation"
Cohesion: 0.39
Nodes (3): Validate that *travel_date* is in the future and within 365 days.      Args:, _validate_travel_date(), TestValidateTravelDate

### Community 13 - "Project Vision & Core Concepts"
Cohesion: 0.29
Nodes (8): SkySaver Project, insert_price_observation, update_price_stats, RateLimiter, AmadeusClient, RouteScraperAgent, ScraperOrchestrator, TinyFishClient

### Community 14 - "Tech Stack & Dependencies"
Cohesion: 1.0
Nodes (2): AG2 (AutoGen), SkySaver Tech Stack

### Community 17 - "Token Reset Logic (TinyFish)"
Cohesion: 1.0
Nodes (1): Zero TinyFish counters if the stored date differs from today (UTC).

### Community 18 - "Token Reset Logic (Amadeus)"
Cohesion: 1.0
Nodes (1): Zero Amadeus counter if the stored date differs from today (UTC).

### Community 20 - "Logger Utility"
Cohesion: 1.0
Nodes (1): get_logger

### Community 21 - "AI Config (Flash)"
Cohesion: 1.0
Nodes (1): get_gemini_flash_config

### Community 22 - "AI Config (Pro)"
Cohesion: 1.0
Nodes (1): get_gemini_pro_config

### Community 23 - "Alert Decision logic"
Cohesion: 1.0
Nodes (1): get_alert_decision

## Knowledge Gaps
- **80 isolated node(s):** `db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth`, `Create all 5 tables and their indexes. Safe to run multiple times.      Raises:`, `Parse config/routes.yaml and upsert every route into monitored_routes.      Args`, `Check that all 5 tables exist with all expected columns.      Returns:         T`, `Raise PermissionError if the database directory is not writable.` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Tech Stack & Dependencies`** (2 nodes): `AG2 (AutoGen)`, `SkySaver Tech Stack`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Token Reset Logic (TinyFish)`** (1 nodes): `Zero TinyFish counters if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Token Reset Logic (Amadeus)`** (1 nodes): `Zero Amadeus counter if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Logger Utility`** (1 nodes): `get_logger`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AI Config (Flash)`** (1 nodes): `get_gemini_flash_config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `AI Config (Pro)`** (1 nodes): `get_gemini_pro_config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Alert Decision logic`** (1 nodes): `get_alert_decision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimiter` connect `Rate Limiting & Web Automation` to `Scraper Orchestration`, `Configuration & Logging`, `Rate Limiter Logic`, `Route Scraping Strategy`, `Price Parsing & Errors`, `Amadeus API Integration`, `Data Normalization`, `TinyFish Response Parsing`, `Date Validation`?**
  _High betweenness centrality (0.361) - this node is a cross-community bridge._
- **Why does `create_tables()` connect `Database Setup & Migration` to `Database Core & Alerts`, `Scraper Orchestration`?**
  _High betweenness centrality (0.317) - this node is a cross-community bridge._
- **Why does `fresh_db()` connect `Scraper Orchestration` to `Database Setup & Migration`?**
  _High betweenness centrality (0.270) - this node is a cross-community bridge._
- **Are the 89 inferred relationships involving `RateLimiter` (e.g. with `ScraperError` and `RouteScrapeFailed`) actually correct?**
  _`RateLimiter` has 89 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `RouteScraperAgent` (e.g. with `RateLimiter` and `TestParsePriceInr`) actually correct?**
  _`RouteScraperAgent` has 24 INFERRED edges - model-reasoned connections that need verification._
- **Are the 22 inferred relationships involving `AmadeusClient` (e.g. with `RateLimiter` and `TestParsePriceInr`) actually correct?**
  _`AmadeusClient` has 22 INFERRED edges - model-reasoned connections that need verification._
- **Are the 25 inferred relationships involving `TinyFishRateLimitError` (e.g. with `RateLimiter` and `TestParsePriceInr`) actually correct?**
  _`TinyFishRateLimitError` has 25 INFERRED edges - model-reasoned connections that need verification._