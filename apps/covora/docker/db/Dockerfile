# Postgres 16 + pgvector, built on the official image (avoids pulling pgvector/pgvector).
FROM postgres:16
RUN apt-get update \
    && apt-get install -y --no-install-recommends postgresql-16-pgvector \
    && rm -rf /var/lib/apt/lists/*
