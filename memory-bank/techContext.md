# Tech Stack Reference

## Server
Oracle Cloud A1 Always-Free: 4 vCPU ARM, 24 GB RAM, 200 GB SSD, Ubuntu 24.04

## IDE
Google Antigravity with Claude Sonnet 4.6 (reasoning) + Gemini 2.5 Flash (bulk)
Graphify installed for token efficiency — always reads graph, not raw files

## Scraping
Primary: TinyFish Web Agent API (natural language browser control, ARM64-compatible)
  - Endpoints: Search, Fetch, Browser, Agent
  - Handles CAPTCHAs and bot-protection natively
Backup: Amadeus Travel API (official, 500 calls/day free, no scraping needed)

## Agent Framework
AG2 (AutoGen) — Python multi-agent orchestration
TinyFishTool — connects TinyFish to AG2 agents natively

## Scheduling
n8n Community Edition (self-hosted, Docker)
Runs every 6 hours: scrape → analyze → alert

## Conversational Interface
OpenClaw (Docker) — reads Telegram messages, natural language commands

## Database
Phase 1-7: SQLite (zero setup, file-based)
Phase 8+ (scale): TimescaleDB (PostgreSQL extension for time-series)

## ML
LightGBM: classifier — "is this price cheap?" (score 0.0–1.0)
PyTorch LSTM: regression — "what will price be in 7 days?"
Hybrid decision: alert only if LightGBM score > 0.8 AND LSTM forecasts price rising

## Key LLM Usage Rule
Claude Sonnet 4.6 (extended thinking): ONLY for reasoning decisions (~4 calls/day)
Gemini 2.5 Flash: everything else (parsing HTML, formatting messages, summaries)
Ratio target: 95% Gemini (free), 5% Claude (paid) → cost stays near ₹0