# Dockerfile

FROM python:3.9-slim

# 1) Install system deps: LibreOffice + Playwright libs + Node.js
RUN apt-get update && apt-get install -y --no-install-recommends \
      libreoffice-core \
      libreoffice-calc \
      libatk1.0-0 \
      libatk-bridge2.0-0 \
      libxkbcommon0 \
      libatspi2.0-0 \
      libxcomposite1 \
      libxdamage1 \
      libxfixes3 \
      libgbm1 \
      libpango-1.0-0 \
      libasound2 \
      curl \
      gnupg \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2) Install Playwright’s own dependencies & browsers
RUN pip install --no-cache-dir playwright \
 && playwright install-deps \
 && playwright install

# 3) Copy your app in
WORKDIR /app
COPY . /app

# 4) Install Python requirements and your package
RUN pip install --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt \
 && pip install --no-cache-dir .

# 5) Expose port for your web UI (if you deploy it)
EXPOSE 5000

# 6a) Default to running your pipeline (cron job style)
ENTRYPOINT ["easy-import-pipeline"]
CMD ["--dry-run"]
