# Use official Python image (with debian/apt-get)
FROM python:3.12-slim

# Install system deps needed for Playwright/Puppeteer
RUN apt-get update && \
    apt-get install -y wget curl gnupg nodejs npm \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libgtk-4-1 \
    libnspr4 libnss3 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils libu2f-udev libvulkan1 libxkbcommon0 libxshmfence1 \
    libpangocairo-1.0-0 libpango-1.0-0 libegl1 libopus0 \
    libgstreamer-plugins-base1.0-0 libgstreamer1.0-0 libxss1 \
    libgl1 libavif15 libgraphene-1.0-0 libgstgl-1.0-0 \
    libgstcodecparsers-1.0-0 libenchant-2-2 libsecret-1-0 \
    libmanette-0.2-0 libgles2 && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python deps
COPY requirements.txt ./
RUN pip install --upgrade pip
RUN pip install -r requirements.txt

# Copy the rest of your code
COPY . .

# Install Playwright browsers for Python
RUN playwright install

# Node dependencies (at root)
RUN if [ -f package.json ]; then npm ci || npm install; fi

# Node dependencies for src/scrapers/
RUN if [ -f src/scrapers/package.json ]; then cd src/scrapers && npm install && cd ../..; fi

# Puppeteer browser install (safe to skip if not used directly)
RUN if [ -f package.json ]; then npx puppeteer browsers install || true; fi

# Set default command (Render cron will override)
CMD ["python3", "-m", "src.main"]
