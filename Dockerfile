# Start from a slim Python image
FROM python:3.9-slim

# 1) Install system dependencies (for LibreOffice & Playwright)
RUN apt-get update && apt-get install -y \
    libreoffice-writer libreoffice-calc libreoffice-core \
    libatk1.0-0 libatk-bridge2.0-0 libxkbcommon0 libatspi2.0-0 \
    libxcomposite1 libxdamage1 libxfixes3 libgbm1 libpango-1.0-0 \
    libasound2 curl gnupg && \
    rm -rf /var/lib/apt/lists/*

# 2) Install Node (for your Puppeteer script)
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# 3) Create app directory
WORKDIR /app

# 4) Copy and install Python dependencies
COPY requirements.txt /app/requirements.txt
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# 5) Copy and install Node dependencies for the eScreen scraper
COPY package.json package-lock.json /app/
RUN npm ci

# 6) Copy your application code
COPY src /app/src
COPY run.py main.py config.py utils.py /app/

# 7) Tell Playwright to install its browsers (and deps)
RUN pip install playwright && \
    # this will also install the linux libs it needs
    playwright install-deps && \
    playwright install chromium

# 8) Expose the port your Flask/Gunicorn app listens on
EXPOSE 5000

# 9) Default entrypoint: run your web server
CMD ["gunicorn", "run:app", "--bind", "0.0.0.0:5000", "--workers", "2"]
