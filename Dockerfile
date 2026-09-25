# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=5050

WORKDIR /app

# Install dependencies before application code so this layer is reused when only
# source files change.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Run without root privileges.  One threaded worker is intentional: the
# dashboard keeps its live metrics and Socket.IO state in process memory.
RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 5050

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5050/health', timeout=3)"

CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "1", "--worker-class", "gthread", "--threads", "8", "wsgi:app"]
