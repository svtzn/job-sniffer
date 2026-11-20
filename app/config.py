from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        env_ignore_empty=True,  # «KEY=» в .env -> значение по умолчанию
    )

    # --- Database ---
    # Относительный путь SQLite считается от корня проекта
    database_url: str = "sqlite+aiosqlite:///./data/jobs.db"

    # --- Browser ---
    headless: bool = True
    viewport_width: int = 1920
    viewport_height: int = 1080
    locale: str = "ru-RU"
    timezone_id: str = "Europe/Moscow"

    # --- Rate limiting ---
    delay_min: float = 2.0
    delay_max: float = 5.0

    # --- HH.ru ---
    hh_base_url: str = "https://krasnodar.hh.ru/search/vacancy"
    hh_wait_until: str = "domcontentloaded"

    # --- Search ---
    search_limit: int = 100  # сколько вакансий собирать за один поиск
    search_timeout_seconds: int = 300  # предел на весь поиск: зависший браузер не держит очередь вечно
    results_page_size: int = 5  # вакансий на одной странице выдачи в боте
    home_area_id: int = 53  # «мой город» для шаблона «удалёнка + мой город» (53 — Краснодар)

    # --- Subscriptions ---
    subscription_interval_minutes: int = 15  # как часто проверять подписки
    subscription_max_per_check: int = 10  # больше новых за раз — одна сводка вместо карточек
    quiet_hours: str = ""  # «23-8»: ночью не присылать, утром — сводкой (локальное время)

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_proxy_url: str = ""
    # Свой адрес Bot API (например, Cloudflare Worker, если api.telegram.org заблокирован)
    telegram_api_base: str = ""
    # Переиспользовать соединения с Telegram. Пусто = авто: выключено при своём адресе API
    # (провайдеры «замораживают» долгие соединения с Cloudflare)
    telegram_keepalive: bool | None = None
    telegram_timeout: int = 15  # секунд на один запрос к Telegram


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
