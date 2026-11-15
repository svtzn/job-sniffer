from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
    )

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
    results_page_size: int = 5  # вакансий на одной странице выдачи в боте
    home_area_id: int = 53  # «мой город» для шаблона «удалёнка + мой город» (53 — Краснодар)

    # --- Telegram ---
    telegram_bot_token: str = ""
    telegram_proxy_url: str = ""


_settings: Settings | None = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
