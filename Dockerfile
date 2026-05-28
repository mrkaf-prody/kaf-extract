FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libu2f-udev libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Crawl4AI browsers (bundled Playwright Chromium)
RUN python3 -m crawl4ai install 2>/dev/null || python3 -m playwright install chromium

COPY src/ ./src/
COPY alembic.ini .
COPY alembic/ ./alembic/
RUN mkdir -p /app/data

# Ensure admin_static is included (built React admin dashboard)
RUN mkdir -p /app/src/admin_static

EXPOSE 8000

# Pre-flight check
RUN python3 -c "from src.main import app; print('OK: app imported successfully')"

# Start API server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
