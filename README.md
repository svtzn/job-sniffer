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

**Job Sniffer** is a self-hosted Telegram bot for searching and monitoring job vacancies.

The project currently focuses on **HH.ru** and uses browser-based scraping with Playwright instead of the official HH API.

The goal is to turn the usual job search into a personalized vacancy monitoring system.

- Define what kind of jobs you want
- Search vacancies directly from Telegram
- Apply custom filters
- Receive relevant vacancies automatically

The architecture is designed with multiple job platforms in mind, so HH.ru is only the first supported source.

---

## ✨ Features

- 🔎 Vacancy search through Telegram
- 🕵️ HH.ru browser scraping
- 🎭 Playwright + playwright-stealth
- 🍲 BeautifulSoup HTML parsing
- 🎛️ Vacancy filtering
- 📄 Paginated search results
- 🌐 Proxy support
- 🧩 Extensible sniffer architecture
- 🐳 Docker-ready

---

## 🛠️ Tech Stack

| Technology | Purpose |
|------------|---------|
| Python 3.12 | Core application |
| aiogram | Telegram Bot API |
| Playwright | Browser automation |
| playwright-stealth | Automation detection mitigation |
| BeautifulSoup4 | HTML parsing |
| SQLAlchemy | Database ORM |
| PostgreSQL | Persistent storage |
| Alembic | Database migrations |
| Pydantic | Data validation |
| pydantic-settings | Configuration |
| Docker | Containerization |
| uv | Dependency management |

---

## 📁 Project Structure

job-sniffer/
├── app/
│   ├── main.py
│   ├── config.py
│   │
│   ├── db/
│   │   └── base.py
│   │
│   ├── models/
│   │   ├── vacancy.py
│   │   ├── subscription.py
│   │   └── subscription_vacancy.py
│   │
│   ├── services/
│   │   └── search.py        # SearchFilters -> HHQuery -> SearchResult
│   │
│   ├── sniffers/
│   │   ├── base.py
│   │   ├── schemas.py       # VacancyData, Salary, SearchResult
│   │   └── hh/
│   │       ├── sniffer.py   # пагинация + дедупликация
│   │       ├── parser.py    # JSON HH-Lux-InitialState, HTML как fallback
│   │       └── query.py
│   │
│   └── telegram/
│       ├── bot.py
│       ├── handlers.py      # только UI-логика
│       ├── keyboards.py     # inline-кнопки и CallbackData
│       ├── formatter.py     # HTML-тексты сообщений
│       ├── labels.py        # подписи для кодов HH
│       └── state.py         # состояние чата (в памяти)
│
├── docs/
│   ├── job-sniffer-technical-specification.md
│   └── hh-russia-parsing-analysis.md
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
└── README.md

---

## 🚀 Current Status

The first working prototype currently supports:

- Telegram-based vacancy search
- Basic vacancy filters
- HH.ru scraping
- HTML parsing
- Vacancy normalization
- Paginated search results
- Proxy support

### Current filters

Work format:
- Remote
- Hybrid
- On-site

Employment:
- Full-time
- Part-time

Experience:
- No experience
- 1–3 years
- 3–6 years
- 6+ years

---

## 🗺️ Roadmap

### Phase 1 — HH Sniffer

- [x] Playwright integration
- [x] HH.ru page retrieval
- [x] HTML parsing
- [x] Vacancy normalization
- [x] Basic search

### Phase 2 — Search Engine

- [ ] Advanced filters
- [ ] Multi-filter search
- [ ] Location-aware filters
- [ ] Custom search presets

### Phase 3 — Persistence

- [ ] PostgreSQL integration
- [ ] User storage
- [ ] Vacancy storage
- [ ] Search history
- [ ] Duplicate detection

### Phase 4 — Subscriptions

- [ ] Saved searches
- [ ] Vacancy subscriptions
- [ ] Background polling
- [ ] New vacancy detection

### Phase 5 — Notifications

- [ ] Automatic Telegram notifications
- [ ] Notification preferences
- [ ] Vacancy deduplication
- [ ] Per-search notification settings

### Phase 6 — Multi-source

- [ ] Additional job platforms
- [ ] Unified vacancy model
- [ ] Source-specific sniffers
- [ ] Cross-platform search

---

## 🎯 Vision

Job Sniffer is intended to evolve from a simple vacancy search bot into a personal job-search automation tool.

Search manually
      ↓
Save your filters
      ↓
Run searches automatically
      ↓
Detect new vacancies
      ↓
Get notified
      ↓
Apply

The end goal is simple:

> You define what you're looking for. Job Sniffer does the boring part.

---

## ⚠️ Disclaimer

Job Sniffer is a personal self-hosted project intended for educational and research purposes.

The project does not use the official HH.ru API for vacancy retrieval. Website structure and anti-bot mechanisms may change over time, which can require updates to the corresponding sniffer.