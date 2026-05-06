# Graph Report - .  (2026-05-07)

## Corpus Check
- Corpus is ~32,710 words - fits in a single context window. You may not need a graph.

## Summary
- 901 nodes · 1953 edges · 68 communities detected
- Extraction: 58% EXTRACTED · 42% INFERRED · 0% AMBIGUOUS · INFERRED: 820 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Scraper Management|Scraper Management]]
- [[_COMMUNITY_Testing Suite|Testing Suite]]
- [[_COMMUNITY_Pipeline Management|Pipeline Management]]
- [[_COMMUNITY_API Routes & Logic|API Routes & Logic]]
- [[_COMMUNITY_Database Operations|Database Operations]]
- [[_COMMUNITY_Testing Suite|Testing Suite]]
- [[_COMMUNITY_Testing Suite|Testing Suite]]
- [[_COMMUNITY_Forecast Management|Forecast Management]]
- [[_COMMUNITY_Rate Management|Rate Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Routes Module|Routes Module]]
- [[_COMMUNITY_Shared Module|Shared Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Module Module|Module Module]]
- [[_COMMUNITY_API Routes & Logic|API Routes & Logic]]
- [[_COMMUNITY_Alert Module|Alert Module]]
- [[_COMMUNITY_01 Module|01 Module]]
- [[_COMMUNITY_App Module|App Module]]
- [[_COMMUNITY_Auth Module|Auth Module]]
- [[_COMMUNITY_Health Module|Health Module]]
- [[_COMMUNITY_Web Module|Web Module]]
- [[_COMMUNITY_Gunicorn Module|Gunicorn Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Main Module|Main Module]]
- [[_COMMUNITY_Apperror Module|Apperror Module]]
- [[_COMMUNITY_Module Module|Module Module]]
- [[_COMMUNITY_Base Module|Base Module]]
- [[_COMMUNITY_Base Module|Base Module]]
- [[_COMMUNITY_Jwt Module|Jwt Module]]
- [[_COMMUNITY_Rate Management|Rate Management]]
- [[_COMMUNITY_Rate Management|Rate Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Base Management|Base Management]]
- [[_COMMUNITY_Projectbrief Module|Projectbrief Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Requirements Module|Requirements Module]]
- [[_COMMUNITY_Requirements Module|Requirements Module]]
- [[_COMMUNITY_Gunicorn Module|Gunicorn Module]]
- [[_COMMUNITY_Readme Module|Readme Module]]
- [[_COMMUNITY_Vitest Module|Vitest Module]]
- [[_COMMUNITY_Server Module|Server Module]]
- [[_COMMUNITY_Errorcodes Module|Errorcodes Module]]
- [[_COMMUNITY_Middleware Module|Middleware Module]]
- [[_COMMUNITY_Middleware Module|Middleware Module]]
- [[_COMMUNITY_Middleware Module|Middleware Module]]
- [[_COMMUNITY_Middleware Module|Middleware Module]]
- [[_COMMUNITY_Middleware Module|Middleware Module]]
- [[_COMMUNITY_Seeds Module|Seeds Module]]
- [[_COMMUNITY_Environment Module|Environment Module]]
- [[_COMMUNITY_Environment Module|Environment Module]]
- [[_COMMUNITY_Jwt Module|Jwt Module]]
- [[_COMMUNITY_Response Module|Response Module]]
- [[_COMMUNITY_Response Module|Response Module]]
- [[_COMMUNITY_Response Module|Response Module]]
- [[_COMMUNITY_Auth Module|Auth Module]]
- [[_COMMUNITY_Testapp Module|Testapp Module]]
- [[_COMMUNITY_Tailwind Module|Tailwind Module]]
- [[_COMMUNITY_Vite Module|Vite Module]]
- [[_COMMUNITY_Web Module|Web Module]]

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
- `RateLimiter` --uses--> `Validate and parse a route string into (origin, destination).      Valid format:`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `AlertDecision` --calls--> `_make_alert_decision()`  [INFERRED]
  db\queries.py → tests\test_phase3.py
- `AlertDecision` --uses--> `TestBuildPriceSummary`  [INFERRED]
  agents\alert_engine.py → tests\test_phase3.py
- `AlertDecision` --uses--> `TestAnalyzerAgent`  [INFERRED]
  agents\alert_engine.py → tests\test_phase3.py
- `AlertDecision` --uses--> `TestForecastEngine`  [INFERRED]
  agents\alert_engine.py → tests\test_phase3.py

## Hyperedges (group relationships)
- **Flight Deal Pipeline** — pipeline_pipelinerunner, forecast_engine_forecastengine, analyzer_agent_analyzeragent, alert_engine_alertengine [EXTRACTED 0.95]
- **Three-Gate Alert Logic** — alert_engine_evaluate_alert, forecast_engine_forecastengine, alert_engine_alertengine [EXTRACTED 0.90]
- **Database Seeding Workflow** — seed_main, 01_permissions_seed_seedpermissions, 02_roles_seed_seedroles, 03_superadmin_tenant_seed_seedsuperadmintenant, 04_superadmin_user_seed_seedsuperadminuser, 05_demo_tenant_seed_seeddemotenant [EXTRACTED 1.00]
- **Server Lifecycle Management** — server_startserver, server_gracefulshutdown, database_connectdatabase, redis_connectredis [EXTRACTED 1.00]
- **Auth Flow Components** — auth_routes, jwt_utils_generateaccesstoken, jwt_utils_verifyaccesstoken, auth_test_integration [INFERRED 0.80]
- **API Utility Layer** — asynchandler_asynchandler, response_sendsuccess, pagination_getpaginationmeta [INFERRED 0.70]

## Communities

### Community 0 - "Scraper Management"
Cohesion: 0.04
Nodes (102): RateLimiter, Thread-safe rate limiter with JSON persistence across restarts.      All public, AmadeusClient, AmadeusServerError, _build_google_flights_goal(), _build_skyscanner_goal(), _call_browser_with_retry(), _call_fetch_with_retry() (+94 more)

### Community 1 - "Testing Suite"
Cohesion: 0.03
Nodes (38): Data payload for POST /api/v1/scrape/run response., ScrapeRunResponse, client(), tests/test_api.py — FastAPI TestClient test suite for Phase 4.  All DB interacti, Insert an alert log entry directly into the in-memory DB., Tests for GET /health — the no-auth liveness probe., Health must be accessible without X-SkySaver-Key., Tests for X-SkySaver-Key header enforcement on protected endpoints. (+30 more)

### Community 2 - "Pipeline Management"
Cohesion: 0.07
Nodes (72): AlertDecision, AlertEngine, _build_skyscanner_url(), _fmt_inr(), format_alert_message(), _format_alert_timestamp(), _format_route_display(), agents/alert_engine.py — Phase 3 Subsystem C: Telegram Alert Engine.  The ONLY m (+64 more)

### Community 3 - "API Routes & Logic"
Cohesion: 0.04
Nodes (74): create_app(), api/main.py — SkySaver FastAPI Application Factory.  Routers mounted:   /api/v1/, Attach a UUID4 request_id to every request and response.      1. Generates reque, Create and return a fully configured FastAPI instance.      Called once at start, RequestIDMiddleware, AddRouteRequest, AlertCooldownResponse, AlertEntry (+66 more)

### Community 4 - "Database Operations"
Cohesion: 0.05
Nodes (63): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), load_routes_from_config(), db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Parse config/routes.yaml and upsert every route into monitored_routes.      Args, Check that all 5 tables exist with all expected columns.      Returns:         T (+55 more)

### Community 5 - "Testing Suite"
Cohesion: 0.08
Nodes (17): evaluate_alert(), build_price_summary(), PriceSummary, Structured price context for one route+date pair, fed to the AnalyzerAgent., Fetch all required data from the DB and construct a PriceSummary.      Calls:, Exception, _make_alert_decision(), _make_analysis() (+9 more)

### Community 6 - "Testing Suite"
Cohesion: 0.05
Nodes (12): _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)., Shortcut to insert one observation with sensible defaults., 10 threads each insert 5 rows — total must be 50, no corruption., TestAlertLog, TestGetAlertDecision, TestGetObservationCountByRoute (+4 more)

### Community 7 - "Forecast Management"
Cohesion: 0.06
Nodes (29): build_features(), _ensure_models_dir(), ForecastEngine, generate_labels(), _latest_model_path(), _list_model_files(), _load_all_price_data(), _next_version() (+21 more)

### Community 8 - "Rate Management"
Cohesion: 0.08
Nodes (23): _empty_state(), agents/rate_limiter.py — Per-route and per-API rate limit enforcement.  Persists, Return ``True`` if enough time has elapsed since this route+date was scraped., Return ``True`` if TinyFish Browser calls today are below the safe limit., Return ``True`` if TinyFish Fetch calls today are below the safe limit., Return ``True`` if Amadeus API calls today are below the safe limit.          Au, Record that a scrape attempt just completed for this route+date.          Update, Increment the TinyFish call counter for *endpoint*.          Args:             e (+15 more)

### Community 9 - "Base Management"
Cohesion: 0.12
Nodes (16): get_gemini_flash_config(), get_gemini_pro_config(), get_logger(), _JsonFormatter, load_env(), agents/base_agent.py — Shared base utilities for all SkySaver agents.  Provides:, Return a configured logger with JSON formatter.      Idempotent — calling this t, Load .env file and validate all required environment variables are present. (+8 more)

### Community 10 - "Routes Module"
Cohesion: 0.15
Nodes (20): Validate and parse a route string into (origin, destination).      Valid format:, _validate_route(), PriceHistoryResponse, PriceObservationResponse, PriceStatsResponse, A single scraped price observation., Computed percentile statistics for a route+date pair., Full price history response for a route+date. (+12 more)

### Community 11 - "Shared Module"
Cohesion: 0.14
Nodes (17): App Constants, HTTP Constants, Constants Entry, Permission Constants, Role Constants, Shared Package Entry, Common Schemas, Schemas Entry (+9 more)

### Community 12 - "Readme Module"
Cohesion: 0.17
Nodes (12): AG2 (AutoGen), Alert Engine, AmadeusClient, RateLimiter, RouteScraperAgent, ScraperOrchestrator, SkySaver, TinyFishClient (+4 more)

### Community 13 - "Module Module"
Cohesion: 0.18
Nodes (12): RateLimiter Middleware, Tenant Middleware, Auth Controller, Auth Repository, Auth Routes, Auth Schemas, Auth Service, Auth Types (+4 more)

### Community 14 - "API Routes & Logic"
Cohesion: 0.25
Nodes (7): get_db_path(), get_request_id(), api/dependencies.py — Shared FastAPI dependencies.  Three injectable dependencie, Verify the X-SkySaver-Key request header.      Uses secrets.compare_digest() for, Return the SQLite database file path from DATABASE_PATH env var.      Falls back, Extract the request_id set by RequestIDMiddleware.      Falls back to a fresh UU, verify_api_key()

### Community 15 - "Alert Module"
Cohesion: 0.4
Nodes (6): AlertEngine, evaluate_alert, AnalyzerAgent, ForecastEngine, PipelineRunner, trigger_scrape_run

### Community 16 - "01 Module"
Cohesion: 0.4
Nodes (6): Permission Seeder, Role Seeder, Superadmin Tenant Seeder, Superadmin User Seeder, Demo Tenant Seeder, Database Seed Entry Point

### Community 17 - "App Module"
Cohesion: 0.4
Nodes (5): Express Application Factory, Database Connection Manager, Environment Configuration, Redis Connection Manager, Server Startup Logic

### Community 18 - "Auth Module"
Cohesion: 0.5
Nodes (4): Authentication Middleware, Prisma Client Singleton, Prisma Client Extensions, Redis Cache Client

### Community 19 - "Health Module"
Cohesion: 0.5
Nodes (4): asyncHandler, Health Router, Health Endpoints Tests, Main Router

### Community 20 - "Web Module"
Cohesion: 0.67
Nodes (3): App Component, Web Index HTML, Web Main Entry

### Community 21 - "Gunicorn Module"
Cohesion: 1.0
Nodes (1): gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP

### Community 22 - "Readme Module"
Cohesion: 1.0
Nodes (2): queries, SQLite Database

### Community 23 - "Main Module"
Cohesion: 1.0
Nodes (2): create_app, APIResponse

### Community 24 - "Apperror Module"
Cohesion: 1.0
Nodes (2): Base Application Error, HTTP 404 Not Found Error

### Community 25 - "Module Module"
Cohesion: 1.0
Nodes (2): Health Controller, Health Service

### Community 26 - "Base Module"
Cohesion: 1.0
Nodes (2): FindManyResult, sendSuccess

### Community 27 - "Base Module"
Cohesion: 1.0
Nodes (2): BaseRepository, Express.Request

### Community 28 - "Jwt Module"
Cohesion: 1.0
Nodes (2): generateAccessToken, parseDurationToSeconds

### Community 29 - "Rate Management"
Cohesion: 1.0
Nodes (1): Zero TinyFish counters if the stored date differs from today (UTC).

### Community 30 - "Rate Management"
Cohesion: 1.0
Nodes (1): Zero Amadeus counter if the stored date differs from today (UTC).

### Community 36 - "Base Management"
Cohesion: 1.0
Nodes (1): Emit every log record as a single-line JSON object.      Fields included: timest

### Community 37 - "Base Management"
Cohesion: 1.0
Nodes (1): Return a configured logger with JSON formatter.      Idempotent — calling this t

### Community 38 - "Base Management"
Cohesion: 1.0
Nodes (1): Load .env file and validate all required environment variables.      Uses ``pyth

### Community 39 - "Base Management"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML

### Community 40 - "Base Management"
Cohesion: 1.0
Nodes (1): Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved

### Community 41 - "Base Management"
Cohesion: 1.0
Nodes (1): Decorator that measures wall-clock execution time of *func*.      Wraps the deco

### Community 42 - "Base Management"
Cohesion: 1.0
Nodes (1): Return the current UTC datetime as a timezone-aware object.      Always use this

### Community 43 - "Base Management"
Cohesion: 1.0
Nodes (1): Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_

### Community 44 - "Projectbrief Module"
Cohesion: 1.0
Nodes (1): SkySaver Project

### Community 45 - "Readme Module"
Cohesion: 1.0
Nodes (1): BaseAgent

### Community 46 - "Readme Module"
Cohesion: 1.0
Nodes (1): init_db

### Community 47 - "Readme Module"
Cohesion: 1.0
Nodes (1): Gemini Flash

### Community 48 - "Readme Module"
Cohesion: 1.0
Nodes (1): LightGBM

### Community 49 - "Requirements Module"
Cohesion: 1.0
Nodes (1): requests

### Community 50 - "Requirements Module"
Cohesion: 1.0
Nodes (1): lightgbm

### Community 52 - "Gunicorn Module"
Cohesion: 1.0
Nodes (1): Worker Count Rationale

### Community 53 - "Readme Module"
Cohesion: 1.0
Nodes (1): SkySaver Overview

### Community 54 - "Vitest Module"
Cohesion: 1.0
Nodes (1): Vitest Configuration

### Community 55 - "Server Module"
Cohesion: 1.0
Nodes (1): Graceful Shutdown Handler

### Community 56 - "Errorcodes Module"
Cohesion: 1.0
Nodes (1): Application Error Codes

### Community 57 - "Middleware Module"
Cohesion: 1.0
Nodes (1): ErrorHandler Middleware

### Community 58 - "Middleware Module"
Cohesion: 1.0
Nodes (1): NotFound Middleware

### Community 59 - "Middleware Module"
Cohesion: 1.0
Nodes (1): RequestId Middleware

### Community 60 - "Middleware Module"
Cohesion: 1.0
Nodes (1): RequestLogger Middleware

### Community 61 - "Middleware Module"
Cohesion: 1.0
Nodes (1): Security Middleware

### Community 62 - "Seeds Module"
Cohesion: 1.0
Nodes (1): seedRoles

### Community 63 - "Environment Module"
Cohesion: 1.0
Nodes (1): Environment

### Community 64 - "Environment Module"
Cohesion: 1.0
Nodes (1): AppConfig

### Community 65 - "Jwt Module"
Cohesion: 1.0
Nodes (1): verifyAccessToken

### Community 66 - "Response Module"
Cohesion: 1.0
Nodes (1): sendCreated

### Community 67 - "Response Module"
Cohesion: 1.0
Nodes (1): sendNoContent

### Community 68 - "Response Module"
Cohesion: 1.0
Nodes (1): sendPaginated

### Community 69 - "Auth Module"
Cohesion: 1.0
Nodes (1): Auth Integration Tests

### Community 70 - "Testapp Module"
Cohesion: 1.0
Nodes (1): createTestApp

### Community 71 - "Tailwind Module"
Cohesion: 1.0
Nodes (1): Tailwind Config

### Community 72 - "Vite Module"
Cohesion: 1.0
Nodes (1): Vite Config

### Community 73 - "Web Module"
Cohesion: 1.0
Nodes (1): Vite Environment Definitions

## Knowledge Gaps
- **203 isolated node(s):** `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`, `agents/analyzer_agent.py — Phase 3 Subsystem A: AnalyzerAgent.  Uses Gemini 2.5`, `Structured price context for one route+date pair, fed to the AnalyzerAgent.`, `Structured reasoning output from Gemini 2.5 Pro for one route+date.`, `Return a safe fallback AnalysisReport when Gemini cannot be reached or parsed.` (+198 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Gunicorn Module`** (2 nodes): `gunicorn_conf.py`, `gunicorn_conf.py — Production Gunicorn configuration for SkySaver.  Oracle A1 VP`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (2 nodes): `queries`, `SQLite Database`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Main Module`** (2 nodes): `create_app`, `APIResponse`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Apperror Module`** (2 nodes): `Base Application Error`, `HTTP 404 Not Found Error`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Module Module`** (2 nodes): `Health Controller`, `Health Service`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Module`** (2 nodes): `FindManyResult`, `sendSuccess`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Module`** (2 nodes): `BaseRepository`, `Express.Request`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Jwt Module`** (2 nodes): `generateAccessToken`, `parseDurationToSeconds`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Rate Management`** (1 nodes): `Zero TinyFish counters if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Rate Management`** (1 nodes): `Zero Amadeus counter if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Emit every log record as a single-line JSON object.      Fields included: timest`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Return a configured logger with JSON formatter.      Idempotent — calling this t`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Load .env file and validate all required environment variables.      Uses ``pyth`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Return AG2 LLMConfig for Gemini 2.5 Flash.      Used for cheap bulk tasks — HTML`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Return AG2 LLMConfig for Claude Sonnet 4.6 with extended thinking.      Reserved`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Decorator that measures wall-clock execution time of *func*.      Wraps the deco`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Return the current UTC datetime as a timezone-aware object.      Always use this`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Management`** (1 nodes): `Convert a datetime to a compact ISO-8601 UTC string.      Example::          to_`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Projectbrief Module`** (1 nodes): `SkySaver Project`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (1 nodes): `BaseAgent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (1 nodes): `init_db`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (1 nodes): `Gemini Flash`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (1 nodes): `LightGBM`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Requirements Module`** (1 nodes): `requests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Requirements Module`** (1 nodes): `lightgbm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Gunicorn Module`** (1 nodes): `Worker Count Rationale`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Readme Module`** (1 nodes): `SkySaver Overview`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vitest Module`** (1 nodes): `Vitest Configuration`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Server Module`** (1 nodes): `Graceful Shutdown Handler`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Errorcodes Module`** (1 nodes): `Application Error Codes`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware Module`** (1 nodes): `ErrorHandler Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware Module`** (1 nodes): `NotFound Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware Module`** (1 nodes): `RequestId Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware Module`** (1 nodes): `RequestLogger Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Middleware Module`** (1 nodes): `Security Middleware`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Seeds Module`** (1 nodes): `seedRoles`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Environment Module`** (1 nodes): `Environment`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Environment Module`** (1 nodes): `AppConfig`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Jwt Module`** (1 nodes): `verifyAccessToken`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Response Module`** (1 nodes): `sendCreated`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Response Module`** (1 nodes): `sendNoContent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Response Module`** (1 nodes): `sendPaginated`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Auth Module`** (1 nodes): `Auth Integration Tests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Testapp Module`** (1 nodes): `createTestApp`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Tailwind Module`** (1 nodes): `Tailwind Config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Vite Module`** (1 nodes): `Vite Config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Web Module`** (1 nodes): `Vite Environment Definitions`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimiter` connect `Scraper Management` to `Pipeline Management`, `API Routes & Logic`, `Rate Management`, `Base Management`, `Routes Module`?**
  _High betweenness centrality (0.262) - this node is a cross-community bridge._
- **Why does `ScrapeRunResponse` connect `Testing Suite` to `API Routes & Logic`?**
  _High betweenness centrality (0.161) - this node is a cross-community bridge._
- **Why does `PipelineRunner` connect `Pipeline Management` to `Scraper Management`, `API Routes & Logic`, `Testing Suite`, `Forecast Management`?**
  _High betweenness centrality (0.136) - this node is a cross-community bridge._
- **Are the 115 inferred relationships involving `RateLimiter` (e.g. with `PipelineRunResult` and `PipelineRunner`) actually correct?**
  _`RateLimiter` has 115 INFERRED edges - model-reasoned connections that need verification._
- **Are the 47 inferred relationships involving `AnalysisReport` (e.g. with `AlertDecision` and `AlertEngine`) actually correct?**
  _`AnalysisReport` has 47 INFERRED edges - model-reasoned connections that need verification._
- **Are the 48 inferred relationships involving `ForecastScore` (e.g. with `AlertDecision` and `AlertEngine`) actually correct?**
  _`ForecastScore` has 48 INFERRED edges - model-reasoned connections that need verification._
- **Are the 41 inferred relationships involving `ScrapeRunResponse` (e.g. with `api/routes/scrape.py — Scraping trigger and status endpoints.  Endpoints:   POST` and `Execute the full pipeline synchronously.      Called inside run_in_executor so t`) actually correct?**
  _`ScrapeRunResponse` has 41 INFERRED edges - model-reasoned connections that need verification._