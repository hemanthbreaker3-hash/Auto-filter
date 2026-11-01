# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply, CallbackQuery
from info import STREAM_MODE, URL, LOG_CHANNEL
from database.users_chats_db import db
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_hash, get_media_file_size
from TechVJ.util.human_readable import humanbytes
import humanize
import random

@Client.on_message(filters.private & filters.command("stream"))
async def stream_start(client, message):
    stream_enabled = await db.get_link_feature("stream_enabled")
    download_enabled = await db.get_link_feature("download_enabled")
    if not stream_enabled and not download_enabled:
        return await message.reply_text("⚠️ <b>Stream and download are currently disabled by the admin.</b>")
    if not stream_enabled and download_enabled:
        pass
    msg = await client.ask(message.chat.id, "**Now send me your file/video to get stream and download link**")
    if not msg.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("**Please send me supported media.**")
    if msg.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
        file = getattr(msg, msg.media.value)
        filename = file.file_name
        filesize = humanize.naturalsize(file.file_size) 
        fileid = file.file_id
        user_id = message.from_user.id
        username =  message.from_user.mention 

        log_msg = await client.send_cached_media(
            chat_id=LOG_CHANNEL,
            file_id=fileid,
        )
        fileName = {quote_plus(get_name(log_msg))}
        stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
        download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
 
        link_buttons = []
        if download_enabled:
            link_buttons.append(InlineKeyboardButton("🚀 Fast Download 🚀", url=download))
        if stream_enabled:
            link_buttons.append(InlineKeyboardButton("🖥️ Watch online 🖥️", url=stream))
        await log_msg.reply_text(
            text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \\n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \\n\\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {fileName}",
            quote=True, disable_web_page_preview=True,
            reply_markup=InlineKeyboardMarkup([link_buttons]) if link_buttons else None
        )
        rm = InlineKeyboardMarkup([link_buttons]) if link_buttons else None
        details = [
            f"<b>📂 File name:</b> <i>{get_name(log_msg)}</i>",
            f"<b>📦 File size:</b> <i>{humanbytes(get_media_file_size(msg))}</i>",
        ]
        if download_enabled:
            details.append(f'<b>📥 Download:</b> <a href="{download}">Open download</a>')
        if stream_enabled:
            details.append(f'<b>🖥 Stream:</b> <a href="{stream}">Watch online</a>')
        details.append("<b>🚸 Links remain available until the stored message is deleted.</b>")
        await message.reply_text(
            "<i><u>Your link is generated!</u></i>\\n\\n" + "\\n\\n".join(details),
            quote=True, disable_web_page_preview=True, reply_markup=rm
        )
