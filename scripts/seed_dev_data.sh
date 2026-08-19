#!/usr/bin/env bash
# Seed local warehouse user and sample catalogue data.
# Run from project root: ./scripts/seed_dev_data.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ -f ".venv/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source ".venv/bin/activate"
fi

python manage.py migrate --noinput
python manage.py seed_dev_data "$@"
