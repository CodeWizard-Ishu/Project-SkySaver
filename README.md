<div align="center">

# ✈️ SkySaver

### Your Personal Flight Price Watchdog — Automatically Finds the Best Fares & Alerts You

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![AG2](https://img.shields.io/badge/AG2%20AutoGen-0.9+-FF6B35?style=for-the-badge)](https://github.com/ag2ai/ag2)
[![Gemini](https://img.shields.io/badge/Gemini%20AI-Flash%20%7C%20Pro-4285F4?style=for-the-badge&logo=google&logoColor=white)](https://deepmind.google/gemini)
[![SQLite](https://img.shields.io/badge/SQLite-Database-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-00D4AA?style=for-the-badge)](LICENSE)

> **Stop manually checking flight prices every day.**  
> SkySaver watches flight routes for you 24/7, learns what a "normal" price looks like, and fires an alert the moment a genuinely good deal appears.

</div>

---

## 🤔 What Is SkySaver?

Imagine having a smart assistant that:
- **Checks flight prices** on your favourite routes every day, automatically
- **Remembers historical prices** and builds a picture of what's cheap vs expensive
- **Sends you an alert** only when the price is *genuinely* low — not just a random fluctuation
- **Never spams you** — it respects cooldown periods so you only get meaningful notifications
- **Predicts future prices** using a trained ML model so you know whether to book now or wait

That's SkySaver. It's a Python-based backend system that runs quietly in the background, scrapes flight data from multiple sources, stores it in a database, uses smart statistics to decide when a price is worth your attention, and employs a ML Forecast Engine to score upcoming prices.

---

## ✨ Key Features

- 🔍 **Multi-Source Scraping** — Pulls prices from TinyFish (Google Flights + Skyscanner) and Amadeus API as a fallback
- 🧠 **Smart Alert Logic** — Only alerts when a price falls below the 10th percentile (bottom 10%) of historical prices for that route
- 🔄 **Auto Retry & Fallback** — If one data source fails or rate-limits, it automatically tries the next one
- 🛡️ **Rate Limit Protection** — Tracks daily API usage and enforces cooldowns so you never get banned
- 💾 **Persistent Memory** — All prices, stats, and alert history are saved in a local SQLite database
- 🤖 **AI-Powered** — Built on AG2 (AutoGen) framework with Google Gemini Flash/Pro and Claude Sonnet support
- 📊 **Price Statistics** — Calculates P10, P50, P90 percentile baselines per route automatically
- 📈 **ML Forecast Engine** — LightGBM-based model generates a `ForecastScore` with feature engineering and versioned model files
- 🔔 **Alert Engine** — Dedicated `AlertEngine` module evaluates `AlertDecision` objects and formats rich alert messages
- 🧪 **Fully Tested** — Comprehensive pytest test suite covering all core logic including Phase 3 integration tests

---

## 🗺️ How It Works — Simple Version

```
Every scheduled run:

1. 📋 Load all monitored flight routes from config
        ↓
2. ✈️  For each route + travel date:
        ↓
3. 🚦 Check rate limits (is it too soon to scrape this again?)
        ↓
4. 🌐 Fetch prices → TinyFish Browser → TinyFish Fetch → Amadeus (in that order)
        ↓
5. 🧹 Clean & normalise the data (remove duplicates, validate dates, parse prices)
        ↓
6. 💾 Save to database & update price statistics
        ↓
7. 📈 Run Forecast Engine → generate ForecastScore for the route
        ↓
8. 🔔 AlertEngine checks: Is today's price in the bottom 10% historically?
        ↓
9. 📊 Produce AnalysisReport with price trend + forecast summary
        ↓
10. 📣 YES → Fire alert! | NO → Sleep and try again next run
```

---

## 🏗️ Project Structure

```
Project - SkySaver/
│
├── 🤖 agents/
│   ├── base_agent.py        ← Shared utilities: logger, env loader, AI model configs
│   ├── rate_limiter.py      ← Tracks & enforces API call limits (thread-safe)
│   └── scraper_agent.py     ← Core scraping logic: TinyFish + Amadeus + Orchestrator
│
├── 🗄️ db/
│   ├── init_db.py           ← Creates database tables on first boot
│   └── queries.py           ← All database read/write operations + alert decisions
│
├── 🔔 alerts/
│   └── alert_engine.py      ← AlertEngine: evaluates AlertDecision + formats messages
│
├── 📈 forecast/
│   └── forecast_engine.py   ← ForecastEngine: LightGBM model, feature engineering, versioned model files
│
├── 🧪 tests/
│   ├── test_db.py           ← Tests for database layer
│   ├── test_scraper.py      ← Tests for scraping agents
│   └── test_integration.py  ← Phase 3 integration tests (PipelineRunner + AnalyzerAgent)
│
├── ⚙️ config/
│   └── routes.yaml          ← List of flight routes to monitor (e.g. BOM-DEL)
│
├── 🧠 memory-bank/
│   ├── projectbrief.md      ← Project goals & vision
│   └── techContext.md       ← Technical decisions & context
│
├── requirements.txt         ← All Python dependencies
└── .env                     ← Your API keys (never commit this!)
```

---

## 🧩 Core Components Explained

### For Non-Developers

| What It Does | The Component |
|---|---|
| 🎯 Coordinates the whole scraping run | **ScraperOrchestrator** |
| 🔎 Handles scraping for one specific route & date | **RouteScraperAgent** |
| 🌐 Gets prices from Google Flights / Skyscanner | **TinyFishClient** |
| ✈️ Gets prices from Amadeus (backup source) | **AmadeusClient** |
| 🚦 Makes sure we don't call APIs too often | **RateLimiter** |
| 🗃️ Stores and retrieves all price data | **SQLite Database** |
| 🔔 Decides if a price is good enough to alert | **AlertEngine** |
| 📈 Predicts whether a price will rise or drop | **ForecastEngine** |
| 📊 Summarises a full price analysis run | **AnalysisReport** |

### For Developers

| Class / Module | File | Responsibility |
|---|---|---|
| `ScraperOrchestrator` | `agents/scraper_agent.py` | Manages full scrape lifecycle across all routes |
| `RouteScraperAgent` | `agents/scraper_agent.py` | Single route scraper with priority-ordered multi-source fallback |
| `TinyFishClient` | `agents/scraper_agent.py` | Browser + Fetch API wrapper with per-endpoint retry logic |
| `AmadeusClient` | `agents/scraper_agent.py` | Amadeus SDK wrapper with error mapping and normalisation |
| `RateLimiter` | `agents/rate_limiter.py` | Thread-safe, JSON-persisted rate limiter for all APIs |
| `BaseAgent` | `agents/base_agent.py` | Logger, `.env` loader, Gemini/Claude config factory |
| `AlertEngine` | `alerts/alert_engine.py` | Evaluates `AlertDecision`, formats alert messages, logs to DB |
| `ForecastEngine` | `forecast/forecast_engine.py` | LightGBM price prediction, feature engineering, versioned model files |
| `AnalysisReport` | *(pipeline output)* | Aggregated output of a full scrape + alert + forecast pipeline run |
| `init_db` | `db/init_db.py` | Creates 5 DB tables + indexes, loads routes from YAML |
| `queries` | `db/queries.py` | All SQL: insert, update, alert decision, percentile computation |

---

## 🗄️ Database Tables

SkySaver stores everything in a local **SQLite** database (no setup needed — it creates itself):

| Table | What's Stored |
|---|---|
| `monitored_routes` | Flight routes you want to track (e.g. BOM→DEL) |
| `price_observations` | Every single price data point ever collected |
| `price_stats` | Computed P10 / P50 / P90 baselines per route |
| `alert_log` | History of every alert ever fired (prevents spam) |
| `forecast_scores` | ML-generated ForecastScore records per route + date |

---

## 🤖 AI & Tech Stack

SkySaver is built on the **AG2 (AutoGen)** AI agent framework and supports multiple AI models:

| Tool / Library | What It's Used For |
|---|---|
| `AG2 (AutoGen)` | Core AI agent framework |
| `Gemini Flash` | Fast, lightweight AI tasks |
| `Gemini Pro` | Advanced reasoning tasks |
| `Claude Sonnet` | Alternative LLM option |
| `Amadeus SDK` | Official flight data API |
| `TinyFish API` | Browser-based flight scraping |
| `SQLite` | Local database (zero config) |
| `Tenacity` | Automatic retry logic on failures |
| `FileLock` | Thread-safe file operations |
| `LightGBM` | ML price forecasting (Phase 4 — active) |
| `PyTorch` | Deep learning support for future model experiments |
| `requests` | HTTP client for API calls |
| `pytest` | Automated testing |

---

## 🚀 Getting Started

### Prerequisites
- Python 3.11 or higher
- API keys for: Amadeus, TinyFish, and Gemini (or Claude)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-username/skysaver.git
cd skysaver

# 2. Create a virtual environment
python -m venv venv
source venv/bin/activate        # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up your API keys
cp .env.example .env
# Edit .env and fill in your keys

# 5. Initialise the database
python -m db.init_db

# 6. Add routes to monitor
# Edit config/routes.yaml — add your flight routes (e.g. BOM-DEL)

# 7. Run SkySaver!
python -m agents.scraper_agent
```

### Configure Routes

Edit `config/routes.yaml` to add the flight routes you want to monitor:

```yaml
routes:
  - origin: BOM        # Mumbai
    destination: DEL   # Delhi
  - origin: BLR        # Bengaluru
    destination: HYD   # Hyderabad
```

### Environment Variables (`.env`)

```env
AMADEUS_CLIENT_ID=your_amadeus_key
AMADEUS_CLIENT_SECRET=your_amadeus_secret
TINYFISH_API_KEY=your_tinyfish_key
GEMINI_API_KEY=your_gemini_key
```

---

## 🧪 Running Tests

```bash
# Run all tests
pytest

# Run with detailed output
pytest -v

# Run only database tests
pytest tests/test_db.py

# Run only scraper tests
pytest tests/test_scraper.py

# Run Phase 3 integration tests
pytest tests/test_integration.py
```

---

## 🔔 How the Alert System Works

SkySaver uses **percentile-based statistics** combined with the **AlertEngine** to make smart alert decisions — not simple price thresholds.

1. Every price observation is saved to the database
2. After enough data is collected, SkySaver computes the **P10 baseline** — the price below which only 10% of historical observations fall
3. When a new price comes in **below the P10**, `AlertEngine` evaluates the `AlertDecision` object
4. A cooldown check prevents duplicate alerts for the same route within a short period
5. If both checks pass → `AlertEngine` **fires the alert and formats the message** 🔔

> **In plain English:** If a flight normally costs ₹5,000–₹12,000 and today it's ₹3,800, SkySaver recognises that's in the bottom 10% of prices ever seen — and tells you immediately.

---

## 📈 Forecast Engine

The **ForecastEngine** uses a trained **LightGBM** model to predict whether a flight price is likely to rise or fall, giving you a `ForecastScore` alongside every alert.

- `build_features()` — Extracts time-series and route-based features from historical price data
- `generate_labels()` — Auto-labels training data (price went up / down) for supervised learning
- `_load_all_price_data()` — Reads the full observation history from SQLite for training
- **Versioned model files** — Each trained model is saved with a version number; `_latest_model_path()` always loads the most recent one
- `AnalysisReport` — The combined output of a full pipeline run: scrape results + alert decision + forecast score

---

## 🛡️ Rate Limiting — Staying Safe

SkySaver tracks every API call and enforces limits automatically:

- **Per-route cooldown** — Won't scrape the same route+date twice within a set interval
- **Daily TinyFish limits** — Separate counters for Browser and Fetch endpoints
- **Daily Amadeus limits** — Tracks usage and auto-resets at midnight UTC
- **JSON persistence** — Rate limit state survives restarts (saved to disk)
- **Thread-safe** — Multiple scraping threads won't corrupt the counters

---

## 🗺️ Roadmap

- [x] **Phase 1** — Core scraping engine (TinyFish + Amadeus)
- [x] **Phase 2** — SQLite database + alert decision logic
- [x] **Phase 3** — Rate limiting + multi-source fallback + integration tests
- [x] **Phase 4** — ML price prediction with LightGBM (ForecastEngine — active)
- [ ] **Phase 5** — Telegram bot integration for alerts
- [ ] **Phase 6** — Web dashboard for price history visualisation

---

## 🤝 Contributing

Contributions are welcome! Here's how to get started:

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature-name`
3. Make your changes and add tests
4. Run the test suite: `pytest`
5. Submit a Pull Request

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<div align="center">

Built with ❤️ by **Utkarsh Jaiswal**

*Never overpay for flights again.*

</div>
