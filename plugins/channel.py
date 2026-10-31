from pyrogram import Client, filters
from info import CHANNELS
from database.users_chats_db import db
from database.ia_filterdb import save_file

media_filter = filters.document | filters.video | filters.audio


@Client.on_message(filters.channel & media_filter)
async def media(bot, message):
    """Save media only from configured or panel-managed channels."""
    managed_channels = await db.get_managed_items("managed_channels")
    blocked_channels = await db.get_managed_items("blocked_channels")
    blocked = set(blocked_channels)
    configured_usernames = {str(channel).lstrip("@").lower() for channel in CHANNELS if isinstance(channel, str) and not channel.lstrip("-").isdigit()}
    allowed_ids = (set(channel for channel in CHANNELS if isinstance(channel, int)) | set(managed_channels)) - blocked
    username = (message.chat.username or "").lower()
    if message.chat.id not in allowed_ids and (not username or username not in configured_usernames):
        return
    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return

    media.file_type = file_type
    media.caption = message.caption
    await save_file(media)
