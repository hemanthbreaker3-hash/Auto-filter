#!/usr/bin/env bash
# Run from extracted folder (or home after unzip). Finds project root automatically.
set -Eeuo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
if [[ -f "$HERE/bot.py" && -f "$HERE/deploy.sh" ]]; then
  ROOT="$HERE"
elif [[ -f "$HERE/movieszoneflix/bot.py" && -f "$HERE/movieszoneflix/deploy.sh" ]]; then
  ROOT="$HERE/movieszoneflix"
elif [[ -f "$HERE/MoviesZoneFlix/bot.py" && -f "$HERE/MoviesZoneFlix/deploy.sh" ]]; then
  ROOT="$HERE/MoviesZoneFlix"
else
  # search one level down
  found="$(find "$HERE" -maxdepth 2 -type f -name bot.py 2>/dev/null | head -1 || true)"
  if [[ -n "$found" ]]; then
    ROOT="$(cd "$(dirname "$found")" && pwd)"
  else
    echo "[error] bot.py not found. Unzip movieszoneflix-READY.zip first, then run from that folder."
    echo "  unzip movieszoneflix-READY.zip"
    echo "  cd movieszoneflix"
    echo "  ./deploy.vps"
    exit 1
  fi
fi
cd "$ROOT"
echo "[deploy] Project: $ROOT"
if [[ ! -f deploy.sh ]]; then
  echo "[error] deploy.sh missing in $ROOT — use movieszoneflix-READY.zip (not incomplete source archive)."
  exit 1
fi
# preserve env under sudo
if [[ $EUID -ne 0 ]] && command -v sudo >/dev/null 2>&1; then
  if [[ -n "${BOT_TOKEN:-}${API_ID:-}${APP_ID:-}" ]]; then
    exec sudo -E bash ./deploy.sh "$@"
  else
    exec sudo bash ./deploy.sh "$@"
  fi
fi
exec bash ./deploy.sh "$@"
