# ─── Stage 1: Build JS dependencies ───────────────────────
FROM node:18-slim AS js-builder
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci --no-audit --no-fund

# ─── Stage 2: Final Python + Chromium + LibreOffice image ─
FROM python:3.11-slim

# 1) System deps + Chromium & libs + Node runtime + LibreOffice
RUN apt-get update && apt-get install -y \
      chromium \
      gconf-service libasound2 libatk1.0-0 libatk-bridge2.0-0 \
      libc6 libcairo2 libexpat1 libfontconfig1 libgcc1 libgconf-2-4 \
      libgdk-pixbuf2.0-0 libglib2.0-0 libgtk-3-0 libnspr4 libpango-1.0-0 \
      libx11-6 libx11-xcb1 libxcb1 libxcomposite1 libxcursor1 libxdamage1 \
      libxext6 libxfixes3 libxi6 libxrandr2 libxrender1 libxss1 libxtst6 \
      ca-certificates fonts-liberation libnss3 lsb-release xdg-utils \
      curl gnupg \
      libreoffice-core libreoffice-calc fonts-dejavu-core \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2) Mark running-in-docker & Puppeteer path
ENV RUNNING_IN_DOCKER=true
ENV PUPPETEER_EXECUTABLE_PATH=/usr/bin/chromium

# 3) Set workdir
WORKDIR /app
ENV PROJECT_ROOT=/app

# 4) Copy Python project and install
COPY .env             /app/.env
COPY setup.py         /app/setup.py
COPY requirements.txt /app/requirements.txt
COPY MANIFEST.in      /app/MANIFEST.in
COPY src/             /app/src/
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt \
 && pip install .

# 5) Pull in JS modules
COPY --from=js-builder /app/node_modules /app/node_modules
COPY package.json package-lock.json /app/

# 6) Ensure folders exist and writable
RUN mkdir -p /app/downloads /app/src/debug \
 && chmod 777 /app/downloads /app/src/debug

# 7) Entrypoint
ENTRYPOINT ["easy-import-pipeline"]
CMD ["--help"]
