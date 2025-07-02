#!/usr/bin/env bash
set -e

# 1. Install system dependencies for Playwright/Puppeteer (skip if using Docker)
apt-get update
apt-get install -y wget curl gnupg \
    fonts-liberation libasound2 libatk-bridge2.0-0 libatk1.0-0 libcups2 \
    libdbus-1-3 libdrm2 libgbm1 libgtk-3-0 libgtk-4-1 \
    libnspr4 libnss3 libxcomposite1 libxdamage1 libxrandr2 \
    xdg-utils libu2f-udev libvulkan1 libxkbcommon0 libxshmfence1 \
    libpangocairo-1.0-0 libpango-1.0-0 libegl1 libopus0 \
    libgstreamer-plugins-base1.0-0 libgstreamer1.0-0 libxss1 \
    libgl1 libavif15 libgraphene-1.0-0 libgstgl-1.0-0 \
    libgstcodecparsers-1.0-0 libenchant-2-2 libsecret-1-0 \
    libmanette-0.2-0 libgles2

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Install Playwright browsers for Python
playwright install

# 4. Install NodeJS dependencies (if package.json exists)
if [ -f package.json ]; then
    npm ci || npm install
fi

# 5. (Optional) Install Puppeteer browsers
if [ -f package.json ]; then
    npx puppeteer browsers install || true
fi

# 6. Install Node dependencies for Puppeteer if src/scrapers is a separate package
if [ -f src/scrapers/package.json ]; then
    cd src/scrapers
    npm install
    cd ../..
fi
