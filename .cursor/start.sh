#!/usr/bin/env bash
# CentCompras Cloud Agent start: PostgreSQL + current schema/seed on every boot.
# Environment builds do not re-run install, so migrate and seed live here so the
# database matches the checked-out codebase (needed for UI work on later revisions).
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PGVER="$(ls /etc/postgresql/ | sort -V | tail -1)"
sudo pg_ctlcluster "$PGVER" main start 2>/dev/null || true
for _ in $(seq 1 30); do pg_isready -h 127.0.0.1 -q && break; sleep 1; done
pg_isready -h 127.0.0.1

if [ ! -f config/settings.py ]; then
    cp config/settings.example.py config/settings.py
fi

if [ -x .venv/bin/python ]; then
    ./scripts/seed_dev_data.sh
fi
