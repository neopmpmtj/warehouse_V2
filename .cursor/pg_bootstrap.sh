#!/usr/bin/env bash
# Idempotent Cloud Agent PostgreSQL bootstrap: database + Django default role.
# Django's POSTGRES_* fallback uses USER=appuser / PASSWORD=your_password_here
# when DATABASE_URL is unset (.env.example leaves those commented).
# Requires PostgreSQL accepting connections on 127.0.0.1 (trust HBA).
set -euo pipefail

PSQL=(psql -h 127.0.0.1 -U postgres -v ON_ERROR_STOP=1)

if ! "${PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='centcompras_db'" | grep -q 1; then
    "${PSQL[@]}" -c "CREATE DATABASE centcompras_db"
fi

if ! "${PSQL[@]}" -tAc "SELECT 1 FROM pg_roles WHERE rolname='appuser'" | grep -q 1; then
    "${PSQL[@]}" -c "CREATE USER appuser WITH CREATEDB PASSWORD 'your_password_here'"
fi
# Django TestCase creates test_centcompras_db; CREATEDB is required for the suite.
"${PSQL[@]}" -c "ALTER USER appuser WITH CREATEDB"

"${PSQL[@]}" -c "ALTER DATABASE centcompras_db OWNER TO appuser"
"${PSQL[@]}" -d centcompras_db -c "GRANT ALL ON SCHEMA public TO appuser"
