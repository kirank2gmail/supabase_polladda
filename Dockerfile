# SportsPoll API — FastAPI backend, deployed to Cloud Run.
#
# Builds from the repo root because api/main.py imports data/ and utils/
# as top-level packages (same layout as running uvicorn locally from here).
# The Streamlit app (app.py, pages/, admin/) is intentionally NOT copied —
# api/ has no dependency on it (verified: no imports of admin/pages/app.py
# anywhere under api/).
#
# Config is via environment variables, not .streamlit/secrets.toml — that
# file is gitignored and deliberately excluded via .dockerignore. Cloud Run
# env vars to set: SUPABASE_URL, SUPABASE_KEY, CORS_ORIGINS, and optionally
# EMAIL_SENDER/EMAIL_APP_PASSWORD/EMAIL_RECIPIENT (see utils/email_sender.py).

FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt ./requirements.txt
COPY api/requirements.txt ./api-requirements.txt
RUN pip install --no-cache-dir -r requirements.txt -r api-requirements.txt

COPY data/ ./data/
COPY utils/ ./utils/
COPY api/ ./api/

ENV PYTHONUNBUFFERED=1
EXPOSE 8080
CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
