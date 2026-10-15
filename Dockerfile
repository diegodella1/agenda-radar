FROM python:3.12-slim AS builder
WORKDIR /build
COPY pyproject.toml requirements.production.txt ./
COPY src ./src
RUN pip wheel --no-cache-dir --wheel-dir /wheels -c requirements.production.txt .

FROM python:3.12-slim
RUN useradd --uid 10001 --create-home radar
WORKDIR /app
COPY --from=builder /wheels /wheels
RUN pip install --no-cache-dir /wheels/* && rm -rf /wheels
COPY src /app/src
COPY alembic.ini /app/alembic.ini
ENV PYTHONPATH=/app/src PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN mkdir -p /app/data /app/secrets /app/backups && chown -R radar:radar /app
USER radar
CMD ["python", "-m", "agenda_radar.cli", "web"]
