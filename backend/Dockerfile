FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PORT=8000

WORKDIR /app

# System deps for PyMuPDF
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app/ ./app/

# Run as an unprivileged user; it owns only the writable dirs.
RUN useradd --create-home --uid 10001 appuser \
    && mkdir -p downloads data \
    && chown -R appuser:appuser downloads data
USER appuser

EXPOSE 8000

# --proxy-headers so request.client is the real caller behind Render's proxy
# (per-IP rate limiting depends on it). Shell form so $PORT expands.
CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT} --proxy-headers --forwarded-allow-ips='*'
