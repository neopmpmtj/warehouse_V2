#!/usr/bin/env bash
# CentCompras Cloud Agent start: bring up PostgreSQL on every boot.
# The data directory is baked into the build; only the daemon needs starting.
set -euo pipefail

PGVER="$(ls /etc/postgresql/ | sort -V | tail -1)"
sudo pg_ctlcluster "$PGVER" main start 2>/dev/null || true
for _ in $(seq 1 30); do pg_isready -h 127.0.0.1 -q && break; sleep 1; done
pg_isready -h 127.0.0.1
