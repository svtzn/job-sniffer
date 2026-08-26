FROM python:3.12-slim

# Системные зависимости для Playwright (установятся автоматически через --with-deps)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Сначала копируем только pyproject.toml для кэширования слоёв
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen

# Копируем весь проект
COPY . .

# Устанавливаем Chromium (через uv run, т.к. playwright CLI в виртуальном окружении)
RUN uv run playwright install --with-deps chromium

# Базу данных монтируем через volume, не копируем в образ
VOLUME ["/app/data"]

CMD ["uv", "run", "python", "-m", "app.telegram.bot"]