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
- 🔔 Subscriptions: new vacancies for saved filters arrive automatically, without duplicates
- 🚫 Exclude words (senior, lead, 1С …) for search results and subscriptions
- 🌙 Quiet hours and digests instead of message floods
- 🗃️ Every search result is stored in a local SQLite database
- 🌐 Telegram proxy support

---

## 🚀 Quick Start

Requirements: Windows, [uv](https://docs.astral.sh/uv/), a Telegram bot token from [@BotFather](https://t.me/BotFather).

**Windows:** double-click `start.bat`. On the first run it installs dependencies and Chromium,
creates `.env` and opens it so you can paste `TELEGRAM_BOT_TOKEN`; next runs just start the bot.

**Manually** (any OS):

```bash
uv sync
```

```bash
uv run playwright install chromium
```

Copy `.env.example` to `.env`, set `TELEGRAM_BOT_TOKEN` (see [Configuration](#️-configuration)), then:

```bash
uv run job-sniffer
```

Database migrations are applied automatically on startup. If Telegram is blocked for you,
see [If Telegram is blocked](#-if-telegram-is-blocked).

---

## 🤖 Bot Usage

| Command | What it does |
|---|---|
| `/start` | Help and the filter panel |
| `/filters` | Filter panel: locations, experience, employment, salary |
| `/search <text>` | Search with current filters (without text — repeat the last query) |
| `/myfilters` | Saved filters: run ▶️, subscribe 🔔/🔕, edit ✏️, delete 🗑 |
| `/help` | Help |

Any plain text message is treated as a search query with the current filters.

**Subscriptions.** Turn on 🔔 for a saved filter and the bot checks HH every few minutes. The first check
only remembers current vacancies; after that only new ones are sent, each once, even if it matches several
filters. Too many at once → one digest. "🙈 Not interested" hides a vacancy.

---

## ⚙️ Configuration

All settings live in `.env` (see `.env.example`). Empty values fall back to defaults.

| Variable | Default | Description |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | — | Bot token (required) |
| `TELEGRAM_PROXY_URL` | — | Proxy for Telegram, e.g. `http://127.0.0.1:10809` |
| `TELEGRAM_API_BASE` | — | Own Bot API address instead of `api.telegram.org` (e.g. a Cloudflare Worker) |
| `TELEGRAM_KEEPALIVE` | auto | Reuse connections to Telegram; auto = off when `TELEGRAM_API_BASE` is set |
| `TELEGRAM_TIMEOUT` | `15` | Seconds per Telegram request |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/jobs.db` | Relative SQLite paths are resolved from the project root |
| `HEADLESS` | `true` | Run Chromium without a window |
| `DELAY_MIN` / `DELAY_MAX` | `2.0` / `5.0` | Random delay between HH page loads, seconds |
| `HH_BASE_URL` | `https://krasnodar.hh.ru/search/vacancy` | HH search page |
| `SEARCH_LIMIT` | `100` | Max vacancies collected per search |
| `SEARCH_TIMEOUT_SECONDS` | `300` | A search taking longer is aborted and the browser is closed |
| `RESULTS_PAGE_SIZE` | `5` | Vacancies per page in the bot |
| `HOME_AREA_ID` | `53` | HH area id for the "Remote + my city" preset (53 — Krasnodar, 1 — Moscow, 2 — St. Petersburg) |
| `SUBSCRIPTION_INTERVAL_MINUTES` | `15` | How often subscriptions are checked |
| `SUBSCRIPTION_MAX_PER_CHECK` | `10` | More new vacancies at once are sent as one digest |
| `QUIET_HOURS` | — | e.g. `23-8`: no messages at night, a digest in the morning (local time) |

Browser fingerprint settings (`VIEWPORT_*`, `LOCALE`, `TIMEZONE_ID`, `HH_WAIT_UNTIL`) rarely need changes.

---

### 🔒 If Telegram is blocked

Nothing to do if Telegram works for you directly. Otherwise pick one:

- **VPN/proxy** on the same machine → `TELEGRAM_PROXY_URL=http://127.0.0.1:10809` (or `socks5://…`).
- **Own Bot API address** (e.g. a Cloudflare Worker that forwards requests to `api.telegram.org`) →
  `TELEGRAM_API_BASE=https://your-worker.workers.dev`. In this mode every request uses a fresh connection:
  some providers silently freeze long-lived connections to Cloudflare, which made requests hang.

---

### 🐧 Running on a Linux server

Same commands as in Quick Start (`uv sync`, `uv run playwright install --with-deps chromium`), then a systemd unit,
e.g. `/etc/systemd/system/job-sniffer.service`:

```ini
[Unit]
Description=Job Sniffer Telegram bot
After=network-online.target
Wants=network-online.target

[Service]
User=youruser
WorkingDirectory=/home/youruser/job-sniffer
ExecStart=/home/youruser/.local/bin/uv run job-sniffer
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Settings stay in `.env`. Logs: `journalctl -u job-sniffer -f`. To keep logs across reboots (off by default on Debian):
`sudo mkdir -p /var/log/journal && sudo systemctl restart systemd-journald`.

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
│   │   ├── saved_filters.py    # saved filters CRUD
│   │   └── subscriptions.py    # new-vacancy detection, notification queue, quiet hours
│   │
│   ├── db/                     # engine, session, types, migrations runner
│   ├── models/                 # Vacancy, SavedFilter, FilterVacancy
│   ├── repositories/           # all SQL lives here
│   │
│   └── telegram/
│       ├── bot.py              # entry point (`uv run job-sniffer`)
│       ├── notifier.py         # background subscription worker
│       ├── session.py          # Telegram connection: API address, proxy, timeouts
│       ├── handlers.py         # UI logic only
│       ├── keyboards.py        # inline keyboards, CallbackData
│       ├── formatter.py        # message texts (HTML)
│       ├── labels.py           # human-readable HH codes
│       └── state.py            # per-chat state in memory
│
├── tests/                      # pytest
├── alembic/                    # migrations
├── alembic.ini
├── .env.example
├── start.bat                   # quick start on Windows
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

## 🧪 Development

```bash
uv run pytest
```

```bash
uvx ruff check app tests
```

Tests use a temporary SQLite database, a fake HH search and a fake Telegram network — nothing leaves the machine.

---

## ⚠️ Disclaimer

Job Sniffer is a personal self-hosted project intended for educational and research purposes.

The project does not use the official HH.ru API. Website structure and anti-bot mechanisms
may change over time, which can require updates to the corresponding sniffer.
