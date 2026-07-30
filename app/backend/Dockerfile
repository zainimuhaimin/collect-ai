FROM python:3.12-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# libpq-dev + gcc: safety net in case no prebuilt wheel matches the platform
# for psycopg2-binary/bcrypt.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

COPY app/backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Build context is the repo root (not app/backend/) specifically so this can also
# pull in app/shared/ — services/restructuring_service.py imports
# `shared.restructuring_offer_calculator`, a sibling package outside app/backend/.
COPY app/backend/ .
COPY app/shared/ ./shared/
COPY app/machine-learning/ ./machine-learning/

EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
