FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libu2f-udev libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 xdg-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN python3 -m playwright install chromium

COPY src/ ./src/
RUN mkdir -p /app/data

EXPOSE 8000

# Run a pre-flight import check before starting server
RUN python3 -c "from src.main import app; print('OK: app imported successfully')"

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]
