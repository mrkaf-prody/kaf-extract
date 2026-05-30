FROM python:3.13-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget ca-certificates fonts-liberation libasound2 libatk-bridge2.0-0 \
    libatk1.0-0 libcups2 libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 \
    libnspr4 libnss3 libu2f-udev libxcomposite1 libxdamage1 libxfixes3 \
    libxkbcommon0 libxrandr2 xdg-utils curl gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Crawl4AI browsers
RUN python3 -m crawl4ai install 2>/dev/null || python3 -m playwright install chromium

# Build user dashboard React SPA
COPY user-dashboard/package.json user-dashboard/package-lock.json* ./user-dashboard/
RUN cd user-dashboard && npm install
COPY user-dashboard/ ./user-dashboard/
RUN cd user-dashboard && npm run build

# Build admin dashboard React SPA
COPY admin/package.json admin/package-lock.json* ./admin/
RUN cd admin && npm install
COPY admin/ ./admin/
RUN cd admin && npm run build

# Build landing page React SPA
COPY landing/package.json landing/package-lock.json* ./landing/
RUN cd landing && npm install
COPY landing/ ./landing/
RUN cd landing && npm run build

# Copy application source code
COPY src/ ./src/
COPY alembic.ini .
COPY alembic/ ./alembic/
RUN mkdir -p /app/data

# After src/ copy, overwrite admin_static with the freshly built admin dashboard
# This ensures src/admin_static contains the latest build regardless of git state
RUN rm -rf src/admin_static/* && cp -r admin/dist/* src/admin_static/

EXPOSE 8000

# Pre-flight check
RUN python3 -c "from src.main import app; print('OK: app imported successfully')"

# Start API server
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8000"]

# Build cache buster 1780082201
