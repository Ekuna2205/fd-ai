FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /srv

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY alembic.ini .
COPY scripts ./scripts
COPY migrations ./migrations
COPY app ./app

# Model files are not kept in git; download and checksum-verify them at build time (needs internet).
RUN python scripts/fetch_models.py

RUN useradd --system --uid 10001 --no-create-home faceguard \
 && mkdir -p /srv/data && chown faceguard /srv/data
ENV DATA_DIR=/srv/data
VOLUME /srv/data
USER faceguard

EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=5 \
  CMD python -c "import json,urllib.request as u; d=json.load(u.urlopen('http://127.0.0.1:8000/api/health', timeout=4)); raise SystemExit(0 if d['status']=='ok' else 1)"

# Apply migrations, then serve. Migrations are idempotent, so restarts are safe.
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --proxy-headers"]
