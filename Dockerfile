# Use official Python slim image
FROM python:3.9-slim

# Install LibreOffice (soffice) for XLSX → CSV
RUN apt-get update \
    && apt-get install -y --no-install-recommends libreoffice-calc \
    && rm -rf /var/lib/apt/lists/*

# Create and activate venv
WORKDIR /app
RUN python -m venv .venv
ENV PATH="/app/.venv/bin:$PATH"

# Copy everything in
COPY . .

# Install Python deps and your package so console_scripts are registered
RUN pip install --upgrade pip \
    && pip install -r requirements.txt \
    && pip install .

# Default: run pipeline in dry‐run
ENTRYPOINT ["easy-import-pipeline"]
CMD ["--dry-run"]
