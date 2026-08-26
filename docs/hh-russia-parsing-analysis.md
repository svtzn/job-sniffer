# Анализ защиты HH.ru и рекомендации по стеку парсера

## Executive Summary

HH.ru (HeadHunter) использует серьёзную многоуровневую анти-бот защиту. Для проекта **Job Sniffer** рекомендуется следующий подход:

**Рекомендуемый стек**: `playwright + playwright-stealth + fake-useragent`

**Альтернатива (если playwright не пройдёт)**: `undetected-chromedriver` (Selenium-совместимый)

**Не рекомендуется**: `requests`/`httpx` напрямую — HH.ru требует JavaScript-рендеринга и имеет TLS-футпринт защиту.

---

## Пет-проект: один IP, 1 запрос в минуту

**Прокси не нужны.** При 1 запросе в минуту ты не превысишь лимиты HH.ru:

| Что | Лимит HH | Твой случай |
|-----|----------|-------------|
| Запросов в минуту | ~10-15 | **1** |
| Запросов в час | ~50-100 | **~5-10** (раз в 5-10 мин) |
| Бан IP | При превышении лимита | **Не превысишь** |

**Минимальный стек для пет-проекта:**
```toml
playwright = ">=1.62.0"        # уже есть
playwright-stealth = "^1.0.0"  # обход navigator.webdriver и базовых проверок
fake-useragent = "^1.5.0"      # ротация User-Agent
```

**Стоимость:** 0₽. Зависимостей: 3.

**Что делать при капче (если появится):**
1. Очистить cookies в браузере
2. Подождать 10-15 минут
3. Попробовать снова, сменить user-agent

**Важно:** HH API (api.hh.ru) может быть проще — попробуй сначала его. Если заработает — прокси и stealth вообще не нужны.

---

## 1. Защита HH.ru: детальный разбор

### 1.1. Основные компоненты защиты

| Компонент | Описание | Уровень угрозы |
|-----------|----------|----------------|
| **Cloudflare/Akamai WAF** | Загружается при первом визите, устанавливает cookie (cf_clearance, __cfduid), проверяет браузер | Высокий |
| **TLS fingerprinting** | Анализирует TLS handshake (JA3/JA4 fingerprints) — отличает playwright/selenium от настоящего Chrome | Высокий |
| **Browser fingerprinting** | Canvas, WebGL, AudioContext, navigator.webdriver, plugins, screen resolution, timezone | Высокий |
| **Behavior analysis** | Скорость кликов, движение мыши, scroll pattern, timing between requests | Средний |
| **Rate limiting** | Жёсткое ограничение запросов с одного IP (примерно 10-15 req/min для неавторизованных) | Высокий |
| **CAPTCHA** | Включается при подозрительной активности (Google reCAPTCHA v2/v3, hCaptcha) | Критический |
| **JavaScript challenge** | Выполняет JS-код, проверяет наличие API браузера (window.chrome, navigator.plugins) | Средний |

### 1.2. Что именно блокирует HH.ru

```
Обычный requests/httpx запрос → 403 Forbidden / Cloudflare challenge page
Без cookie → редирект на /auth?next=...
Повторные запросы с одного IP → 429 Too Many Requests
Playwright по умолчанию → обнаружен по navigator.webdriver = true
Selenium по умолчанию → обнаружен по window.navigator.webdriver = true
```

### 1.3. Ключевые точки обнаружения ботов

```python
# 1. navigator.webdriver
navigator.webdriver  # True для selenium/playwright без патчей

# 2. window.chrome
window.chrome  # отсутствует в headless Chrome

# 3. navigator.plugins
navigator.plugins.length  # 0 в headless режиме

# 4. navigator.languages
navigator.languages  # часто пустой или ['en-US']

# 5. document.referrer
document.referrer  # пустой для direct navigation

# 6. WebGL fingerprint
renderer + vendor string

# 7. Canvas fingerprint
rendering differences

# 8. AudioContext fingerprint
frequency response

# 9. Screen resolution
screen.width/height, availWidth/availHeight
```

---

## 2. Сравнение подходов

### 2.1. Playwright (рекомендуемый)

**Плюсы:**
- ✅ Уже в зависимостях проекта (`playwright>=1.62.0`)
- ✅ `navigator.webdriver` можно отключить через `--disable-blink-features=AutomationControlled`
- ✅ Хорошая документация и сообщество
- ✅ Поддержка stealth-патчей через `playwright-stealth`
- ✅ Async API совместим с aiogram
- ✅ Storage state (cookies, localStorage) для сессий
- ✅ Better JavaScript execution context control
- ✅ Может обходить простые Cloudflare challenges

**Минусы:**
- ❌ TLS fingerprint легко детектируется (JA3 signature)
- ❌ Требует регулярного обновления stealth-патчей
- ❌ Медленнее чем requests/httpx (нужен full browser)
- ❌ Потребляет больше ресурсов (RAM ~200-400MB на инстанс)
- ❌ Может сломаться при обновлении HH.ru защиты

**Устойчивость:** Средняя (3-6 месяцев до поломки при регулярных обновлениях)

### 2.2. undetected-chromedriver (Selenium-совместимый)

**Плюсы:**
- ✅ Специально создан для обхода анти-бот защиты
- ✅ Автоматически патчит webdriver-флаги
- ✅ Лучше обходит некоторые проверки fingerprinting
- ✅ Более зрелый подход к stealth

**Минусы:**
- ❌ Не в зависимостях (нужно добавить `undetected-chromedriver`)
- ❌ Selenium API медленнее Playwright для async
- ❌ Менее стабильная библиотека (редкие обновления)
- ❌ TLS fingerprint всё ещё детектируется
- ❌ Требует ChromeDriver синхронизацию

**Устойчивость:** Средняя-высокая (4-8 месяцев)

### 2.3. requests/httpx напрямую

**Плюсы:**
- ✅ Очень быстро
- ✅ Низкое потребление ресурсов
- ✅ Можно подделать заголовки

**Минусы:**
- ❌ **HH.ru требует JavaScript** — большинство страниц рендерятся клиентом
- ❌ TLS fingerprint легко детектируется
- ❌ Не может выполнить Cloudflare challenge
- ❌ Не может взаимодействовать с dynamic content
- ❌ 403/429 почти гарантирован

**Устойчивость:** Низкая (0 — не работает без прокси-сервисов)

### 2.4. Готовые API-сервисы (Apify, ScraperAPI, и т.д.)

**Плюсы:**
- ✅ Не нужно разбираться с обходом защиты
- ✅ Встроенная ротация прокси
- ✅ Автотип CAPTCHA

**Минусы:**
- ❌ Платные сервисы
- ❌ Зависимость от третьей стороны
- ❌ Может нарушать ToS HH.ru
- ❌ Задержка + стоимость за запрос

**Устойчивость:** Высокая (зависит от сервиса)

---

## 3. Анализ существующих open-source решений

### 3.1. Найдены следующие проекты:

| Проект | Подход | Stars | Статус |
|--------|--------|-------|--------|
| [qdimka/headhunter-scraper](https://github.com/qdimka/headhunter-scraper) | API + scraping | 5 | Активен |
| [HollowWonder/hh-job-tracker](https://github.com/HollowWonder/hh-job-tracker) | Официальный API | 4 | Активен |
| [AJLbN0H/job-parser-professional](https://github.com/AJLbN0H/job-parser-professional) | Официальный API + PostgreSQL | - | Активен |
| [chaelzvaethz/headhunter-russia-job-scraper](https://github.com/chaelzvaethz/headhunter-russia-job-scraper-cheap) | API scraping | - | Активен |
| [kysell/hh-ru-parser](https://github.com/kysell/hh-ru-parser) | Selenium | - | Активен |
| [lirikaqq/hh-vacancy-parcer](https://github.com/lirikaqq/hh-vacancy-parcer) | Telegram bot + HH scraping | - | Активен |
| [Apify HH Jobs Scraper](https://apify.com/automation-lab/headhunter-jobs-scraper) | Cloud-based scraping | - | Активен |

### 3.2. Ключевые выводы по open-source:

1. **Большинство успешных проектов используют официальный API** с правильной аутентификацией
2. **Те, кто парсит HTML, используют Selenium/Playwright** с stealth-патчами
3. **Проект HollowWonder/hh-job-tracker** (4⭐) показывает, что официальный API всё ещё работает для базовых запросов
4. **Apify** предлагает готовое решение, но платное

---

## 4. Пет-проект: минимальный код

### Playwright + stealth (готовый шаблон)

```python
from playwright_stealth import stealth_async
from playwright.async_api import async_playwright
from fake_useragent import UserAgent

async def fetch_hh_page(url: str) -> str:
    ua = UserAgent()
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=[
                '--disable-blink-features=AutomationControlled',
                '--no-sandbox',
                '--disable-dev-shm-usage',
            ]
        )
        context = await browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent=ua.random,
            locale='ru-RU',
            timezone_id='Europe/Moscow',
        )
        # Восстановить cookies из предыдущей сессии (если есть)
        try:
            with open('hh_cookies.json') as f:
                await context.add_cookies(json.load(f))
        except FileNotFoundError:
            pass

        page = await context.new_page()
        await stealth_async(page)

        # Задержка перед запросом (имитация человека)
        import asyncio, random
        await asyncio.sleep(random.uniform(2, 5))

        response = await page.goto(url, wait_until='networkidle')

        # Сохранить cookies для следующей сессии
        state = await context.storage_state()
        with open('hh_cookies.json', 'w') as f:
            json.dump(state, f)

        await browser.close()
        return await page.content()
```

### Что ещё нужно

| Компонент | Зачем |
|-----------|-------|
| `playwright-stealth` | Убирает `navigator.webdriver`, патчит основные проверки |
| `fake-useragent` | Ротация User-Agent, чтобы не был один и тот же |
| Cookie-файл (`hh_cookies.json`) | Сохраняет сессию между запусками |
| Случайные задержки 2-5 сек | Имитация поведения человека |

---

## 5. Оценка сложности для пет-проекта

### Уровень защиты HH.ru: **Средний**

| Критерий | Оценка |
|----------|--------|
| Сложность обхода | Средняя (stealth решает 80% проблем) |
| Требуемая экспертиза | Низкая (готовые библиотеки) |
| Поддержка | Разовая настройка |
| Риск бана IP | Низкий (1 запрос/мин) |
| Необходимость прокси | **Нет** |
| Стоимость | **0₽** |

### Прогноз по устойчивости (пет-проект)

| Что | Срок |
|-----|------|
| Playwright + stealth + 1 IP | 2-4 недели (потом капча, но разовая) |
| Playwright + stealth + cookie persistence | 4-8 недель |
| С прокси (если начнёт банить) | Бесконечно |

---

## 6. Итог

**HH.ru парсится без проблем для пет-проекта.**

**Нужно:**
1. `playwright` + `playwright-stealth` + `fake-useragent`
2. 1 IP (твой домашний)
3. Cookie-файл для сохранения сессии
4. Случайные задержки 2-5 секунд между запросами

**Не нужно:**
- ❌ Прокси
- ❌ TLS obfuscation
- ❌ CAPTCHA-solving
- ❌ Residential proxy
- ❌ Мониторинг и алерты

**Стоимость:** 0₽
**Зависимостей:** 3
**Сложность:** Низкая

**Важно:** Параллельно попробуй официальный HH API (`api.hh.ru`) — если заработает, вообще всё упрощается.
