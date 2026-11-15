#!/usr/bin/env bash
# Auto-filter VPS deploy — FAST (zero APT wait), uses exported shell credentials.
# Supports:
#   export BOT_TOKEN="..."
#   export API_ID="..."   or  export APP_ID="..."
#   export API_HASH="..."
#   export CHANNEL_ID="..."  or  export CHANNELS="..."
#   export DATABASE_URI="..."
#   export ADMINS="..."
# then:  sudo -E bash deploy-now.sh
#
# FORCE_APT_UNLOCK=1 to clear stuck apt locks (no waiting queue).
set -Eeuo pipefail
cd "$(dirname "$0")"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'
log(){ printf "${CYAN}[deploy]${NC} %s\n" "$*"; }
ok(){ printf "${GREEN}[ok]${NC} %s\n" "$*"; }
warn(){ printf "${YELLOW}[warn]${NC} %s\n" "$*"; }
die(){ printf "${RED}[error]${NC} %s\n" "$*" >&2; exit 1; }
trap 'rc=$?; printf "${RED}[error]${NC} Deploy failed at line %s (exit %s).\n" "$LINENO" "$rc" >&2; exit "$rc"' ERR

[[ -f bot.py && -f requirements.txt ]] || die "Run from project root (bot.py + requirements.txt required)."
IS_TERMUX=0
if [[ -n "${PREFIX:-}" && -d /data/data/com.termux ]] || command -v termux-info >/dev/null 2>&1; then IS_TERMUX=1; fi
IS_ROOT=0; [[ $EUID -eq 0 ]] && IS_ROOT=1
SUDO=()
if [[ $IS_ROOT -eq 0 && $IS_TERMUX -eq 0 ]]; then
  command -v sudo >/dev/null 2>&1 || die "sudo required (or run as root)."
  SUDO=(sudo)
fi
runroot(){ if [[ $IS_TERMUX -eq 1 ]]; then "$@"; else "${SUDO[@]}" "$@"; fi; }

# ---------- ZERO APT wait ----------
wait_apt_lock(){
  local force="${FORCE_APT_UNLOCK:-0}" busy=0
  if command -v fuser >/dev/null 2>&1; then
    fuser /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock >/dev/null 2>&1 && busy=1
  fi
  if pgrep -x apt >/dev/null 2>&1 || pgrep -x apt-get >/dev/null 2>&1 || pgrep -x dpkg >/dev/null 2>&1 || pgrep -x unattended-upgr >/dev/null 2>&1; then
    busy=1
  fi
  (( busy == 0 )) && return 0
  if [[ "$force" == "1" ]]; then
    warn "APT busy — FORCE_APT_UNLOCK=1: clearing locks…"
    runroot pkill -9 -x apt 2>/dev/null || true
    runroot pkill -9 -x apt-get 2>/dev/null || true
    runroot pkill -9 -x dpkg 2>/dev/null || true
    runroot pkill -9 -x unattended-upgr 2>/dev/null || true
    runroot rm -f /var/lib/dpkg/lock-frontend /var/lib/dpkg/lock /var/lib/apt/lists/lock /var/cache/apt/archives/lock 2>/dev/null || true
    runroot dpkg --configure -a 2>/dev/null || true
    return 0
  fi
  warn "APT busy — proceeding immediately (no wait). If install fails: FORCE_APT_UNLOCK=1 bash deploy.sh"
  return 0
}
apt(){ wait_apt_lock; runroot apt-get "$@"; }

# ---------- Alias mapping (VPS export style → bot keys) ----------
# APP_ID -> API_ID, CHANNEL_ID -> CHANNELS, ADMIN_ID -> ADMINS
if [[ -z "${API_ID:-}" && -n "${APP_ID:-}" ]]; then export API_ID="$APP_ID"; fi
if [[ -z "${CHANNELS:-}" && -n "${CHANNEL_ID:-}" ]]; then export CHANNELS="$CHANNEL_ID"; fi
if [[ -z "${ADMINS:-}" && -n "${ADMIN_ID:-}" ]]; then export ADMINS="$ADMIN_ID"; fi
if [[ -z "${BOT_TOKEN:-}" && -n "${TOKEN:-}" ]]; then export BOT_TOKEN="$TOKEN"; fi
if [[ -z "${DATABASE_URI:-}" && -n "${MONGO_URI:-}" ]]; then export DATABASE_URI="$MONGO_URI"; fi
if [[ -z "${DATABASE_URI:-}" && -n "${MONGO_URL:-}" ]]; then export DATABASE_URI="$MONGO_URL"; fi

# ---------- Merge shell-exported credentials into .env ----------
write_env_from_shell(){
  local envfile=".env"
  touch "$envfile"
  chmod 600 "$envfile"

  # Keys we pull from the current shell environment into .env
  local keys=(
    BOT_TOKEN API_ID API_HASH SESSION APP_ID
    DATABASE_URI DATABASE_NAME COLLECTION_NAME
    FILE_DB_URI SEC_FILE_DB_URI USER_DB_URI OTHER_DB_URI CLONE_DATABASE_URI
    ADMINS ADMIN_ID AUTH_USERS
    CHANNELS CHANNEL_ID LOG_CHANNEL DELETE_CHANNELS
    AUTH_CHANNEL AUTH_GROUPS INDEX_REQ_CHANNEL FILE_STORE_CHANNEL
    PORT SUPPORT_CHAT GRP_LNK CHNL_LNK
    SHORTLINK_URL SHORTLINK_API SHORTLINK_MODE
    VERIFY VERIFY_SHORTLINK_URL VERIFY_SHORTLINK_API
    VERIFY_SECOND_SHORTNER VERIFY_SND_SHORTLINK_URL VERIFY_SND_SHORTLINK_API
    VERIFY_TUTORIAL TUTORIAL VERIFY_EXPIRE_SECONDS
    PICS PUBLIC_FILE_STORE MULTIPLE_DATABASE
    USE_CAPTION_FILTER MAX_B_TN AUTO_DELETE AUTO_FFILTER
    PROTECT_CONTENT IS_TUTORIAL CUSTOM_FILE_CAPTION BATCH_FILE_CAPTION
  )

  local tmp
  tmp="$(mktemp)"
  # Keep existing .env lines that we are not overriding
  declare -A override=()
  local k v
  for k in "${keys[@]}"; do
    v="${!k-}"
    if [[ -n "${v}" ]]; then
      override["$k"]=1
    fi
  done

  if [[ -f "$envfile" ]]; then
    while IFS= read -r line || [[ -n "$line" ]]; do
      if [[ "$line" =~ ^([A-Za-z_][A-Za-z0-9_]*)= ]]; then
        key="${BASH_REMATCH[1]}"
        if [[ -n "${override[$key]+x}" ]]; then
          continue  # will rewrite from shell
        fi
      fi
      printf '%s\n' "$line" >> "$tmp"
    done < "$envfile"
  fi

  local written=0
  for k in "${keys[@]}"; do
    v="${!k-}"
    if [[ -n "${v}" ]]; then
      # Escape nothing special for .env plain assignment
      printf '%s=%s\n' "$k" "$v" >> "$tmp"
      written=$((written+1))
    fi
  done

  # Ensure canonical keys exist when only aliases were exported
  if [[ -n "${API_ID:-}" ]] && ! grep -q '^API_ID=' "$tmp" 2>/dev/null; then
    printf 'API_ID=%s\n' "$API_ID" >> "$tmp"
  fi
  if [[ -n "${CHANNELS:-}" ]] && ! grep -q '^CHANNELS=' "$tmp" 2>/dev/null; then
    printf 'CHANNELS=%s\n' "$CHANNELS" >> "$tmp"
  fi
  if [[ -n "${ADMINS:-}" ]] && ! grep -q '^ADMINS=' "$tmp" 2>/dev/null; then
    printf 'ADMINS=%s\n' "$ADMINS" >> "$tmp"
  fi

  mv "$tmp" "$envfile"
  chmod 600 "$envfile"
  if (( written > 0 )); then
    ok "Merged $written credential(s) from shell environment into .env"
  fi
}

log "Detecting platform… (FAST deploy, zero APT wait)"
if [[ $IS_TERMUX -eq 1 ]]; then
  pkg update -y || true
  pkg install -y python git clang libffi openssl rust binutils make ffmpeg 2>/dev/null || true
elif [[ -f /etc/alpine-release ]]; then
  runroot apk add --no-cache python3 py3-pip py3-virtualenv git build-base libffi-dev openssl-dev curl bash ffmpeg jpeg-dev zlib-dev libpng-dev || true
elif [[ -f /etc/redhat-release || -f /etc/rocky-release || -f /etc/almalinux-release ]]; then
  PM=dnf; command -v dnf >/dev/null 2>&1 || PM=yum
  runroot "$PM" install -y python3 python3-pip git gcc gcc-c++ make libffi-devel openssl-devel curl ffmpeg libjpeg-turbo-devel zlib-devel libpng-devel || true
elif command -v apt-get >/dev/null 2>&1; then
  log "APT fast path (no queue)…"
  apt update -y || apt update || true
  apt install -y python3 python3-venv python3-pip git build-essential libffi-dev libssl-dev curl ca-certificates screen ffmpeg libjpeg-dev zlib1g-dev libpng-dev libwebp-dev libtiff-dev libopenjp2-7-dev || true
else
  die "Unsupported package manager. Install Python 3 + venv + ffmpeg manually."
fi

PY="$(command -v python3 || command -v python || true)"
[[ -n "$PY" ]] || die "Python 3 not found."
"$PY" -c 'import sys; print("Python", sys.version.split()[0])'

# Seed blank .env if missing
if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    cp .env.example .env
  else
    cat > .env <<'ENVEOF'
BOT_TOKEN=
API_ID=
API_HASH=
DATABASE_URI=
ADMINS=
DATABASE_NAME=tgboxoffice
COLLECTION_NAME=tgboxoffice_files
PORT=8080
ENVEOF
  fi
  chmod 600 .env
fi

# Pull credentials from current shell (export BOT_TOKEN=... etc.)
write_env_from_shell

# Load .env for validation
set -a
# shellcheck disable=SC1091
source .env 2>/dev/null || true
set +a

# Re-apply aliases after sourcing .env
if [[ -z "${API_ID:-}" && -n "${APP_ID:-}" ]]; then export API_ID="$APP_ID"; fi
if [[ -z "${CHANNELS:-}" && -n "${CHANNEL_ID:-}" ]]; then export CHANNELS="$CHANNEL_ID"; fi
if [[ -z "${ADMINS:-}" && -n "${ADMIN_ID:-}" ]]; then export ADMINS="$ADMIN_ID"; fi

missing=()
[[ -z "${BOT_TOKEN:-}" ]] && missing+=(BOT_TOKEN)
[[ -z "${API_ID:-}" ]] && missing+=(API_ID/APP_ID)
[[ -z "${API_HASH:-}" ]] && missing+=(API_HASH)
[[ -z "${DATABASE_URI:-}" ]] && missing+=(DATABASE_URI)
[[ -z "${ADMINS:-}" ]] && missing+=(ADMINS)
if ((${#missing[@]})); then
  die "Missing credentials: ${missing[*]}

Provide them either:
  1) export in shell then:  sudo -E bash deploy-now.sh
     export BOT_TOKEN=\"...\"
     export API_ID=\"...\"          # or APP_ID
     export API_HASH=\"...\"
     export DATABASE_URI=\"...\"
     export ADMINS=\"123456789\"
     export CHANNEL_ID=\"-100...\"  # optional
  2) Or put KEY=value lines in .env
  3) Or /exportcreds from a running bot, then source the .sh file"
fi

log "Creating virtualenv + installing requirements…"
if [[ ! -x venv/bin/python ]]; then
  "$PY" -m venv venv || die "venv failed — install python3-venv"
fi
venv/bin/python -m pip install --upgrade pip setuptools wheel
# Prefer binary wheels (avoids compiling old Pillow on Python 3.12)
if ! venv/bin/python -m pip install --no-cache-dir --only-binary=:all: -r requirements.txt; then
  warn "Binary-only install failed for some packages — retrying with source build allowed…"
  venv/bin/python -m pip install --no-cache-dir -r requirements.txt || die "pip install failed. Check the package error above, install the required system build libraries, and re-run ./deploy.vps"
fi

# TgCrypto is an optional Pyrogram accelerator. Keep it out of the core
# requirements so a missing wheel/compiler never aborts an otherwise valid
# bot deployment. Try a wheel first, then build the pinned source release.
log "Installing optional TgCrypto accelerator…"
if venv/bin/python -m pip install --no-cache-dir --prefer-binary "TgCrypto==1.2.5"; then
  ok "TgCrypto installed (accelerated crypto enabled)."
elif venv/bin/python -m pip install --no-cache-dir --no-build-isolation "TgCrypto==1.2.5"; then
  ok "TgCrypto installed from source."
else
  warn "TgCrypto could not be built for this Python/platform. Pyrogram will use its built-in pure-Python crypto; bot functionality remains available, but transfers may be slower."
fi

log "Quick import check…"
venv/bin/python - <<'PY' || die "Import check failed — fix credentials / dependencies"
import info
print("info OK | API_ID=", getattr(info, "API_ID", None), "| ADMINS=", getattr(info, "ADMINS", None))
PY

SERVICE="auto-filter"
APP_DIR="$PWD"
PYTHON_BIN="$APP_DIR/venv/bin/python"

if [[ $IS_TERMUX -eq 0 && $IS_ROOT -eq 1 ]] && command -v systemctl >/dev/null 2>&1; then
  cat > "/etc/systemd/system/${SERVICE}.service" <<UNIT
[Unit]
Description=Auto-filter Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=${APP_DIR}
EnvironmentFile=${APP_DIR}/.env
ExecStart=${PYTHON_BIN} ${APP_DIR}/bot.py
Restart=always
RestartSec=3
TimeoutStopSec=20
KillSignal=SIGINT
NoNewPrivileges=true
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
UNIT
  systemctl daemon-reload
  systemctl enable "$SERVICE" >/dev/null 2>&1 || true
  systemctl restart "$SERVICE"
  sleep 2
  if systemctl is-active --quiet "$SERVICE"; then
    ok "Service active — runs 24/7 (auto-restart + boot)."
    echo "Logs:   journalctl -u ${SERVICE} -f"
    echo "Status: systemctl status ${SERVICE}"
    echo "Stop:   systemctl stop ${SERVICE}"
    echo "Export: /exportcreds in private chat with bot (admin)"
  else
    systemctl --no-pager --full status "$SERVICE" || true
    journalctl -u "$SERVICE" -n 40 --no-pager || true
    die "Service did not stay running — check logs above."
  fi
elif [[ $IS_TERMUX -eq 0 ]] && command -v screen >/dev/null 2>&1; then
  screen -S auto-filter -X quit >/dev/null 2>&1 || true
  screen -dmS auto-filter bash -lc "cd '$APP_DIR' && set -a && source '$APP_DIR/.env' && set +a && exec '$PYTHON_BIN' '$APP_DIR/bot.py'"
  sleep 2
  screen -list | grep -q auto-filter || die "screen session failed"
  ok "Running in screen 'auto-filter'. Attach: screen -r auto-filter"
else
  ok "Deps ready. Starting in foreground…"
  exec venv/bin/python bot.py
fi
