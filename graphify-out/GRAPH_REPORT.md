# Graph Report - .  (2026-05-11)

## Corpus Check
- Corpus is ~33,472 words - fits in a single context window. You may not need a graph.

## Summary
- 1012 nodes · 2298 edges · 74 communities detected
- Extraction: 55% EXTRACTED · 45% INFERRED · 0% AMBIGUOUS · INFERRED: 1037 edges (avg confidence: 0.55)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]
- [[_COMMUNITY_Community 12|Community 12]]
- [[_COMMUNITY_Community 13|Community 13]]
- [[_COMMUNITY_Community 14|Community 14]]
- [[_COMMUNITY_Community 15|Community 15]]
- [[_COMMUNITY_Community 16|Community 16]]
- [[_COMMUNITY_Community 17|Community 17]]
- [[_COMMUNITY_Community 18|Community 18]]
- [[_COMMUNITY_Community 19|Community 19]]
- [[_COMMUNITY_Community 20|Community 20]]
- [[_COMMUNITY_Community 21|Community 21]]
- [[_COMMUNITY_Community 22|Community 22]]
- [[_COMMUNITY_Community 23|Community 23]]
- [[_COMMUNITY_Community 24|Community 24]]
- [[_COMMUNITY_Community 25|Community 25]]
- [[_COMMUNITY_Community 26|Community 26]]
- [[_COMMUNITY_Community 27|Community 27]]
- [[_COMMUNITY_Community 28|Community 28]]
- [[_COMMUNITY_Community 29|Community 29]]
- [[_COMMUNITY_Community 30|Community 30]]
- [[_COMMUNITY_Community 31|Community 31]]
- [[_COMMUNITY_Community 32|Community 32]]
- [[_COMMUNITY_Community 33|Community 33]]
- [[_COMMUNITY_Community 34|Community 34]]
- [[_COMMUNITY_Community 40|Community 40]]
- [[_COMMUNITY_Community 41|Community 41]]
- [[_COMMUNITY_Community 42|Community 42]]
- [[_COMMUNITY_Community 43|Community 43]]
- [[_COMMUNITY_Community 44|Community 44]]
- [[_COMMUNITY_Community 45|Community 45]]
- [[_COMMUNITY_Community 46|Community 46]]
- [[_COMMUNITY_Community 47|Community 47]]
- [[_COMMUNITY_Community 48|Community 48]]
- [[_COMMUNITY_Community 49|Community 49]]
- [[_COMMUNITY_Community 50|Community 50]]
- [[_COMMUNITY_Community 51|Community 51]]
- [[_COMMUNITY_Community 52|Community 52]]
- [[_COMMUNITY_Community 53|Community 53]]
- [[_COMMUNITY_Community 54|Community 54]]
- [[_COMMUNITY_Community 56|Community 56]]
- [[_COMMUNITY_Community 57|Community 57]]
- [[_COMMUNITY_Community 58|Community 58]]
- [[_COMMUNITY_Community 59|Community 59]]
- [[_COMMUNITY_Community 60|Community 60]]
- [[_COMMUNITY_Community 61|Community 61]]
- [[_COMMUNITY_Community 62|Community 62]]
- [[_COMMUNITY_Community 63|Community 63]]
- [[_COMMUNITY_Community 64|Community 64]]
- [[_COMMUNITY_Community 65|Community 65]]
- [[_COMMUNITY_Community 66|Community 66]]
- [[_COMMUNITY_Community 67|Community 67]]
- [[_COMMUNITY_Community 68|Community 68]]
- [[_COMMUNITY_Community 69|Community 69]]
- [[_COMMUNITY_Community 70|Community 70]]
- [[_COMMUNITY_Community 71|Community 71]]
- [[_COMMUNITY_Community 72|Community 72]]
- [[_COMMUNITY_Community 73|Community 73]]
- [[_COMMUNITY_Community 74|Community 74]]
- [[_COMMUNITY_Community 75|Community 75]]
- [[_COMMUNITY_Community 76|Community 76]]
- [[_COMMUNITY_Community 77|Community 77]]
- [[_COMMUNITY_Community 78|Community 78]]
- [[_COMMUNITY_Community 79|Community 79]]

## God Nodes (most connected - your core abstractions)
1. `RateLimiter` - 190 edges
2. `ScraperOrchestrator` - 55 edges
3. `ScrapeRunResult` - 52 edges
4. `AnalysisReport` - 51 edges
5. `ForecastScore` - 51 edges
6. `RouteScraperAgent` - 50 edges
7. `ScrapeRunResponse` - 44 edges
8. `TinyFishRateLimitError` - 42 edges
9. `ScrapedFare` - 42 edges
10. `TinyFishClient` - 42 edges

## Surprising Connections (you probably didn't know these)
- `RateLimiter` --uses--> `Validate and parse a route string into (origin, destination).      Valid format:`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Extract an integer INR fare from a raw price string.      Handles every real-wor`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Map a raw airline name to its canonical form.      Lookup is case-insensitive on`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Attempt to parse one raw fare dict into a ScrapedFare.      Args:         item:`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Parse Amadeus offer objects into ScrapedFare list.          Args:             of`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py

## Hyperedges (group relationships)
- **LLM Configuration Strategy** — agents_get_gemini_flash_config, agents_get_gemini_pro_config, gemini_flash, gemini_pro, thinking_budget [EXTRACTED 0.95]

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (139): RateLimiter, Thread-safe rate limiter with JSON persistence across restarts.      All public, AmadeusClient, AmadeusServerError, _build_google_flights_goal(), _build_skyscanner_goal(), _call_browser_with_retry(), _call_fetch_with_retry() (+131 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (92): AlertDecision, AlertEngine, _build_skyscanner_url(), evaluate_alert(), _fmt_inr(), format_alert_message(), _format_alert_timestamp(), _format_route_display() (+84 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (38): Data payload for POST /api/v1/scrape/run response., ScrapeRunResponse, client(), tests/test_api.py — FastAPI TestClient test suite for Phase 4.  All DB interacti, Insert an alert log entry directly into the in-memory DB., Tests for GET /health — the no-auth liveness probe., Health must be accessible without X-SkySaver-Key., Tests for X-SkySaver-Key header enforcement on protected endpoints. (+30 more)

### Community 3 - "Community 3"
Cohesion: 0.04
Nodes (74): create_app(), api/main.py — SkySaver FastAPI Application Factory.  Routers mounted:   /api/v1/, Attach a UUID4 request_id to every request and response.      1. Generates reque, Create and return a fully configured FastAPI instance.      Called once at start, RequestIDMiddleware, AddRouteRequest, AlertCooldownResponse, AlertEntry (+66 more)

### Community 4 - "Community 4"
Cohesion: 0.06
Nodes (60): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), load_routes_from_config(), db/init_db.py â€” Database initializer for SkySaver.  Run once on first boot (py, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Parse config/routes.yaml and upsert every route into monitored_routes.      Args, Check that all 5 tables exist with all expected columns.      Returns:         T (+52 more)

### Community 5 - "Community 5"
Cohesion: 0.05
Nodes (18): Alert Trigger Decision Logic, Database Queries Module, Price Statistics Calculation, Database Test Suite, fresh_db(), _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank). (+10 more)

### Community 6 - "Community 6"
Cohesion: 0.06
Nodes (29): build_features(), _ensure_models_dir(), ForecastEngine, generate_labels(), _latest_model_path(), _list_model_files(), _load_all_price_data(), _next_version() (+21 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (32): get_gemini_flash_config(), get_gemini_pro_config(), get_logger(), _JsonFormatter, load_env(), agents/base_agent.py — Shared base utilities for all SkySaver agents.  Provides:, Return a configured logger with JSON formatter.      Idempotent — calling this t, Return a configured logger with JSON formatter.      Idempotent — calling this t (+24 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (24): _empty_state(), agents/rate_limiter.py — Per-route and per-API rate limit enforcement.  Persists, Return ``True`` if enough time has elapsed since this route+date was scraped., Return ``True`` if TinyFish Browser calls today are below the safe limit., Return ``True`` if TinyFish Fetch calls today are below the safe limit., Return ``True`` if Sky Scrapper API calls today are below the safe limit., Record that a scrape attempt just completed for this route+date.          Update, Increment the TinyFish call counter for *endpoint*.          Args:             e (+16 more)

### Community 9 - "Community 9"
Cohesion: 0.09
Nodes (13): _normalise_airline(), _parse_price_inr(), _parse_single_tinyfish_fare(), Parse Amadeus offer objects into ScrapedFare list.          Args:             of, Convert one Amadeus offer dict to a ScrapedFare.          Args:             offe, Extract an integer INR fare from a raw price string.      Handles every real-wor, Extract an integer INR fare from a raw price string.      Handles every real-wor, Map a raw airline name to its canonical form.      Lookup is case-insensitive on (+5 more)

### Community 10 - "Community 10"
Cohesion: 0.12
Nodes (23): Attempt Sky Scrapper API fallback fetch.          Returns:             List of f, Validate and parse a route string into (origin, destination).      Valid format:, Validate and parse a route string into (origin, destination).      Valid format:, Fetch flight offers from Sky Scrapper and return normalised ScrapedFare list., _validate_route(), PriceHistoryResponse, PriceObservationResponse, PriceStatsResponse (+15 more)

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (17): App Constants, HTTP Constants, Constants Entry, Permission Constants, Role Constants, Shared Package Entry, Common Schemas, Schemas Entry (+9 more)

### Community 12 - "Community 12"
Cohesion: 0.15
Nodes (13): AG2 (AutoGen), Alert Engine, AmadeusClient, RateLimiter, RouteScraperAgent, ScraperOrchestrator, SkySaver, Three-tier architecture (+5 more)

### Community 13 - "Community 13"
Cohesion: 0.18
Nodes (12): RateLimiter Middleware, Tenant Middleware, Auth Controller, Auth Repository, Auth Routes, Auth Schemas, Auth Service, Auth Types (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.22
Nodes (10): insert_price_observation, PriceObservation, update_price_stats, RateLimiter, RouteScraperAgent, ScrapedFare, ScraperOrchestrator, SkyScrappperClient (+2 more)

### Community 15 - "Community 15"
Cohesion: 0.25
Nodes (7): get_db_path(), get_request_id(), api/dependencies.py — Shared FastAPI dependencies.  Three injectable dependencie, Verify the X-SkySaver-Key request header.      Uses secrets.compare_digest() for, Return the SQLite database file path from DATABASE_PATH env var.      Falls back, Extract the request_id set by RequestIDMiddleware.      Falls back to a fresh UU, verify_api_key()

### Community 16 - "Community 16"
Cohesion: 0.4
Nodes (6): AlertEngine, evaluate_alert, AnalyzerAgent, ForecastEngine, PipelineRunner, trigger_scrape_run

### Community 17 - "Community 17"
Cohesion: 0.4
Nodes (6): Permission Seeder, Role Seeder, Superadmin Tenant Seeder, Superadmin User Seeder, Demo Tenant Seeder, Database Seed Entry Point

### Community 18 - "Community 18"
Cohesion: 0.4
Nodes (5): Express Application Factory, Database Connection Manager, Environment Configuration, Redis Connection Manager, Server Startup Logic

### Community 19 - "Community 19"
Cohesion: 0.5
Nodes (5): Get Gemini Flash Config, Get Gemini Pro Config, Gemini 2.5 Flash Strategy, Gemini 2.5 Pro Strategy, LLM Thinking Budget

### Community 20 - "Community 20"
Cohesion: 0.5
Nodes (4): Authentication Middleware, Prisma Client Singleton, Prisma Client Extensions, Redis Cache Client

### Community 21 - "Community 21"
Cohesion: 0.5
Nodes (4): asyncHandler, Health Router, Health Endpoints Tests, Main Router

### Community 22 - "Community 22"
Cohesion: 0.67
Nodes (3): App Component, Web Index HTML, Web Main Entry

### Community 23 - "Community 23"
Cohesion: 0.67
Nodes (3): AG2 Agent Framework, Base Agent Utilities, TinyFish Scraper Library

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (2): queries, SQLite Database

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (2): create_app, APIResponse

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (2): Base Application Error, HTTP 404 Not Found Error

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (2): Health Controller, Health Service

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (2): BaseRepository, Express.Request

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (2): generateAccessToken, parseDurationToSeconds

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (2): FindManyResult, sendSuccess

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (2): get_gemini_flash_config, get_gemini_pro_config

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): Zero TinyFish counters if the stored date differs from today (UTC).

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Zero Sky Scrapper counter if the stored date differs from today.

### Community 40 - "Community 40"
Cohesion: 1.0
Nodes (1): Emit every log record as a single-line JSON object.      Fields included: timest

### Community 41 - "Community 41"
Cohesion: 1.0
Nodes (1): Return a configured logger with JSON formatter.      Idempotent — calling this t

### Community 42 - "Community 42"
Cohesion: 1.0
Nodes (1): Load .env file and validate all required environment variables.      Uses ``pyth

### Community 43 - "Community 43"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML

### Community 44 - "Community 44"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved

### Community 45 - "Community 45"
Cohesion: 1.0
Nodes (1): Decorator that measures wall-clock execution time of *func*.      Wraps the deco

### Community 46 - "Community 46"
Cohesion: 1.0
Nodes (1): Return the current UTC datetime as a timezone-aware object.      Always use this

### Community 47 - "Community 47"
Cohesion: 1.0
Nodes (1): Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_

### Community 48 - "Community 48"
Cohesion: 1.0
Nodes (1): SkySaver Project

### Community 49 - "Community 49"
Cohesion: 1.0
Nodes (1): BaseAgent

### Community 50 - "Community 50"
Cohesion: 1.0
Nodes (1): init_db

### Community 51 - "Community 51"
Cohesion: 1.0
Nodes (1): Gemini Flash

### Community 52 - "Community 52"
Cohesion: 1.0
Nodes (1): LightGBM

### Community 53 - "Community 53"
Cohesion: 1.0
Nodes (1): requests

### Community 54 - "Community 54"
Cohesion: 1.0
Nodes (1): lightgbm

### Community 56 - "Community 56"
Cohesion: 1.0
Nodes (1): Worker Count Rationale

### Community 57 - "Community 57"
Cohesion: 1.0
Nodes (1): SkySaver Overview

### Community 58 - "Community 58"
Cohesion: 1.0
Nodes (1): Vitest Configuration

### Community 59 - "Community 59"
Cohesion: 1.0
Nodes (1): Graceful Shutdown Handler

### Community 60 - "Community 60"
Cohesion: 1.0
Nodes (1): Application Error Codes

### Community 61 - "Community 61"
Cohesion: 1.0
Nodes (1): ErrorHandler Middleware

### Community 62 - "Community 62"
Cohesion: 1.0
Nodes (1): NotFound Middleware

### Community 63 - "Community 63"
Cohesion: 1.0
Nodes (1): RequestId Middleware

### Community 64 - "Community 64"
Cohesion: 1.0
Nodes (1): RequestLogger Middleware

### Community 65 - "Community 65"
Cohesion: 1.0
Nodes (1): Security Middleware

### Community 66 - "Community 66"
Cohesion: 1.0
Nodes (1): seedRoles

### Community 67 - "Community 67"
Cohesion: 1.0
Nodes (1): Environment

### Community 68 - "Community 68"
Cohesion: 1.0
Nodes (1): AppConfig

### Community 69 - "Community 69"
Cohesion: 1.0
Nodes (1): verifyAccessToken

### Community 70 - "Community 70"
Cohesion: 1.0
Nodes (1): sendCreated

### Community 71 - "Community 71"
Cohesion: 1.0
Nodes (1): sendNoContent

### Community 72 - "Community 72"
Cohesion: 1.0
Nodes (1): sendPaginated

### Community 73 - "Community 73"
Cohesion: 1.0
Nodes (1): Auth Integration Tests

### Community 74 - "Community 74"
Cohesion: 1.0
Nodes (1): createTestApp

### Community 75 - "Community 75"
Cohesion: 1.0
Nodes (1): Tailwind Config

### Community 76 - "Community 76"
Cohesion: 1.0
Nodes (1): Vite Config

### Community 77 - "Community 77"
Cohesion: 1.0
Nodes (1): Vite Environment Definitions

### Community 78 - "Community 78"
Cohesion: 1.0
Nodes (1): create_tables

### Community 79 - "Community 79"
Cohesion: 1.0
Nodes (1): Project Dependencies

## Knowledge Gaps
- **227 isolated node(s):** `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`, `agents/analyzer_agent.py — Phase 3 Subsystem A: AnalyzerAgent.  Uses Gemini 2.5`, `Structured price context for one route+date pair, fed to the AnalyzerAgent.`, `Structured reasoning output from Gemini 2.5 Pro for one route+date.`, `Return a safe fallback AnalysisReport when Gemini cannot be reached or parsed.` (+222 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 24`** (2 nodes): `gunicorn_conf.py`, `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (2 nodes): `queries`, `SQLite Database`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (2 nodes): `create_app`, `APIResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (2 nodes): `Base Application Error`, `HTTP 404 Not Found Error`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (2 nodes): `Health Controller`, `Health Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (2 nodes): `BaseRepository`, `Express.Request`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (2 nodes): `generateAccessToken`, `parseDurationToSeconds`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (2 nodes): `FindManyResult`, `sendSuccess`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (2 nodes): `get_gemini_flash_config`, `get_gemini_pro_config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `Zero TinyFish counters if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Zero Sky Scrapper counter if the stored date differs from today.`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 40`** (1 nodes): `Emit every log record as a single-line JSON object.      Fields included: timest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 41`** (1 nodes): `Return a configured logger with JSON formatter.      Idempotent — calling this t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 42`** (1 nodes): `Load .env file and validate all required environment variables.      Uses ``pyth`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 43`** (1 nodes): `Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 44`** (1 nodes): `Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 45`** (1 nodes): `Decorator that measures wall-clock execution time of *func*.      Wraps the deco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 46`** (1 nodes): `Return the current UTC datetime as a timezone-aware object.      Always use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 47`** (1 nodes): `Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 48`** (1 nodes): `SkySaver Project`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 49`** (1 nodes): `BaseAgent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 50`** (1 nodes): `init_db`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 51`** (1 nodes): `Gemini Flash`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 52`** (1 nodes): `LightGBM`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 53`** (1 nodes): `requests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 54`** (1 nodes): `lightgbm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 56`** (1 nodes): `Worker Count Rationale`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 57`** (1 nodes): `SkySaver Overview`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 58`** (1 nodes): `Vitest Configuration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 59`** (1 nodes): `Graceful Shutdown Handler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 60`** (1 nodes): `Application Error Codes`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 61`** (1 nodes): `ErrorHandler Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 62`** (1 nodes): `NotFound Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 63`** (1 nodes): `RequestId Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 64`** (1 nodes): `RequestLogger Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 65`** (1 nodes): `Security Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 66`** (1 nodes): `seedRoles`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 67`** (1 nodes): `Environment`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 68`** (1 nodes): `AppConfig`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 69`** (1 nodes): `verifyAccessToken`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 70`** (1 nodes): `sendCreated`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 71`** (1 nodes): `sendNoContent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 72`** (1 nodes): `sendPaginated`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 73`** (1 nodes): `Auth Integration Tests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 74`** (1 nodes): `createTestApp`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 75`** (1 nodes): `Tailwind Config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 76`** (1 nodes): `Vite Config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 77`** (1 nodes): `Vite Environment Definitions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 78`** (1 nodes): `create_tables`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 79`** (1 nodes): `Project Dependencies`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimiter` connect `Community 0` to `Community 1`, `Community 3`, `Community 7`, `Community 8`, `Community 9`, `Community 10`?**
  _High betweenness centrality (0.283) - this node is a cross-community bridge._
- **Why does `PipelineRunner` connect `Community 1` to `Community 0`, `Community 3`, `Community 6`?**
  _High betweenness centrality (0.128) - this node is a cross-community bridge._
- **Why does `ScrapeRunResponse` connect `Community 2` to `Community 3`?**
  _High betweenness centrality (0.121) - this node is a cross-community bridge._
- **Are the 173 inferred relationships involving `RateLimiter` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`RateLimiter` has 173 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `ScraperOrchestrator` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`ScraperOrchestrator` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `ScrapeRunResult` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`ScrapeRunResult` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `AnalysisReport` (e.g. with `AlertDecision` and `AlertEngine`) actually correct?**
  _`AnalysisReport` has 47 INFERRED edges - model-reasoned connections that need verification._