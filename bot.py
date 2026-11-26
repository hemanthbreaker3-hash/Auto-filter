# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

# Clone Code Credit : YT - @MoviesZoneFlix / TG - @MoviesZoneFlix / GitHub - @MoviesZoneFlix

import logging, logging.config, pytz, asyncio

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("cinemagoer").setLevel(logging.CRITICAL)
logging.getLogger("imdbpy").setLevel(logging.CRITICAL)
logging.getLogger("imdb").setLevel(logging.CRITICAL)

from pyrogram import Client, idle
from info import *

_missing = []
if not BOT_TOKEN:
    _missing.append("BOT_TOKEN")
if not API_ID or not API_HASH:
    _missing.extend([name for name, value in (("API_ID", API_ID), ("API_HASH", API_HASH)) if not value])
if not DATABASE_URI:
    _missing.append("DATABASE_URI (MongoDB connection string)")
if not ADMINS:
    _missing.append("ADMINS (at least one trusted Telegram numeric user ID)")
if _missing:
    raise RuntimeError("MoviesZoneFlix cannot start. Configure: " + ", ".join(_missing) + ". A bot token alone is not sufficient for Pyrogram + MongoDB.")

from database.users_chats_db import db
from utils import temp
from typing import Union, Optional, AsyncGenerator
from Script import script 
from datetime import date, datetime 
from aiohttp import web
from plugins import web_server
from plugins.clone import restart_bots

from TechVJ.bot import TechVJBot
from TechVJ.util.telegram_rich import api_request
from TechVJ.util.keepalive import ping_server
from TechVJ.bot.clients import initialize_clients
from TechVJ.bot.register_commands import register_all_commands

# Pyrogram loads the configured plugins package automatically on start.
# Do not import the same modules a second time; doing so registers duplicate handlers.
TechVJBot.start()
loop = asyncio.get_event_loop()


async def start():
    print('\n')
    print('Initializing MoviesZoneFlix')
    bot_info = await TechVJBot.get_me()
    await initialize_clients()
    # Load database-managed admins before command handlers become active.
    import info as bot_info_config
    for _admin_id in await db.get_admins():
        if _admin_id not in bot_info_config.ADMINS:
            bot_info_config.ADMINS.append(_admin_id)
        if _admin_id not in bot_info_config.AUTH_USERS:
            bot_info_config.AUTH_USERS.append(_admin_id)
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    me = await TechVJBot.get_me()
    temp.BOT = TechVJBot
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    # Deploy succeeded and the bot's identity is confirmed — register the
    # "/" command menu with Telegram now (public menu for everyone, full
    # menu for ADMINS). See TechVJ/bot/register_commands.py.
    await register_all_commands(TechVJBot)
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    # Validate every configured destination with the official Bot API. This does
    # not depend on Pyrogram's local peer/access-hash cache.
    destinations = {}
    def _add_destination(value, label):
        if value in (None, "", 0, "0"):
            return
        try:
            chat_id = int(value)
        except (TypeError, ValueError):
            logging.warning("Skipping invalid %s destination: %r", label, value)
            return
        destinations.setdefault(chat_id, set()).add(label)

    # Include every environment-configured destination, not just the FSub/log
    # entries.  All checks below use the official Bot API so no Pyrogram peer
    # cache or access-hash is required for numeric chat IDs.
    _add_destination(LOG_CHANNEL, "log channel")
    _add_destination(AUTH_CHANNEL, "environment FSub")
    _add_destination(globals().get("REQST_CHANNEL"), "request channel")
    _add_destination(globals().get("INDEX_REQ_CHANNEL"), "index request channel")
    _add_destination(globals().get("SUPPORT_CHAT_ID"), "support group")
    for _channel in (globals().get("CHANNELS", []) or []):
        _add_destination(_channel, "file/index channel")
    for _channel in (globals().get("FILE_STORE_CHANNEL", []) or []):
        _add_destination(_channel, "file-store channel")
    for _channel in (globals().get("DELETE_CHANNELS", []) or []):
        _add_destination(_channel, "delete-index channel")
    for _channel in await db.get_managed_channels():
        _add_destination(_channel, "managed/index channel")
    try:
        # Validate saved FSub chats even while the FSub toggle is OFF; otherwise
        # a broken configured destination can remain hidden until users hit /start.
        for _channel in await db.get_force_subscribe_chats():
            _add_destination(_channel, "panel FSub")
    except Exception as _exc:
        logging.warning("Could not load panel FSub destinations during startup: %s", _exc)
    try:
        _auto_post_settings = await db.get_auto_post_settings()
        _add_destination(_auto_post_settings.get("post_channel_id"), "auto-post destination")
    except Exception as _exc:
        logging.warning("Could not load auto-post destination during startup: %s", _exc)

    for _chat_id, _labels in destinations.items():
        _label = ", ".join(sorted(_labels))
        try:
            _chat = await api_request(TechVJBot, "getChat", {"chat_id": _chat_id})
            _title = _chat.get("title") or _chat.get("username") or str(_chat_id)
            _bot_member = await api_request(TechVJBot, "getChatMember", {
                "chat_id": _chat_id, "user_id": int(me.id)
            })
            _bot_status = str((_bot_member or {}).get("status", "unknown")).lower()
            _can_send = _bot_status in {"creator", "administrator", "member"}
            logging.info(
                "Startup chat resolved: %s [%s] roles=%s bot_status=%s",
                _title, _chat_id, _label, _bot_status
            )
            if not _can_send:
                logging.warning(
                    "Startup access warning: %s [%s] bot membership status is %s; testing send permission anyway",
                    _title, _chat_id, _bot_status
                )
            # A short-lived message verifies actual send permission. Delete it
            # immediately through Bot API, not Pyrogram's MTProto peer resolver.
            _probe = await api_request(TechVJBot, "sendMessage", {
                "chat_id": _chat_id,
                "text": "MoviesZoneFlix startup access check.",
                "disable_notification": True,
            })
            _message_id = (_probe or {}).get("message_id")
            _probe_deleted = False
            if _message_id:
                try:
                    await api_request(TechVJBot, "deleteMessage", {
                        "chat_id": _chat_id, "message_id": int(_message_id)
                    })
                    _probe_deleted = True
                except Exception as _delete_exc:
                    logging.warning(
                        "Startup check: %s (%s) is reachable but test message %s could not be deleted: %s",
                        _title, _chat_id, _message_id, _delete_exc
                    )
            logging.info(
                "Startup access OK: %s [%s] (%s); test_message_deleted=%s",
                _title, _chat_id, _label, _probe_deleted
            )
        except Exception as _exc:
            logging.error(
                "Startup access FAILED: chat=%s roles=%s reason=%s. Check the ID, bot membership, and channel admin/send permissions.",
                _chat_id, _label, _exc
            )

    try:
        await api_request(TechVJBot, "sendMessage", {
            "chat_id": int(LOG_CHANNEL),
            "text": script.RESTART_TXT.format(today, time)
        })
    except Exception as _exc:
        logging.error("Could not send restart notice to log channel %s: %s", LOG_CHANNEL, _exc)

    if CLONE_MODE == True:
        print("Restarting All Clone Bots.......")
        await restart_bots()
        print("Restarted All Clone Bots.")
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    # If another process already owns the configured port (e.g. 8080),
    # try nearby ports instead of crashing the bot startup.
    requested_port = int(PORT)
    bound_port = None
    for candidate_port in [requested_port] + list(range(requested_port + 1, requested_port + 11)):
        try:
            await web.TCPSite(app, bind_address, candidate_port).start()
            bound_port = candidate_port
            break
        except OSError as exc:
            if getattr(exc, "errno", None) != 98:
                raise
            logging.warning("Web server port %s is occupied; trying next port", candidate_port)
    if bound_port is None:
        raise RuntimeError(f"Unable to bind web server: ports {requested_port}-{requested_port + 10} are occupied")
    if bound_port != requested_port:
        logging.warning("Web server started on fallback port %s (configured port %s)", bound_port, requested_port)
    await idle()


if __name__ == '__main__':
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')


