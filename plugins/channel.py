import logging
from pyrogram import Client, filters, enums
import info
from database.users_chats_db import db, normalize_channel_id
from database.ia_filterdb import save_file
from TechVJ.util.auto_post import process_caption_for_auto_post

logger = logging.getLogger(__name__)
media_filter = filters.document | filters.video | filters.audio | filters.animation


def _extract_media(message):
    if not message:
        return None
    if getattr(message, "media", None) and hasattr(message.media, "value"):
        media_obj = getattr(message, message.media.value, None)
        if media_obj and getattr(media_obj, "file_id", None):
            return media_obj
    for attr in ("document", "video", "audio", "animation"):
        media_obj = getattr(message, attr, None)
        if media_obj and getattr(media_obj, "file_id", None):
            return media_obj
    return None


async def _auto_index_incoming(bot, message):
    try:
        if not message or not message.chat:
            return
        media_obj = _extract_media(message)
        if not media_obj:
            return
        if not await db.auto_index_enabled():
            return
        chat_id = int(message.chat.id)
        norm_id = normalize_channel_id(chat_id)
        post_channel_id = await db.get_auto_post_channel()
        excluded_ids = {
            normalize_channel_id(x) or x
            for x in [
                getattr(info, "LOG_CHANNEL", None),
                getattr(info, "AUTH_CHANNEL", None),
                getattr(info, "REQST_CHANNEL", None),
                getattr(info, "SUPPORT_CHAT_ID", None),
                post_channel_id,
                *(getattr(info, "DELETE_CHANNELS", []) or []),
            ]
            if x
        }
        if chat_id in excluded_ids or (norm_id is not None and norm_id in excluded_ids):
            return

        allowed_channels = set(await db.get_managed_channels())
        if allowed_channels:
            if chat_id not in allowed_channels and (norm_id is None or norm_id not in allowed_channels):
                if message.chat.type == enums.ChatType.CHANNEL:
                    doc = await db.get_file_channels_doc()
                    removed = {normalize_channel_id(x) for x in (doc.get("removed_channels", []) if doc else [])}
                    if norm_id in removed or chat_id in removed:
                        return
                else:
                    return

        media_obj.caption = message.caption
        saved, status = await save_file(media_obj)
        if saved:
            logger.info("MoviesZoneFlix auto-indexed file from channel %s (msg %s)", chat_id, message.id)
        # Check caption and file_name for movie/series name, season, episode, quality, and languages
        raw_caption = str(message.caption) if message.caption else None
        raw_file_name = getattr(media_obj, "file_name", None)
        if raw_caption or raw_file_name:
            await process_caption_for_auto_post(
                bot,
                caption=raw_caption,
                source_chat_id=chat_id,
                file_name=raw_file_name,
            )
    except Exception:
        logging.exception("MoviesZoneFlix channel auto-indexing failed")


@Client.on_message((filters.channel | filters.group) & media_filter, group=-2)
async def media(bot, message):
    await _auto_index_incoming(bot, message)


@Client.on_edited_message((filters.channel | filters.group) & media_filter, group=-2)
async def edited_media(bot, message):
    await _auto_index_incoming(bot, message)
