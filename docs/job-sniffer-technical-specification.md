# Job Sniffer — техническое задание

## 1. Общая идея

**Job Sniffer** — локально запускаемый сервис для поиска вакансий на HH.ru с более гибкой системой фильтрации, чем стандартный интерфейс HH, и с Telegram-интерфейсом.

Сервис должен поддерживать два основных сценария:

1. **Одноразовый поиск** — пользователь задаёт фильтры, получает список подходящих вакансий.
2. **Подписка на фильтр** — пользователь сохраняет фильтр, а Job Sniffer периодически проверяет HH и автоматически отправляет новые подходящие вакансии в Telegram.

На первом этапе реализуется **только HH.ru**, но архитектура должна позволять в дальнейшем добавлять другие источники вакансий без переделки основной бизнес-логики.

Приложение предназначено для локального запуска через Docker Compose.

---

# 2. Цели проекта

## Основные цели

- Получать вакансии с HH.ru.
- Поддерживать пользовательские фильтры.
- Позволять создавать несколько независимых фильтров.
- Поддерживать комбинации условий, которые неудобно или невозможно настроить стандартным поиском HH.
- Выполнять одноразовый поиск.
- Поддерживать постоянные подписки на фильтры.
- Отправлять новые вакансии в Telegram.
- Исключать дубликаты.
- Хранить историю найденных вакансий.
- Позволять управлять фильтрами и подписками через Telegram.
- Запускать весь проект локально одной командой через Docker Compose.

## Архитектурные цели

- Разделить получение вакансий, нормализацию, фильтрацию, хранение и уведомления.
- Не привязывать бизнес-логику к HH API.
- В дальнейшем добавить другие источники вакансий через отдельные адаптеры.
- Сделать систему пригодной для нескольких пользователей.

---

# 3. Пример основной задачи

Пользователь хочет искать:

### Фильтр №1 — Remote

- Python
- FastAPI
- Backend
- удалённая работа
- регион работодателя не важен
- опыт: 0–3 года
- зарплата от определённой суммы
- исключить Senior / Lead / Architect
- желательно PostgreSQL / Redis / Docker

### Фильтр №2 — Hybrid

- Python
- Backend
- гибрид
- только город пользователя
- опыт: 0–3 года
- зарплата от определённой суммы

На HH пользователь фактически вынужден переключаться между разными поисковыми конфигурациями.

Job Sniffer должен позволять хранить оба фильтра одновременно:

```text
Remote Python Backend
Hybrid Python Backend
```

и проверять их параллельно.

---

# 4. Основные сущности

## User

Telegram-пользователь.

Пример:

```text
User
- id
- telegram_id
- username
- created_at
- is_active
```

---

## Filter

Сохранённый поисковый профиль.

```text
Filter
- id
- user_id
- name
- enabled
- created_at
- updated_at
```

Фильтр содержит набор условий.

---

## FilterRule

Правила конкретного фильтра.

Условия могут включать:

- ключевые слова;
- обязательные слова;
- желательные слова;
- запрещённые слова;
- опыт;
- зарплату;
- формат работы;
- тип занятости;
- регион;
- профессиональную роль;
- расписание проверки;
- минимальный score.

---

## Vacancy

Нормализованная вакансия независимо от источника.

```text
Vacancy
- id
- source
- external_id
- title
- company
- description
- url
- salary_from
- salary_to
- currency
- employment
- experience
- area
- work_formats
- published_at
- fetched_at
```

Уникальность:

```text
(source, external_id)
```

---

## VacancyMatch

Результат применения конкретного фильтра к вакансии.

```text
VacancyMatch
- vacancy_id
- filter_id
- score
- matched_rules
- rejected_rules
- created_at
```

Это позволит одной вакансии соответствовать нескольким фильтрам пользователя.

---

## Notification

Информация об отправленных уведомлениях.

```text
Notification
- id
- user_id
- filter_id
- vacancy_id
- sent_at
- status
```

Основная задача — не отправить одну и ту же вакансию пользователю повторно.

---

# 5. Архитектура

Предполагаемая архитектура:

```text
                    Telegram
                       │
                       ▼
                ┌──────────────┐
                │ Telegram Bot │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │ Application  │
                │   Service    │
                └──────┬───────┘
                       │
          ┌────────────┼────────────┐
          │            │            │
          ▼            ▼            ▼
      Filters      Search       Subscriptions
          │            │            │
          └────────────┼────────────┘
                       ▼
                ┌──────────────┐
                │   Matcher    │
                └──────┬───────┘
                       │
                       ▼
                ┌──────────────┐
                │  Repository  │
                └──────┬───────┘
                       │
                       ▼
                 PostgreSQL

Background Worker
       │
       ▼
┌─────────────────┐
│   HH Sniffer    │
└────────┬────────┘
         ▼
   Normalizer
         ▼
   Deduplication
         ▼
   PostgreSQL
         ▼
   Matcher
         ▼
 Notifications
         ▼
 Telegram
```

---

# 6. Разделение на слои

## Sniffers

**Sniffer** — компонент, который отвечает за получение вакансий из конкретного источника.

Название `sniffer` является частью концепции Job Sniffer: каждый источник имеет собственного "сниффера", который знает, как искать и получать вакансии.

Первый источник:

```text
HHSniffer
```

Sniffer не должен знать:

- как работают пользовательские фильтры;
- кому отправлять вакансии;
- как считается score;
- как устроен Telegram;
- как работает бизнес-логика подписок.

Его задача:

```text
Source → получить вакансии → передать дальше
```

### Базовый интерфейс

Предполагается общий контракт:

```text
BaseSniffer
    sniff(...)
```

В будущем:

```text
BaseSniffer
├── HHSniffer
├── HabrSniffer
├── LinkedInSniffer
└── OtherSniffer
```

Каждый сниффер отвечает только за специфику своего источника.

---

# 7. Source Adapter

`BaseSniffer` должен выступать абстракцией источника вакансий.

Концептуально:

```text
BaseSniffer
    sniff(...)
```

Результатом работы сниффера должны быть данные, которые затем передаются в `Normalizer`.

Поток:

```text
HHSniffer
    │
    ▼
Raw HH vacancies
    │
    ▼
Normalizer
    │
    ▼
Normalized Vacancy
```

Важно не смешивать Sniffer и Normalizer.

**Sniffer знает, как добыть данные.**

**Normalizer знает, как привести данные к единому формату.**

Например, при добавлении нового источника:

```text
HHSniffer ──────┐
                │
HabrSniffer ────┼──→ Normalizer → Vacancy
                │
FutureSniffer ──┘
```

Matcher, Database и Telegram при этом не должны знать особенности конкретного источника.

---

# 8. Нормализация

Разные источники будут иметь разные форматы.

Поэтому после Collector данные преобразуются в единую внутреннюю модель:

```text
Raw HH Vacancy
       │
       ▼
   Normalizer
       │
       ▼
Normalized Vacancy
```

Например:

```text
HH:
"Удаленная работа"

       ↓

work_formats:
["REMOTE"]
```

Или:

```text
"Москва"

       ↓

area:
{
    id: ...,
    name: "Москва"
}
```

---

# 9. Система фильтрации

Это одна из ключевых частей проекта.

Фильтр должен поддерживать несколько типов правил.

## Required

Обязательные условия.

Пример:

```text
Python
FastAPI
```

Если обязательное условие не выполнено:

```text
MATCH = false
```

---

## Preferred

Желательные условия.

Например:

```text
PostgreSQL
Redis
Docker
SQLAlchemy
```

Они влияют на score, но не обязательны.

---

## Excluded

Запрещённые условия:

```text
Senior
Lead
Architect
C++
Java
```

При обнаружении критичного запрещённого условия вакансия отбрасывается.

---

## Numeric filters

Например:

```text
salary >= 100000
```

или:

```text
experience in [no_experience, 1-3]
```

---

## Location filters

Поддержать несколько вариантов:

```text
ANY
REMOTE_ONLY
SPECIFIC_AREAS
```

Ключевой сценарий:

```text
REMOTE_ONLY
```

означает:

> регион работодателя не имеет значения, если вакансия действительно допускает удалённую работу.

---

# 10. Мультифильтры

Один пользователь может иметь несколько фильтров:

```text
User
│
├── Remote Python
├── Hybrid Frankfurt
└── Backend Junior
```

Каждый фильтр независим.

Во время фонового поиска:

```text
new vacancy
     │
     ├── Filter A → MATCH
     ├── Filter B → NO MATCH
     └── Filter C → MATCH
```

В Telegram пользователь должен получить вакансию по подходящим фильтрам.

Если одна вакансия подходит под два фильтра, не следует отправлять её дважды.

Пример:

```text
🔥 Новая вакансия

Python Backend Developer

Подходит:
✓ Remote Python
✓ Backend Junior
```

---

# 11. Одноразовый поиск

Telegram-команда:

```text
/search
```

или кнопка:

```text
🔎 Новый поиск
```

Пользователь выбирает существующий фильтр или создаёт временный.

Сервис:

```text
Telegram
   ↓
Filter
   ↓
HH Search
   ↓
Normalize
   ↓
Matcher
   ↓
Sort by score
   ↓
Telegram
```

Результат должен поддерживать пагинацию.

Например:

```text
Найдено: 47 вакансий

1–10 из 47

[1] [2] [3] [4] ...
```

---

# 12. Подписка

Пользователь может включить:

```text
🔔 Подписка
```

для конкретного фильтра.

После этого Worker периодически запускает:

```text
fetch vacancies
      ↓
normalize
      ↓
save/update
      ↓
match active filters
      ↓
find unseen matches
      ↓
send Telegram
```

---

# 13. Проверка новых вакансий

Периодическая задача должна получать вакансии за некоторый временной диапазон.

Например:

```text
каждые 5 минут
```

Но нельзя полагаться только на дату публикации.

Нужно дополнительно использовать:

```text
source + external_id
```

для дедупликации.

Таким образом:

```text
HH vacancy ID 12345
```

будет сохранена один раз.

---

# 14. Telegram-интерфейс

Минимальный набор:

```text
/start
/help
/filters
/search
/subscriptions
/settings
```

Лучше использовать inline-кнопки вместо ручного ввода большинства параметров.

---

# 15. Создание фильтра

Пример UX:

```text
➕ Создать фильтр

Название:
[Python Remote]

Ключевые слова:
[Python, FastAPI, Backend]

Обязательные:
[Python]

Желательные:
[FastAPI, PostgreSQL, Redis, Docker]

Исключить:
[Senior, Lead, Architect]

Опыт:
[Без опыта / 1–3 года]

Формат:
[Удалённо]

Зарплата:
[100000]

[💾 Сохранить]
```

В дальнейшем настройки должны быть расширяемыми.

---

# 16. Просмотр вакансии

Telegram-сообщение:

```text
🔥 91/100

Python Backend Developer

🏢 Company
💰 100 000–150 000 ₽
🏠 Remote
📈 1–3 года

Совпадения:
✓ Python
✓ FastAPI
✓ PostgreSQL
✓ Docker
✓ Remote

Не найдено:
○ Redis
○ SQLAlchemy

[Открыть вакансию]
```

---

# 17. Scoring

Scoring не должен быть обязательным условием MVP.

После реализации базового Matcher добавить систему оценки.

Пример:

```text
Python       +30
FastAPI      +20
PostgreSQL   +10
Redis        +10
Docker       +10
Junior       +10
Remote       +10

Senior       -100
Lead         -100
```

Результат:

```text
score = 90
```

В будущем веса должны быть частью конфигурации фильтра.

---

# 18. Предполагаемый стек

## Core

```text
Python 3.12+
```

## Telegram

```text
aiogram
```

## HTTP

```text
httpx
```

## Database

```text
PostgreSQL
SQLAlchemy
Alembic
```

## Configuration

```text
pydantic
pydantic-settings
python-dotenv
```

`python-dotenv` может использоваться для локальной работы с `.env`, хотя при использовании `pydantic-settings` отдельная необходимость в нём может отсутствовать.

## Async / workers

На первой версии предпочтительно не усложнять архитектуру.

Возможный вариант:

```text
APScheduler
```

для периодических задач.

При росте проекта можно перейти к:

```text
Celery + Redis
```

или другому брокеру/worker-решению.

## Logging

```text
structlog
```

или стандартный `logging`.

Для MVP достаточно стандартного `logging`.

## Testing

```text
pytest
pytest-asyncio
```

## HTTP mocking

```text
respx
```

для тестирования `httpx`.

## Containerization

```text
Docker
Docker Compose
```

---

# 19. Предполагаемая структура проекта

```text
job-sniffer/
│
├── app/
│   ├── sniffers/
│   │   ├── base.py
│   │   └── hh.py
│   │
│   ├── bot/
│   │   ├── handlers/
│   │   ├── keyboards/
│   │   ├── states/
│   │   └── bot.py
│   │
│   ├── collectors/
│   │   ├── base.py
│   │   └── hh.py
│   │
│   ├── domain/
│   │   ├── vacancy.py
│   │   ├── filters.py
│   │   └── matching.py
│   │
│   ├── services/
│   │   ├── search.py
│   │   ├── matching.py
│   │   ├── subscriptions.py
│   │   └── notifications.py
│   │
│   ├── db/
│   │   ├── models/
│   │   ├── repositories/
│   │   └── session.py
│   │
│   ├── workers/
│   │   └── scheduler.py
│   │
│   ├── config.py
│   └── main.py
│
├── migrations/
│
├── tests/
│   ├── unit/
│   └── integration/
│
├── docker/
│
├── docker-compose.yml
├── Dockerfile
├── pyproject.toml
├── .env.example
└── README.md
```

На раннем этапе структуру можно упростить. Не нужно создавать 50 модулей до появления соответствующей логики.

---

# 20. Docker

Для локального запуска:

```text
docker compose up -d
```

Минимальные контейнеры:

```text
job-sniffer
postgres
```

Если появится Redis:

```text
job-sniffer
postgres
redis
```

Telegram Bot и Collector могут первоначально работать внутри одного Python-контейнера.

Позже их можно разделить:

```text
bot
worker
postgres
redis
```

---

# 21. Конфигурация

`.env`:

```text
TELEGRAM_BOT_TOKEN=
DATABASE_URL=
HH_CLIENT_ID=
HH_CLIENT_SECRET=
LOG_LEVEL=INFO
```

Секреты не должны храниться в Git.

В репозитории:

```text
.env.example
```

---

# 22. Поток данных: одноразовый поиск

```text
User
 │
 ▼
Telegram Bot
 │
 ▼
Search Service
 │
 ▼
HH Sniffer
 │
 ▼
HH API
 │
 ▼
Raw vacancies
 │
 ▼
Normalizer
 │
 ▼
Normalized vacancies
 │
 ▼
Matcher
 │
 ▼
Scoring
 │
 ▼
Sort
 │
 ▼
Telegram
```

---

# 23. Поток данных: подписка

```text
Scheduler
   │
   ▼
HH Collector
   │
   ▼
HH API
   │
   ▼
Normalizer
   │
   ▼
Database
   │
   ▼
Active Filters
   │
   ▼
Matcher
   │
   ▼
VacancyMatch
   │
   ▼
Notification Service
   │
   ▼
Telegram
```

---

# 24. Поток дедупликации

```text
Получена вакансия
       │
       ▼
source + external_id
       │
       ▼
Есть в БД?
   ┌───┴───┐
  YES      NO
   │        │
update    insert
   │        │
   └───┬────┘
       ▼
   Matching
```

Отдельно должна существовать дедупликация уведомлений:

```text
user + filter + vacancy
```

---

# 25. API

FastAPI не является обязательным компонентом первой версии.

Если добавлять API, он должен использоваться для:

- просмотра фильтров;
- создания/изменения фильтров;
- просмотра вакансий;
- просмотра статистики;
- управления подписками;
- health-check;
- дальнейшего создания web UI.

Пример:

```text
GET    /health
GET    /filters
POST   /filters
GET    /filters/{id}
PATCH  /filters/{id}
DELETE /filters/{id}

POST   /search
GET    /vacancies
GET    /vacancies/{id}

POST   /subscriptions
DELETE /subscriptions/{id}
```

Telegram Bot и API должны обращаться к одним сервисам, а не реализовывать бизнес-логику независимо.

---

# 26. Расширение на другие источники

Главное архитектурное правило:

> Source-specific код не должен проникать в бизнес-логику.

Плохо:

```text
if source == "hh":
    ...
elif source == "habr":
    ...
```

внутри Matcher.

Хорошо:

```text
Collector
    ↓
Normalized Vacancy
    ↓
Common Matcher
```

Добавление нового источника должно выглядеть примерно так:

```text
BaseSniffer
    │
    ├── HHSniffer
    └── NewSourceSniffer
```

---

# 27. Что НЕ делать в первой версии

Не добавлять сразу:

- ML;
- LLM-анализ вакансий;
- автоматическую генерацию сопроводительных писем;
- Selenium;
- полноценную web-панель;
- микросервисную архитектуру;
- Kubernetes;
- Celery без необходимости;
- сложную event-driven систему;
- Elasticsearch;
- сложную recommendation system.

Сначала должна работать цепочка:

```text
HH Sniffer → Filter → DB → Telegram
```

---

# 28. MVP

MVP считается готовым, если пользователь может:

1. Запустить проект через Docker Compose.
2. Открыть Telegram-бота.
3. Создать фильтр.
4. Указать обязательные и запрещённые условия.
5. Указать зарплату.
6. Указать опыт.
7. Указать формат работы.
8. Выполнить одноразовый поиск.
9. Получить список вакансий.
10. Включить подписку.
11. Получить новую подходящую вакансию автоматически.
12. Не получать одну и ту же вакансию повторно.

---

# 29. Критерии качества

## Код

- типизация;
- понятное разделение ответственности;
- отсутствие бизнес-логики в Telegram handlers;
- отсутствие бизнес-логики в Collector;
- отсутствие SQL внутри бизнес-логики;
- конфигурация через environment variables.

## Надёжность

- обработка HTTP ошибок;
- timeout запросов;
- retry для временных ошибок;
- логирование;
- graceful shutdown;
- защита от повторной отправки.

## Тестируемость

Минимум должны тестироваться:

- Matcher;
- scoring;
- дедупликация;
- нормализация;
- repository;
- обработка ошибок Collector.

---

# 30. Будущие возможности

После стабильного MVP:

### Источники

```text
HH
Habr Career
LinkedIn
Indeed
и другие
```

### Фильтрация

- regex;
- синонимы;
- группы навыков;
- логические выражения;
- пользовательские веса;
- отдельные positive/negative rules.

### Intelligence

Можно добавить LLM-классификацию:

```text
Vacancy
   ↓
LLM
   ↓
"Подходит пользователю?"
   ↓
score
```

Например, модель может отличать:

```text
Python Developer
```

от:

```text
Python Developer,
но фактически 90% работы — DevOps.
```

Но это отдельный этап и не должно быть частью MVP.

---

# 31. Этапы разработки

Общий порядок:

```text
0. Project bootstrap
        ↓
1. Domain models
        ↓
2. HH Collector
        ↓
3. Normalization
        ↓
4. Basic Matcher
        ↓
5. PostgreSQL
        ↓
6. One-shot search
        ↓
7. Telegram Bot
        ↓
8. User filters
        ↓
9. Subscriptions
        ↓
10. Scheduler
        ↓
11. Notifications
        ↓
12. Deduplication
        ↓
13. Scoring
        ↓
14. Tests
        ↓
15. Docker / deployment polish
        ↓
16. Extension architecture
```

---

# 32. Главный принцип разработки

Не строить весь Job Sniffer сразу.

Каждый этап должен давать работающий кусок системы.

Например:

```text
Этап 1:
Python → HHSniffer → print(vacancies)
```

затем:

```text
Этап 2:
Python → HHSniffer → Matcher → print(matches)
```

затем:

```text
Этап 3:
Python → HHSniffer → Matcher → PostgreSQL
```

затем:

```text
Этап 4:
Telegram → Search → HHSniffer → Matcher → Telegram
```

и только потом:

```text
Scheduler → HHSniffer → Matcher → Telegram
```

---

# 33. Финальная целевая архитектура

```text
                         ┌───────────────┐
                         │   Telegram    │
                         │     User      │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Telegram Bot  │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │ Application   │
                         │   Services    │
                         └───────┬───────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                  │
              ▼                  ▼                  ▼
          Filters             Search          Subscriptions
              │                  │                  │
              └──────────────────┼──────────────────┘
                                 ▼
                         ┌───────────────┐
                         │    Matcher    │
                         │   + Scoring   │
                         └───────┬───────┘
                                 │
                                 ▼
                         ┌───────────────┐
                         │  PostgreSQL   │
                         └───────────────┘

                     Background Worker
                            │
                            ▼
                     ┌───────────────┐
                     │   Sniffers     │
                     └───────┬───────┘
                             │
                ┌────────────┼────────────┐
                ▼            ▼            ▼
           HH Sniffer    Habr Sniffer  Future Sniffer
                │
                ▼
            Normalizer
                │
                ▼
           Vacancy model
                │
                ▼
             Matcher
                │
                ▼
           Notifications
                │
                ▼
             Telegram
```

---

# 34. Definition of Done проекта

Проект считается первой полноценной версией, когда:

- [ ] Job Sniffer запускается через Docker Compose.
- [ ] Пользователь взаимодействует с системой через Telegram.
- [ ] HH является первым и пока единственным источником.
- [ ] Реализован одноразовый поиск.
- [ ] Реализованы сохранённые пользовательские фильтры.
- [ ] Реализованы несколько фильтров на одного пользователя.
- [ ] Поддерживаются независимые remote/hybrid сценарии.
- [ ] Реализованы required/preferred/excluded условия.
- [ ] Реализованы фильтры опыта.
- [ ] Реализован фильтр зарплаты.
- [ ] Реализован фильтр формата работы.
- [ ] Вакансии сохраняются в PostgreSQL.
- [ ] Реализована дедупликация вакансий.
- [ ] Реализована подписка на фильтр.
- [ ] Worker периодически проверяет новые вакансии.
- [ ] Новые совпадения отправляются в Telegram.
- [ ] Одинаковая вакансия не отправляется повторно.
- [ ] Реализован базовый scoring.
- [ ] Ключевая бизнес-логика покрыта тестами.
- [ ] HH-specific код изолирован от общей логики.
- [ ] Архитектура допускает добавление второго источника без переписывания Matcher.
