# Graph Report - .  (2026-05-06)

## Corpus Check
- Corpus is ~25,291 words - fits in a single context window. You may not need a graph.

## Summary
- 597 nodes · 1416 edges · 26 communities detected
- Extraction: 60% EXTRACTED · 40% INFERRED · 0% AMBIGUOUS · INFERRED: 566 edges (avg confidence: 0.56)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Rate Limiting & API Clients|Rate Limiting & API Clients]]
- [[_COMMUNITY_Alert Engine Implementation|Alert Engine Implementation]]
- [[_COMMUNITY_Database Initialization & Config|Database Initialization & Config]]
- [[_COMMUNITY_Database Unit Tests|Database Unit Tests]]
- [[_COMMUNITY_Forecast Engine & Feature Engineering|Forecast Engine & Feature Engineering]]
- [[_COMMUNITY_Rate Limiter Logic|Rate Limiter Logic]]
- [[_COMMUNITY_Agent Configuration & Logging|Agent Configuration & Logging]]
- [[_COMMUNITY_Data Normalization|Data Normalization]]
- [[_COMMUNITY_Integration Testing (Phase 3)|Integration Testing (Phase 3)]]
- [[_COMMUNITY_JSON Parsing & Extraction|JSON Parsing & Extraction]]
- [[_COMMUNITY_System Architecture (Semantic)|System Architecture (Semantic)]]
- [[_COMMUNITY_Orchestrator Testing|Orchestrator Testing]]
- [[_COMMUNITY_SkySaver Core Concepts|SkySaver Core Concepts]]
- [[_COMMUNITY_Database & Queries|Database & Queries]]
- [[_COMMUNITY_TinyFish Reset Logic|TinyFish Reset Logic]]
- [[_COMMUNITY_Amadeus Reset Logic|Amadeus Reset Logic]]
- [[_COMMUNITY_Logger Utility|Logger Utility]]
- [[_COMMUNITY_Gemini Flash Config|Gemini Flash Config]]
- [[_COMMUNITY_Gemini Pro Config|Gemini Pro Config]]
- [[_COMMUNITY_Alert Decision logic|Alert Decision logic]]
- [[_COMMUNITY_Base Agent Utils|Base Agent Utils]]
- [[_COMMUNITY_Init DB logic|Init DB logic]]
- [[_COMMUNITY_Gemini Flash Model|Gemini Flash Model]]
- [[_COMMUNITY_LightGBM Model|LightGBM Model]]
- [[_COMMUNITY_Requests Library|Requests Library]]
- [[_COMMUNITY_LightGBM Library|LightGBM Library]]

## God Nodes (most connected - your core abstractions)
1. `RateLimiter` - 104 edges
2. `AnalysisReport` - 41 edges
3. `ForecastScore` - 41 edges
4. `RouteScraperAgent` - 36 edges
5. `AmadeusClient` - 31 edges
6. `TinyFishRateLimitError` - 29 edges
7. `TinyFishClient` - 29 edges
8. `TinyFishInvalidResponseError` - 28 edges
9. `ScraperOrchestrator` - 28 edges
10. `AmadeusServerError` - 27 edges

## Surprising Connections (you probably didn't know these)
- `RateLimiter` --uses--> `Extract an integer INR fare from a raw price string.      Handles every real-wor`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Map a raw airline name to its canonical form.      Lookup is case-insensitive on`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Remove leading/trailing markdown code fences from *text*.      TinyFish sometime`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Extract the first JSON array substring from *text*.      Finds the first ``[`` a`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py
- `RateLimiter` --uses--> `Parse a raw TinyFish response string into a list of ScrapedFare.      Processing`  [INFERRED]
  agents\rate_limiter.py → agents\scraper_agent.py

## Communities

### Community 0 - "Rate Limiting & API Clients"
Cohesion: 0.05
Nodes (87): RateLimiter, Thread-safe rate limiter with JSON persistence across restarts.      All public, AmadeusClient, AmadeusServerError, _build_google_flights_goal(), _build_skyscanner_goal(), _call_browser_with_retry(), _call_fetch_with_retry() (+79 more)

### Community 1 - "Alert Engine Implementation"
Cohesion: 0.05
Nodes (71): AlertDecision, AlertEngine, _build_skyscanner_url(), evaluate_alert(), _fmt_inr(), format_alert_message(), _format_alert_timestamp(), _format_route_display() (+63 more)

### Community 2 - "Database Initialization & Config"
Cohesion: 0.05
Nodes (65): _check_sqlite_version(), create_tables(), _ensure_db_dir_writable(), load_routes_from_config(), db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth, Create all 5 tables and their indexes. Safe to run multiple times.      Raises:, Parse config/routes.yaml and upsert every route into monitored_routes.      Args, Check that all 5 tables exist with all expected columns.      Returns:         T (+57 more)

### Community 3 - "Database Unit Tests"
Cohesion: 0.05
Nodes (12): _insert(), tests/test_db.py — Comprehensive pytest suite for db/queries.py and db/init_db.p, Hardcoded 20 prices — P10 must be exactly prices[1] (nearest rank)., Shortcut to insert one observation with sensible defaults., 10 threads each insert 5 rows — total must be 50, no corruption., TestAlertLog, TestGetAlertDecision, TestGetObservationCountByRoute (+4 more)

### Community 4 - "Forecast Engine & Feature Engineering"
Cohesion: 0.06
Nodes (29): build_features(), _ensure_models_dir(), ForecastEngine, generate_labels(), _latest_model_path(), _list_model_files(), _load_all_price_data(), _next_version() (+21 more)

### Community 5 - "Rate Limiter Logic"
Cohesion: 0.08
Nodes (23): _empty_state(), agents/rate_limiter.py — Per-route and per-API rate limit enforcement.  Persists, Return ``True`` if enough time has elapsed since this route+date was scraped., Return ``True`` if TinyFish Browser calls today are below the safe limit., Return ``True`` if TinyFish Fetch calls today are below the safe limit., Return ``True`` if Amadeus API calls today are below the safe limit.          Au, Record that a scrape attempt just completed for this route+date.          Update, Increment the TinyFish call counter for *endpoint*.          Args:             e (+15 more)

### Community 6 - "Agent Configuration & Logging"
Cohesion: 0.07
Nodes (27): get_claude_sonnet_config(), get_gemini_flash_config(), get_gemini_pro_config(), get_logger(), _JsonFormatter, load_env(), agents/base_agent.py — Shared base utilities for all SkySaver agents.  Provides:, Return a configured logger with JSON formatter.      Idempotent — calling this t (+19 more)

### Community 7 - "Data Normalization"
Cohesion: 0.11
Nodes (9): _normalise_airline(), _parse_price_inr(), _parse_single_tinyfish_fare(), Convert one Amadeus offer dict to a ScrapedFare.          Args:             offe, Extract an integer INR fare from a raw price string.      Handles every real-wor, Map a raw airline name to its canonical form.      Lookup is case-insensitive on, Attempt to parse one raw fare dict into a ScrapedFare.      Args:         item:, TestNormaliseAirline (+1 more)

### Community 8 - "Integration Testing (Phase 3)"
Cohesion: 0.18
Nodes (5): _make_chat_result(), _make_summary(), test_returns_analysis_report(), TestAnalyzerAgent, TestPipelineRunner

### Community 9 - "JSON Parsing & Extraction"
Cohesion: 0.2
Nodes (7): _extract_json_array(), _parse_tinyfish_response(), Remove leading/trailing markdown code fences from *text*.      TinyFish sometime, Extract the first JSON array substring from *text*.      Finds the first ``[`` a, Parse a raw TinyFish response string into a list of ScrapedFare.      Processing, _strip_markdown_fences(), TestParseTinyFishResponse

### Community 10 - "System Architecture (Semantic)"
Cohesion: 0.17
Nodes (12): AG2 (AutoGen), Alert Engine, AmadeusClient, RateLimiter, RouteScraperAgent, ScraperOrchestrator, SkySaver, TinyFishClient (+4 more)

### Community 11 - "Orchestrator Testing"
Cohesion: 0.56
Nodes (1): TestScraperOrchestrator

### Community 12 - "SkySaver Core Concepts"
Cohesion: 0.29
Nodes (8): SkySaver Project, insert_price_observation, update_price_stats, RateLimiter, AmadeusClient, RouteScraperAgent, ScraperOrchestrator, TinyFishClient

### Community 13 - "Database & Queries"
Cohesion: 1.0
Nodes (2): queries, SQLite Database

### Community 16 - "TinyFish Reset Logic"
Cohesion: 1.0
Nodes (1): Zero TinyFish counters if the stored date differs from today (UTC).

### Community 17 - "Amadeus Reset Logic"
Cohesion: 1.0
Nodes (1): Zero Amadeus counter if the stored date differs from today (UTC).

### Community 19 - "Logger Utility"
Cohesion: 1.0
Nodes (1): get_logger

### Community 20 - "Gemini Flash Config"
Cohesion: 1.0
Nodes (1): get_gemini_flash_config

### Community 21 - "Gemini Pro Config"
Cohesion: 1.0
Nodes (1): get_gemini_pro_config

### Community 22 - "Alert Decision logic"
Cohesion: 1.0
Nodes (1): get_alert_decision

### Community 23 - "Base Agent Utils"
Cohesion: 1.0
Nodes (1): BaseAgent

### Community 24 - "Init DB logic"
Cohesion: 1.0
Nodes (1): init_db

### Community 25 - "Gemini Flash Model"
Cohesion: 1.0
Nodes (1): Gemini Flash

### Community 26 - "LightGBM Model"
Cohesion: 1.0
Nodes (1): LightGBM

### Community 27 - "Requests Library"
Cohesion: 1.0
Nodes (1): requests

### Community 28 - "LightGBM Library"
Cohesion: 1.0
Nodes (1): lightgbm

## Knowledge Gaps
- **123 isolated node(s):** `db/init_db.py — Database initializer for SkySaver.  Run once on first boot (pyth`, `Create all 5 tables and their indexes. Safe to run multiple times.      Raises:`, `Parse config/routes.yaml and upsert every route into monitored_routes.      Args`, `Check that all 5 tables exist with all expected columns.      Returns:         T`, `Raise PermissionError if the database directory is not writable.` (+118 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Orchestrator Testing`** (9 nodes): `TestScraperOrchestrator`, `._make_orchestrator()`, `._patch_sleep()`, `.test_cooldown_routes_skipped()`, `.test_one_route_fail_others_continue()`, `.test_run_multiple_routes()`, `.test_run_no_routes_returns_empty()`, `.test_scrape_run_result_accurate()`, `.test_stats_recalculated_after_scrape()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Database & Queries`** (2 nodes): `queries`, `SQLite Database`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `TinyFish Reset Logic`** (1 nodes): `Zero TinyFish counters if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Amadeus Reset Logic`** (1 nodes): `Zero Amadeus counter if the stored date differs from today (UTC).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Logger Utility`** (1 nodes): `get_logger`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Gemini Flash Config`** (1 nodes): `get_gemini_flash_config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Gemini Pro Config`** (1 nodes): `get_gemini_pro_config`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Alert Decision logic`** (1 nodes): `get_alert_decision`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Base Agent Utils`** (1 nodes): `BaseAgent`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Init DB logic`** (1 nodes): `init_db`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Gemini Flash Model`** (1 nodes): `Gemini Flash`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `LightGBM Model`** (1 nodes): `LightGBM`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Requests Library`** (1 nodes): `requests`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `LightGBM Library`** (1 nodes): `lightgbm`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RateLimiter` connect `Rate Limiting & API Clients` to `Rate Limiter Logic`, `Agent Configuration & Logging`, `Data Normalization`, `JSON Parsing & Extraction`, `Orchestrator Testing`?**
  _High betweenness centrality (0.160) - this node is a cross-community bridge._
- **Why does `create_tables()` connect `Database Initialization & Config` to `Rate Limiting & API Clients`?**
  _High betweenness centrality (0.140) - this node is a cross-community bridge._
- **Why does `fresh_db()` connect `Rate Limiting & API Clients` to `Database Initialization & Config`?**
  _High betweenness centrality (0.120) - this node is a cross-community bridge._
- **Are the 89 inferred relationships involving `RateLimiter` (e.g. with `ScraperError` and `RouteScrapeFailed`) actually correct?**
  _`RateLimiter` has 89 INFERRED edges - model-reasoned connections that need verification._
- **Are the 37 inferred relationships involving `AnalysisReport` (e.g. with `AlertDecision` and `AlertEngine`) actually correct?**
  _`AnalysisReport` has 37 INFERRED edges - model-reasoned connections that need verification._
- **Are the 38 inferred relationships involving `ForecastScore` (e.g. with `AlertDecision` and `AlertEngine`) actually correct?**
  _`ForecastScore` has 38 INFERRED edges - model-reasoned connections that need verification._
- **Are the 24 inferred relationships involving `RouteScraperAgent` (e.g. with `RateLimiter` and `TestParsePriceInr`) actually correct?**
  _`RouteScraperAgent` has 24 INFERRED edges - model-reasoned connections that need verification._