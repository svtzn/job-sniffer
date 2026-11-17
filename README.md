<h1 align="center">
  🐽
</h1>

<h1 align="center">Job Sniffer</h1>

<p align="center">
  Personal job vacancy aggregator powered by Telegram and Playwright.
</p>

<p align="center">
  Search. Filter. Sniff.
</p>

---

## 🕵️ About

**Job Sniffer** is a self-hosted Telegram bot for searching job vacancies on **HH.ru**.

It drives a real browser (Playwright) instead of the official HH API, reads the structured
vacancy data HH embeds into its search pages and shows the results in Telegram with filters
that the HH website itself can't combine — for example, *remote jobs anywhere in Russia*
**plus** *office jobs in your own city* in a single result list.

---

## ✨ Features

- 🔎 Vacancy search right from Telegram
- 📍 Multi-location filters: up to 4 "area + work format" rules merged into one result list
- 🎛️ Filters: experience, employment type, "only with salary"
- 💰 Accurate salary data (from/to, currency, gross/net) from HH's embedded page state
- 📄 Paginated results with deduplication across pages and locations
- 💾 Saved filters: save, rename, run, edit, delete (`/myfilters`)
- 🗃️ Every search result is stored in a local SQLite database
- 🌐 Telegram proxy support

---

## 🚀 Quick Start

Requirements: Python 3.12+, [uv](https://docs.astral.sh/uv/), a Telegram bot token from [@BotFather](https://t.me/BotFather).

```bash
uv sync
```

```bash
uv run playwright install chromium
```

Copy `.env.example` to `.env` and set `TELEGRAM_BOT_TOKEN` (see [Configuration](#️-configuration)), then start the bot:

```bash
uv run python -m app.telegram.bot
```

Database migrations are applied automatically on startup.

---

## 🤖 Bot Usage

| Command | What it does |
|---|---|
| `/start` | Help and the filter panel |
| `/filters` | Filter panel: locations, experience, employment, salary |
| `/search <text>` | Search with current filters (without text — repeat the last query) |
| `/myfilters` | Saved filters |
| `/help` | Help |

Any plain text message is treated as a search query with the current filters.

---

## ⚙️ Configuration

All settings live in `.env` (see `.env.example`). Empty values fall back to defaults.

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Bot token (required) |
| `TELEGRAM_PROXY_URL` | — | Proxy for Telegram, e.g. `http://127.0.0.1:10809` |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/jobs.db` | Relative SQLite paths are resolved from the project root |
| `HEADLESS` | `true` | Run Chromium without a window |
| `DELAY_MIN` / `DELAY_MAX` | `2.0` / `5.0` | Random delay between HH page loads, seconds |
| `HH_BASE_URL` | `https://krasnodar.hh.ru/search/vacancy` | HH search page |
| `SEARCH_LIMIT` | `100` | Max vacancies collected per search |
| `RESULTS_PAGE_SIZE` | `5` | Vacancies per page in the bot |
| `HOME_AREA_ID` | `53` | HH area id for the "Remote + my city" preset (53 — Krasnodar, 1 — Moscow, 2 — St. Petersburg) |

Browser fingerprint settings (`VIEWPORT_*`, `LOCALE`, `TIMEZONE_ID`, `HH_WAIT_UNTIL`) rarely need changes.

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Core application |
| aiogram 3 | Telegram Bot API |
| Playwright | Browser automation |
| BeautifulSoup4 | HTML parsing |
| SQLAlchemy 2 (async) + aiosqlite | Storage |
| Alembic | Database migrations |
| pydantic-settings | Configuration |
| uv | Dependency management |

---

## 📁 Project Structure

```text
job-sniffer/
├── app/
│   ├── config.py               # settings from .env
│   ├── main.py                 # manual search run without Telegram
│   │
│   ├── sniffers/               # getting data from job sites
│   │   ├── base.py             # browser lifecycle
│   │   ├── schemas.py          # VacancyData, Salary, SearchResult
│   │   └── hh/
│   │       ├── query.py        # HH search URL parameters
│   │       ├── parser.py       # HH-Lux-InitialState JSON, HTML cards as fallback
│   │       └── sniffer.py      # pagination + deduplication
│   │
│   ├── services/               # business logic, independent of Telegram
│   │   ├── filters.py          # SearchFilters, LocationRule
│   │   ├── search.py           # one request per location -> merged result
│   │   └── saved_filters.py    # saved filters CRUD
│   │
│   ├── db/                     # engine, session, types, migrations runner
│   ├── models/                 # Vacancy, SavedFilter, FilterVacancy
│   ├── repositories/           # all SQL lives here
│   │
│   └── telegram/
│       ├── bot.py              # entry point
│       ├── handlers.py         # UI logic only
│       ├── keyboards.py        # inline keyboards, CallbackData
│       ├── formatter.py        # message texts (HTML)
│       ├── labels.py           # human-readable HH codes
│       └── state.py            # per-chat state in memory
│
├── alembic/                    # migrations
├── alembic.ini
├── .env.example
└── pyproject.toml
```

---

## 💾 Database

SQLite file `data/jobs.db` (created automatically). Manual migration commands:

```bash
uv run alembic upgrade head
```

```bash
uv run alembic revision --autogenerate -m "describe change"
```

---

## ⚠️ Disclaimer

Job Sniffer is a personal self-hosted project intended for educational and research purposes.

The project does not use the official HH.ru API. Website structure and anti-bot mechanisms
may change over time, which can require updates to the corresponding sniffer.
