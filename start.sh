#!/usr/bin/env bash
set -Eeuo pipefail
cd "$(dirname "$(readlink -f "$0")")"
export PYTHONUNBUFFERED=1
export PORT="${PORT:-10000}"
echo "Starting TGBoxOffice..."
exec python -u bot.py
