"""Admin-only export of bot credentials for VPS deploy (export KEY="value" shell format)."""
import io
import os
from datetime import datetime, timezone

from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton

import info


# Canonical keys + common VPS aliases users expect
_EXPORT_KEYS = [
    # Core Telegram
    "BOT_TOKEN", "API_ID", "API_HASH", "SESSION",
    # Aliases often used on VPS
    "APP_ID",  # alias of API_ID
    # Mongo / DB
    "DATABASE_URI", "DATABASE_NAME", "COLLECTION_NAME",
    "FILE_DB_URI", "SEC_FILE_DB_URI", "USER_DB_URI", "OTHER_DB_URI", "CLONE_DATABASE_URI",
    # Admins / channels
    "ADMINS", "ADMIN_ID", "AUTH_USERS",
    "CHANNELS", "CHANNEL_ID", "LOG_CHANNEL", "DELETE_CHANNELS",
    "AUTH_CHANNEL", "AUTH_GROUPS", "INDEX_REQ_CHANNEL", "FILE_STORE_CHANNEL",
    # Runtime
    "PORT", "SUPPORT_CHAT", "GRP_LNK", "CHNL_LNK",
    # Shortener / verify
    "SHORTLINK_URL", "SHORTLINK_API", "SHORTLINK_MODE",
    "VERIFY", "VERIFY_SHORTLINK_URL", "VERIFY_SHORTLINK_API",
    "VERIFY_SECOND_SHORTNER", "VERIFY_SND_SHORTLINK_URL", "VERIFY_SND_SHORTLINK_API",
    "VERIFY_TUTORIAL", "TUTORIAL", "VERIFY_EXPIRE_SECONDS",
    # Misc
    "PICS", "PUBLIC_FILE_STORE", "MULTIPLE_DATABASE",
    "USE_CAPTION_FILTER", "MAX_B_TN", "AUTO_DELETE", "AUTO_FFILTER",
    "PROTECT_CONTENT", "IS_TUTORIAL", "CUSTOM_FILE_CAPTION", "BATCH_FILE_CAPTION",
]


def _authorized(message: Message) -> bool:
    return bool(message.from_user and message.from_user.id in info.ADMINS)


def _shell_quote(val: str) -> str:
    """Safe double-quoted value for export KEY="value"."""
    return str(val).replace("\\", "\\\\").replace('"', '\\"').replace("$", "\\$").replace("`", "\\`")


def _val_from_info(key: str):
    # Map aliases to info attributes
    attr_map = {
        "APP_ID": "API_ID",
        "ADMIN_ID": "ADMINS",
        "CHANNEL_ID": "CHANNELS",
    }
    attr_name = attr_map.get(key, key)
    attr = getattr(info, attr_name, None)
    if attr is None:
        return None
    if isinstance(attr, (list, tuple, set)):
        return " ".join(str(x) for x in attr)
    if isinstance(attr, bool):
        return "True" if attr else "False"
    return str(attr)


def _collect_pairs() -> list:
    """Return ordered list of (KEY, value) for export."""
    pairs = []
    seen = set()

    def add(key, val):
        if key in seen:
            return
        if val is None:
            return
        val = str(val).strip()
        if not val or val in ("0", "None", "[]", "()"):
            # keep real zeros only for numeric ids that are meaningful — skip empty noise
            if key not in ("PORT",) and val in ("0", "None", "[]", "()"):
                return
            if not val:
                return
        seen.add(key)
        pairs.append((key, val))

    # 1) Known keys: env first, then info module
    for key in _EXPORT_KEYS:
        val = os.environ.get(key)
        if val is None or not str(val).strip():
            val = _val_from_info(key)
        # Special: always emit APP_ID when API_ID exists (VPS convenience)
        if key == "APP_ID" and (val is None or not str(val).strip()):
            val = os.environ.get("API_ID") or _val_from_info("API_ID")
        if key == "CHANNEL_ID" and (val is None or not str(val).strip()):
            val = os.environ.get("CHANNELS") or _val_from_info("CHANNELS")
            if val:
                # first channel id for single CHANNEL_ID convenience
                first = str(val).split()[0] if str(val).split() else val
                add("CHANNEL_ID", first)
                continue
        add(key, val)

    # 2) Extra uppercase env vars that look bot-related
    skip_prefix = (
        "PWD", "HOME", "PATH", "LANG", "TERM", "SHELL", "USER", "LOGNAME",
        "SSH", "XDG", "LC_", "OLDPWD", "SHLVL", "HOSTNAME", "_", "LS_",
        "GPG_", "DBUS_", "QT_", "GTK_", "XAUTHORITY", "DISPLAY",
    )
    keywords = (
        "BOT", "API", "TOKEN", "MONGO", "DB", "URI", "CHANNEL", "ADMIN",
        "SHORT", "VERIFY", "AUTH", "PORT", "SESSION", "HASH", "ID",
        "LINK", "CHAT", "PIC", "CAPTION", "FILTER", "STORE", "APP_",
    )
    for key, val in sorted(os.environ.items()):
        if key in seen:
            continue
        if not key.isupper():
            continue
        if any(key.startswith(p) for p in skip_prefix):
            continue
        if not val or not str(val).strip():
            continue
        if any(x in key for x in keywords):
            add(key, val)

    return pairs


def _format_shell_exports(pairs: list) -> str:
    lines = [
        "#!/usr/bin/env bash",
        "# Auto-filter credentials for VPS — source this file or paste into shell before deploy",
        f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "# Usage:",
        "#   source credentials.export.sh",
        "#   # or:  bash -c 'source credentials.export.sh && cd Auto-filter-main && sudo -E bash deploy-now.sh'",
        "# PRIVATE — do not share.",
        "",
    ]
    for key, val in pairs:
        lines.append(f'export {key}="{_shell_quote(val)}"')
    lines.append("")
    lines.append("# After export, run:  chmod +x deploy.vps && ./deploy.vps")
    lines.append("")
    return "\n".join(lines)


def _format_dotenv(pairs: list) -> str:
    lines = [
        "# Auto-filter .env credentials",
        f"# Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
    ]
    for key, val in pairs:
        lines.append(f"{key}={val}")
    lines.append("")
    return "\n".join(lines)


@Client.on_message(filters.command(["exportcreds", "exportenv", "credentials", "export"]) & filters.private)
async def export_credentials(client: Client, message: Message):
    if not _authorized(message):
        return await message.reply_text("⛔ Admins only.")

    pairs = _collect_pairs()
    if not pairs:
        return await message.reply_text("⚠️ No credentials found in environment or config.")

    shell_body = _format_shell_exports(pairs)
    dotenv_body = _format_dotenv(pairs)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    # Primary: shell export format for VPS
    bio_sh = io.BytesIO(shell_body.encode("utf-8"))
    bio_sh.name = f"credentials.export.{stamp}.sh"

    await message.reply_document(
        document=bio_sh,
        caption=(
            "✅ <b>VPS credentials export</b> (shell)\n\n"
            "Format:\n"
            "<code>export API_HASH=\"…\"</code>\n"
            "<code>export APP_ID=\"…\"</code>\n"
            "<code>export CHANNEL_ID=\"…\"</code>\n\n"
            "<b>On VPS:</b>\n"
            "<code>source credentials.export.*.sh</code>\n"
            "<code>chmod +x deploy.vps && ./deploy.vps</code>\n\n"
            "<i>Private — do not forward.</i>"
        ),
    )

    # Secondary: classic .env for EnvironmentFile / dotenv
    bio_env = io.BytesIO(dotenv_body.encode("utf-8"))
    bio_env.name = f"credentials.{stamp}.env"
    await message.reply_document(
        document=bio_env,
        caption=(
            "📄 Also as <code>.env</code> (KEY=value)\n"
            "Copy to project folder as <code>.env</code> if you prefer."
        ),
    )


@Client.on_message(filters.command(["exportcreds", "exportenv", "credentials", "export"]) & filters.group)
async def export_credentials_group(client: Client, message: Message):
    if not _authorized(message):
        return
    await message.reply_text("🔐 Use <code>/exportcreds</code> in <b>private chat</b> with the bot.")
