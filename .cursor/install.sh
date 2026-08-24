#!/usr/bin/env bash
# CentCompras Cloud Agent install: idempotent dependency + database bootstrap.
# Runs after checkout. Bakes seeded PostgreSQL data into the environment build.
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 1. System packages (PostgreSQL + venv). No-op once present / baked into snapshot.
if ! command -v pg_ctlcluster >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq postgresql postgresql-contrib python3-venv
fi

PGVER="$(ls /etc/postgresql/ | sort -V | tail -1)"
HBA="/etc/postgresql/${PGVER}/main/pg_hba.conf"

# 2. Trust local connections (dev only). Idempotent via marker line.
if ! sudo grep -q "CentCompras dev" "$HBA"; then
    sudo cp "$HBA" "${HBA}.bak"
    printf '%s\n' \
        "# --- CentCompras dev: trust local connections ---" \
        "local   all             all                                     trust" \
        "host    all             all             127.0.0.1/32            trust" \
        "host    all             all             ::1/128                 trust" \
        | sudo tee /tmp/hba_prepend >/dev/null
    sudo bash -c "cat /tmp/hba_prepend '${HBA}.bak' > '$HBA'"
fi

# 3. Ensure PostgreSQL is running so migrate/seed can connect.
sudo pg_ctlcluster "$PGVER" main start 2>/dev/null || true
for _ in $(seq 1 30); do pg_isready -h 127.0.0.1 -q && break; sleep 1; done

# 4. Application database (idempotent).
if ! psql -h 127.0.0.1 -U postgres -tAc "SELECT 1 FROM pg_database WHERE datname='centcompras_db'" | grep -q 1; then
    psql -h 127.0.0.1 -U postgres -c "CREATE DATABASE centcompras_db"
fi

# 5. Python virtualenv + dependencies.
if [ ! -d .venv ]; then
    python3 -m venv .venv
fi
.venv/bin/python -m pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q

# 6. Django settings (config/settings.py is gitignored).
if [ ! -f config/settings.py ]; then
    cp config/settings.example.py config/settings.py
fi

# 7. Schema + seed data (both idempotent). Snapshot bake; start.sh repeats this
#    after checkout so later revisions still match the current codebase.
.venv/bin/python manage.py migrate --noinput
./scripts/seed_dev_data.sh
