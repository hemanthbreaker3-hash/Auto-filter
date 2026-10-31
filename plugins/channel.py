import logging
from pyrogram import Client, filters
from database.users_chats_db import db
from database.ia_filterdb import save_file

media_filter = filters.document | filters.video

@Client.on_message(filters.channel & media_filter, group=10)
async def media(bot, message):
    try:
        allowed_channels = await db.get_managed_channels()
        if message.chat.id not in allowed_channels:
            return
        media_obj = getattr(message, message.media.value, None)
        if not media_obj:
            return
        media_obj.caption = message.caption
        await save_file(media_obj)
    except Exception:
        logging.exception("TGBOXOFFICE channel indexing failed")
