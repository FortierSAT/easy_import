FROM python:3.9-slim

# 1) Install system deps (libreoffice, Node.js, etc.)
RUN apt-get update && apt-get install -y \
      libreoffice-core libreoffice-calc libreoffice-writer \
      libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 \
      libxcomposite1 libxdamage1 libxfixes3 libgbm1 libpango-1.0-0 \
      libasound2 curl gnupg ca-certificates \
    && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs \
    && rm -rf /var/lib/apt/lists/*

# 2) Create & switch to /app
WORKDIR /app

# 3) Copy Python dependencies
COPY requirements.txt /app/
RUN pip install --upgrade pip setuptools wheel \
 && pip install -r requirements.txt

# 4) Copy Node dependencies
COPY package*.json /app/
RUN npm ci

# 5) Copy your application code
COPY easy_import/src/   /app/src/
COPY easy_import/src/main.py  /app/main.py
COPY easy_import/src/run.py   /app/run.py
COPY easy_import/src/config.py  /app/config.py
COPY easy_import/src/utils.py   /app/utils.py

# 6) Expose/entrypoints
ENTRYPOINT ["easy-import-pipeline"]
CMD ["--help"]
