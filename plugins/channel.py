import logging
import asyncio
from pyrogram import Client, filters, enums
import info
from database.users_chats_db import db, normalize_channel_id
from database.ia_filterdb import save_file, delete_files_by_source_message
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
        try:
            saved, status = await save_file(media_obj, source_chat_id=chat_id, source_message_id=message.id)
            if saved:
                logger.info("MoviesZoneFlix auto-indexed file from channel %s (msg %s)", chat_id, message.id)
        except Exception:
            # Auto-posting must still run even if the search-index write fails.
            logger.exception("File search indexing failed for %s/%s; continuing to /auto processing", chat_id, message.id)
        # Process caption and filename independently from the search-index write.
        raw_caption = str(message.caption) if message.caption else None
        raw_file_name = getattr(media_obj, "file_name", None)
        if raw_caption or raw_file_name:
            result = await process_caption_for_auto_post(
                bot,
                caption=raw_caption,
                source_chat_id=chat_id,
                file_name=raw_file_name,
            )
            if result and result.get("posted"):
                logger.info("/auto destination post completed for source %s/%s", chat_id, message.id)
    except Exception:
        logging.exception("MoviesZoneFlix channel auto-indexing failed")


@Client.on_message((filters.channel | filters.group) & media_filter, group=-2)
async def media(bot, message):
    await _auto_index_incoming(bot, message)


@Client.on_edited_message((filters.channel | filters.group) & media_filter, group=-2)
async def edited_media(bot, message):
    await _auto_index_incoming(bot, message)


@Client.on_deleted_messages()
async def cleanup_deleted_index_entries(bot, messages):
    """Purge files from search indexes when their source Telegram messages are deleted."""
    for message in messages or []:
        try:
            chat = getattr(message, "chat", None)
            chat_id = getattr(chat, "id", None)
            message_id = getattr(message, "id", None)
            if chat_id is None or message_id is None:
                continue
            removed = await asyncio.to_thread(
                delete_files_by_source_message, int(chat_id), int(message_id)
            )
            if removed:
                logger.info(
                    "Removed %s indexed file record(s) for deleted source message %s/%s",
                    removed, chat_id, message_id
                )
        except Exception:
            logger.exception("Deleted-message index cleanup failed")
