# syntax=docker/dockerfile:1

# ---------- builder ----------
FROM python:3.11-slim AS builder

WORKDIR /app

# system deps
RUN apt-get update && apt-get install -y --no-install-recommends build-essential && rm -rf /var/lib/apt/lists/*

# install deps into virtualenv dir to copy later
COPY requirements.txt .
RUN pip install --prefix /install --no-cache-dir -r requirements.txt

# ---------- runtime ----------
FROM python:3.11-slim AS runtime

ENV PYTHONUNBUFFERED=1
WORKDIR /app

# copy installed python packages
COPY --from=builder /install /usr/local

# copy project
COPY . .

# create user
RUN useradd -ms /bin/bash appuser && \
    mkdir -p /app/data /app/logs /app/.sessions && \
    chown -R appuser:appuser /app

USER appuser

CMD ["python", "main.py"] 