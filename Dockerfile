# 1. Base image
FROM python:3.9-slim

# 2. Install system libs (LibreOffice + Playwright deps + Node)
RUN apt-get update && apt-get install -y \
    libreoffice-core libreoffice-calc libreoffice-writer \
    libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libgbm1 libpango-1.0-0 \
    libasound2 curl gnupg ca-certificates \
  && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
  && apt-get install -y nodejs \
  && rm -rf /var/lib/apt/lists/*

# 3. Create app dir
WORKDIR /app

# 4. Python deps
COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# 5. Node deps (for escreen.js)
COPY package.json /app/
# either you’ve already committed package-lock.json:
# COPY package-lock.json /app/
RUN npm install

# 6) Copy your app code into /app
COPY src/            /app/src/
COPY src/main.py     /app/main.py
COPY src/run.py      /app/run.py
COPY src/config.py   /app/config.py
COPY src/utils.py    /app/utils.py

# 7. Playwright browsers + deps
RUN pip install playwright \
 && playwright install-deps \
 && playwright install chromium

# 8. Expose & default to your web CMD
EXPOSE 5000
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
