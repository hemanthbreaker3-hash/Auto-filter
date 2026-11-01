import logging
from pyrogram import Client, filters
from database.users_chats_db import db, normalize_channel_id
from database.ia_filterdb import save_file

logger = logging.getLogger(__name__)
media_filter = filters.document | filters.video | filters.audio


async def _auto_index_incoming(bot, message):
    try:
        if not message or not message.chat or not message.media:
            return
        if not await db.auto_index_enabled():
            return
        allowed_channels = set(await db.get_managed_channels())
        chat_id = int(message.chat.id)
        norm_id = normalize_channel_id(chat_id)
        if chat_id not in allowed_channels and (norm_id is None or norm_id not in allowed_channels):
            return
        media_obj = getattr(message, message.media.value, None)
        if not media_obj or not getattr(media_obj, "file_id", None):
            return
        media_obj.caption = message.caption
        saved, status = await save_file(media_obj)
        if saved:
            logger.info("Auto-indexed file from channel %s (msg %s)", chat_id, message.id)
    except Exception:
        logging.exception("TGBOXOFFICE channel auto-indexing failed")


@Client.on_message((filters.channel | filters.group) & media_filter, group=-2)
async def media(bot, message):
    await _auto_index_incoming(bot, message)


@Client.on_edited_message((filters.channel | filters.group) & media_filter, group=-2)
async def edited_media(bot, message):
    await _auto_index_incoming(bot, message)
