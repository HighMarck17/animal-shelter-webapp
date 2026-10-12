FROM python:3.12.15-slim-trixie AS base

WORKDIR /app

# Every dependency ships binary wheels (psycopg-binary bundles libpq), so the
# image needs no compiler or -dev headers. --only-binary makes a future
# wheel-less dependency fail the build instead of compiling from source;
# --require-hashes rejects any file that differs from the lock.
COPY requirements/ requirements/
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements/production.txt

FROM base AS test
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements/test.txt
COPY . .
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

FROM base AS production
COPY . .
RUN mkdir -p /app/logs /app/staticfiles && useradd -m appuser && chown -R appuser:appuser /app
USER appuser
EXPOSE 8000
ENTRYPOINT ["./entrypoint.sh"]
