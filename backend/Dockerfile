FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# No apt-get: the build must not depend on Debian mirrors (fragile on a NAS).
# All runtime deps (asyncpg/psycopg) ship as prebuilt wheels from PyPI.

# Install Python deps first for better layer caching.
COPY pyproject.toml ./
RUN pip install --upgrade pip && pip install ".[dev]"

COPY . .

# Run unprivileged: the code and installed packages stay root-owned and
# read-only for the app; a compromise can't rewrite them or touch the host.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /data/tts && chown app:app /data/tts  # server-voice MP3 cache (volume)
USER app

EXPOSE 8000

# Healthcheck via Python (already in the image) instead of curl.
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health').status==200 else 1)" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
