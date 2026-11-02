# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

# Clone Code Credit : YT - @MoviesZoneFlix / TG - @MoviesZoneFlix / GitHub - @MoviesZoneFlix

import logging, logging.config, pytz, asyncio

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("cinemagoer").setLevel(logging.ERROR)

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
    try:
        await TechVJBot.send_message(chat_id=LOG_CHANNEL, text=script.RESTART_TXT.format(today, time))
    except:
        print("Make Your Bot Admin In Log Channel With Full Rights")
    for ch in await db.get_managed_channels():
        try:
            k = await TechVJBot.send_message(chat_id=ch, text="**Bot Restarted**")
            await k.delete()
        except:
            print("Make Your Bot Admin In File Channels With Full Rights")
    try:
        k = await TechVJBot.send_message(chat_id=AUTH_CHANNEL, text="**Bot Restarted**")
        await k.delete()
    except:
        print("Make Your Bot Admin In Force Subscribe Channel With Full Rights")
    if CLONE_MODE == True:
        print("Restarting All Clone Bots.......")
        await restart_bots()
        print("Restarted All Clone Bots.")
    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()
    await idle()


if __name__ == '__main__':
    try:
        loop.run_until_complete(start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')


