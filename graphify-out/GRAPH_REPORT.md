# Graph Report - Project - SkySaver  (2026-05-07)

## Corpus Check
- 27 files · ~32,676 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 809 nodes · 1892 edges · 33 communities detected
- Extraction: 57% EXTRACTED · 43% INFERRED · 0% AMBIGUOUS · INFERRED: 811 edges (avg confidence: 0.56)
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
- [[_COMMUNITY_Community 35|Community 35]]
- [[_COMMUNITY_Community 36|Community 36]]
- [[_COMMUNITY_Community 37|Community 37]]

## God Nodes (most connected - your core abstractions)
1. `RateLimiter` - 130 edges
2. `AnalysisReport` - 51 edges
3. `ForecastScore` - 51 edges
4. `ScrapeRunResponse` - 44 edges
5. `ScraperOrchestrator` - 42 edges
6. `ScrapeRunResult` - 39 edges
7. `AnalyzerAgent` - 37 edges
8. `RouteScraperAgent` - 36 edges
9. `AlertDecision` - 34 edges
10. `TrainingResult` - 31 edges

## Surprising Connections (you probably didn't know these)
- `RateLimiter` --uses--> `Aggregated result of a full scrape run across all routes.`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Validate and parse a route string into (origin, destination).      Valid format:`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Map a raw airline name to its canonical form.      Lookup is case-insensitive on`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Manages a complete scrape run across all active monitored routes.      Lifecycle`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Execute a full scrape run across all active routes.          Returns:`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.04
Nodes (90): RateLimiter, Thread-safe rate limiter with JSON persistence across restarts.      All public, AmadeusClient, AmadeusServerError, _build_google_flights_goal(), _build_skyscanner_goal(), _call_browser_with_retry(), _call_fetch_with_retry() (+82 more)

### Community 1 - "Community 1"
Cohesion: 0.04
Nodes (91): create_app(), api/main.py — SkySaver FastAPI Application Factory.  Routers mounted:   /api/v1/, Attach a UUID4 request_id to every request and response.      1. Generates reque, Create and return a fully configured FastAPI instance.      Called once at start, RequestIDMiddleware, AddRouteRequest, AlertCooldownResponse, AlertEntry (+83 more)

### Community 2 - "Community 2"
Cohesion: 0.03
Nodes (38): Data payload for POST /api/v1/scrape/run response., ScrapeRunResponse, client(), tests/test_api.py — FastAPI TestClient test suite for Phase 4.  All DB interacti, Insert an alert log entry directly into the in-memory DB., Tests for GET /health — the no-auth liveness probe., Health must be accessible without X-SkySaver-Key., Tests for X-SkySaver-Key header enforcement on protected endpoints. (+30 more)

### Community 3 - "Community 3"
Cohesion: 0.07
Nodes (74): AlertDecision, AlertEngine, _format_alert_timestamp(), agents/alert_engine.py — Phase 3 Subsystem C: Telegram Alert Engine.  The ONLY m, Build the HTML-formatted Telegram message string., Send a message via Telegram Bot API. Never raises. Returns True on success., Send a connectivity test message to verify bot token and chat ID., Evaluate whether all three gates pass for an alert.      Gate 1 — Statistical ga (+66 more)

### Community 4 - "Community 4"
Cohesion: 0.08
Nodes (24): _build_skyscanner_url(), evaluate_alert(), _fmt_inr(), format_alert_message(), _format_route_display(), send_telegram_alert(), _strip_html(), build_price_summary() (+16 more)

### Community 5 - "Community 5"
Cohesion: 0.06
Nodes (62): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), load_routes_from_config(), db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Parse config/routes.yaml and upsert every route into monitored_routes.      Args, Check that all 5 tables exist with all expected columns.      Returns:         T (+54 more)

### Community 6 - "Community 6"
Cohesion: 0.05
Nodes (14): fresh_db(), _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)., Provide an isolated database for every single test., Shortcut to insert one observation with sensible defaults., 10 threads each insert 5 rows — total must be 50, no corruption., TestAlertLog (+6 more)

### Community 7 - "Community 7"
Cohesion: 0.06
Nodes (29): build_features(), _ensure_models_dir(), ForecastEngine, generate_labels(), _latest_model_path(), _list_model_files(), _load_all_price_data(), _next_version() (+21 more)

### Community 8 - "Community 8"
Cohesion: 0.08
Nodes (23): _empty_state(), agents/rate_limiter.py — Per-route and per-API rate limit enforcement.  Persists, Return ``True`` if enough time has elapsed since this route+date was scraped., Return ``True`` if TinyFish Browser calls today are below the safe limit., Return ``True`` if TinyFish Fetch calls today are below the safe limit., Return ``True`` if Amadeus API calls today are below the safe limit.          Au, Record that a scrape attempt just completed for this route+date.          Update, Increment the TinyFish call counter for *endpoint*.          Args:             e (+15 more)

### Community 9 - "Community 9"
Cohesion: 0.12
Nodes (14): Construct the AG2 ConversableAgent pair (assistant + user proxy)., get_gemini_flash_config(), get_gemini_pro_config(), get_logger(), _JsonFormatter, load_env(), agents/base_agent.py — Shared base utilities for all SkySaver agents.  Provides:, Return a configured logger with JSON formatter.      Idempotent — calling this t (+6 more)

### Community 10 - "Community 10"
Cohesion: 0.29
Nodes (3): _normalise_airline(), Map a raw airline name to its canonical form.      Lookup is case-insensitive on, TestNormaliseAirline

### Community 11 - "Community 11"
Cohesion: 0.17
Nodes (12): AG2 (AutoGen), Alert Engine, AmadeusClient, RateLimiter, RouteScraperAgent, ScraperOrchestrator, SkySaver, TinyFishClient (+4 more)

### Community 12 - "Community 12"
Cohesion: 0.44
Nodes (4): Validate and parse a route string into (origin, destination).      Valid format:, _validate_route(), _validate_route(), TestValidateRoute

### Community 13 - "Community 13"
Cohesion: 0.25
Nodes (7): get_db_path(), get_request_id(), api/dependencies.py — Shared FastAPI dependencies.  Three injectable dependencie, Verify the X-SkySaver-Key request header.      Uses secrets.compare_digest() for, Return the SQLite database file path from DATABASE_PATH env var.      Falls back, Extract the request_id set by RequestIDMiddleware.      Falls back to a fresh UU, verify_api_key()

### Community 14 - "Community 14"
Cohesion: 1.0
Nodes (1): gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP

### Community 15 - "Community 15"
Cohesion: 1.0
Nodes (2): queries, SQLite Database

### Community 16 - "Community 16"
Cohesion: 1.0
Nodes (1): Zero TinyFish counters if the stored date differs from today (UTC).

### Community 17 - "Community 17"
Cohesion: 1.0
Nodes (1): Zero Amadeus counter if the stored date differs from today (UTC).

### Community 23 - "Community 23"
Cohesion: 1.0
Nodes (1): Emit every log record as a single-line JSON object.      Fields included: timest

### Community 24 - "Community 24"
Cohesion: 1.0
Nodes (1): Return a configured logger with JSON formatter.      Idempotent — calling this t

### Community 25 - "Community 25"
Cohesion: 1.0
Nodes (1): Load .env file and validate all required environment variables.      Uses ``pyth

### Community 26 - "Community 26"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML

### Community 27 - "Community 27"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved

### Community 28 - "Community 28"
Cohesion: 1.0
Nodes (1): Decorator that measures wall-clock execution time of *func*.      Wraps the deco

### Community 29 - "Community 29"
Cohesion: 1.0
Nodes (1): Return the current UTC datetime as a timezone-aware object.      Always use this

### Community 30 - "Community 30"
Cohesion: 1.0
Nodes (1): Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_

### Community 31 - "Community 31"
Cohesion: 1.0
Nodes (1): SkySaver Project

### Community 32 - "Community 32"
Cohesion: 1.0
Nodes (1): BaseAgent

### Community 33 - "Community 33"
Cohesion: 1.0
Nodes (1): init_db

### Community 34 - "Community 34"
Cohesion: 1.0
Nodes (1): Gemini Flash

### Community 35 - "Community 35"
Cohesion: 1.0
Nodes (1): LightGBM

### Community 36 - "Community 36"
Cohesion: 1.0
Nodes (1): requests

### Community 37 - "Community 37"
Cohesion: 1.0
Nodes (1): lightgbm

## Knowledge Gaps
- **141 isolated node(s):** `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`, `agents/analyzer_agent.py — Phase 3 Subsystem A: AnalyzerAgent.  Uses Gemini 2.5`, `Structured price context for one route+date pair, fed to the AnalyzerAgent.`, `Structured reasoning output from Gemini 2.5 Pro for one route+date.`, `Return a safe fallback AnalysisReport when Gemini cannot be reached or parsed.` (+136 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 14`** (2 nodes): `gunicorn_conf.py`, `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 15`** (2 nodes): `queries`, `SQLite Database`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 16`** (1 nodes): `Zero TinyFish counters if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 17`** (1 nodes): `Zero Amadeus counter if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 23`** (1 nodes): `Emit every log record as a single-line JSON object.      Fields included: timest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 24`** (1 nodes): `Return a configured logger with JSON formatter.      Idempotent — calling this t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 25`** (1 nodes): `Load .env file and validate all required environment variables.      Uses ``pyth`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 26`** (1 nodes): `Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 27`** (1 nodes): `Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 28`** (1 nodes): `Decorator that measures wall-clock execution time of *func*.      Wraps the deco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 29`** (1 nodes): `Return the current UTC datetime as a timezone-aware object.      Always use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 30`** (1 nodes): `Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 31`** (1 nodes): `SkySaver Project`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 32`** (1 nodes): `BaseAgent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 33`** (1 nodes): `init_db`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 34`** (1 nodes): `Gemini Flash`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 35`** (1 nodes): `LightGBM`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 36`** (1 nodes): `requests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 37`** (1 nodes): `lightgbm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimiter` connect `Community 0` to `Community 1`, `Community 3`, `Community 5`, `Community 8`, `Community 10`, `Community 12`?**
  _High betweenness centrality (0.325) - this node is a cross-community bridge._
- **Why does `ScrapeRunResponse` connect `Community 2` to `Community 1`?**
  _High betweenness centrality (0.200) - this node is a cross-community bridge._
- **Why does `PipelineRunner` connect `Community 3` to `Community 0`, `Community 1`, `Community 4`, `Community 7`?**
  _High betweenness centrality (0.168) - this node is a cross-community bridge._
- **Are the 115 inferred relationships involving `RateLimiter` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`RateLimiter` has 115 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `AnalysisReport` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`AnalysisReport` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `ForecastScore` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`ForecastScore` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `ScrapeRunResponse` (e.g. with `api/routes/scrape.py — Scraping trigger and status endpoints.  Endpoints:   POST` and `Execute the full pipeline synchronously.      Called inside run_in_executor so t`) actually correct?**
  _`ScrapeRunResponse` has 41 INFERRED edges - model-reasoned connections that need verification._