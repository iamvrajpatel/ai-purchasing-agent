#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/backend"

if [[ -d ".venv" ]]; then
  source .venv/bin/activate
fi

python -m app.verify_demo_db
