# Use the slim Python base
FROM python:3.9-slim

# 1) Install system dependencies: LibreOffice (for XLSX→CSV), Node.js, fonts, libs for headless browsers
RUN apt-get update && apt-get install -y \
      libreoffice-core libreoffice-calc libreoffice-writer \
      libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 \
      libxcomposite1 libxdamage1 libxfixes3 libgbm1 libpango-1.0-0 \
      libasound2 curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2) Create & switch to your app directory
WORKDIR /app

# 3) Install Python dependencies
COPY requirements.txt ./
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# 4) Install Node dependencies (for your escreen.js scraper)
COPY package.json package-lock.json ./
RUN npm ci

# 5) Copy your application code (all modules live under src/)
COPY src/        ./src/
COPY src/main.py ./main.py
COPY src/run.py  ./run.py
COPY src/config.py ./config.py
COPY src/utils.py  ./utils.py

# 6) Expose web port (if you serve a Flask app on 5000)
EXPOSE 5000

# 7) Default entrypoint for your pipeline CLI — change to run web service if you prefer
ENTRYPOINT ["easy-import-pipeline"]
CMD ["--help"]
