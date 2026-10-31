
import sys
from pyromod import listen
from pyrogram import idle
import logging
import logging.config

# Get logging configurations
logging.config.fileConfig('logging.conf')
logging.getLogger().setLevel(logging.INFO)
logging.getLogger("pyrogram").setLevel(logging.ERROR)
logging.getLogger("imdbpy").setLevel(logging.ERROR)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logging.getLogger("aiohttp").setLevel(logging.ERROR)
logging.getLogger("aiohttp.web").setLevel(logging.ERROR)


from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from database.ia_filterdb import Media
from database.users_chats_db import db
from info import *
from utils import temp
from typing import Union, Optional, AsyncGenerator
from pyrogram import types
from Script import script 
from datetime import date, datetime 
import pytz
from aiohttp import web
from plugins import web_server

import asyncio
from pyrogram import idle
from lazybot import LazyPrincessBot
from util.keepalive import ping_server
from lazybot.clients import initialize_clients


async def Lazy_start():
    print('\n')
    print('Initializing TGBoxOffice...')
    if not API_ID or not API_HASH or not BOT_TOKEN:
        raise RuntimeError('Missing required configuration: set API_ID, API_HASH, and BOT_TOKEN before starting TGBoxOffice.')
    await LazyPrincessBot.start()
    bot_info = await LazyPrincessBot.get_me()
    LazyPrincessBot.username = bot_info.username
    await initialize_clients()
    logging.info("Pyrogram plugin loader initialized.")
    if ON_HEROKU:
        asyncio.create_task(ping_server())
    b_users, b_chats = await db.get_banned()
    temp.BANNED_USERS = b_users
    temp.BANNED_CHATS = b_chats
    await Media.ensure_indexes()
    me = await LazyPrincessBot.get_me()
    temp.ME = me.id
    temp.U_NAME = me.username
    temp.B_NAME = me.first_name
    LazyPrincessBot.username = '@' + me.username
    logging.info(f"{me.first_name} with for Pyrogram v{__version__} (Layer {layer}) started on {me.username}.")
    logging.info(LOG_STR)
    logging.info(script.LOGO)
    tz = pytz.timezone('Asia/Kolkata')
    today = date.today()
    now = datetime.now(tz)
    time = now.strftime("%H:%M:%S %p")
    # A missing/inaccessible log channel must not prevent the bot from starting.
    if LOG_CHANNEL:
        try:
            await LazyPrincessBot.send_message(
                chat_id=LOG_CHANNEL,
                text=script.RESTART_TXT.format(today, time)
            )
        except Exception:
            logging.exception("Could not send restart message to LOG_CHANNEL")

    app = web.AppRunner(await web_server())
    await app.setup()
    bind_address = "0.0.0.0"
    await web.TCPSite(app, bind_address, PORT).start()

    # Notify owner and every configured admin after successful initialization.
    startup_text = (
        "✅ <b>I am started!</b>\n\n"
        f"🤖 <b>Bot:</b> @{me.username or 'unknown'}\n"
        f"📅 <b>Date:</b> {today}\n"
        f"🕒 <b>Time:</b> {time} (Asia/Kolkata)"
    )
    recipients = set([OWNER_ID] + list(ADMINS))
    recipients.discard(0)
    for recipient in recipients:
        try:
            await LazyPrincessBot.send_message(chat_id=recipient, text=startup_text)
        except Exception:
            logging.exception("Could not send startup notification to chat_id=%s", recipient)

    logging.info("Startup notifications processed for %d owner/admin recipient(s).", len(recipients))
    await idle()


if __name__ == '__main__':
    try:
        asyncio.run(Lazy_start())
    except KeyboardInterrupt:
        logging.info('Service Stopped Bye 👋')
