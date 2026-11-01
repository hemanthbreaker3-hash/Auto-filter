# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from TechVJ.util.telegram_rich import ButtonStyle
from info import STREAM_MODE, URL, LOG_CHANNEL
from database.users_chats_db import db
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_hash, get_media_file_size
from TechVJ.util.human_readable import humanbytes
import humanize


@Client.on_message(filters.command("stream"))
async def stream_start(client, message):
    stream_enabled = await db.get_link_feature("stream_enabled")
    download_enabled = await db.get_link_feature("download_enabled")
    if not STREAM_MODE or (not stream_enabled and not download_enabled):
        return await message.reply_text("⚠️ <b>Stream and download are currently disabled by the admin.</b>")

    if message.chat.type != enums.ChatType.PRIVATE:
        return await message.reply_text("<b>Please use /stream in my private chat (PM).</b>")

    if message.reply_to_message and message.reply_to_message.media in [
        enums.MessageMediaType.VIDEO,
        enums.MessageMediaType.DOCUMENT,
    ]:
        msg = message.reply_to_message
    else:
        prompt_label = (
            "**Now send me your file/video to get stream and download link**"
            if (stream_enabled and download_enabled)
            else (
                "**Now send me your file/video to get stream link (Download is disabled)**"
                if stream_enabled
                else "**Now send me your file/video to get download link (Stream is disabled)**"
            )
        )
        msg = await client.ask(message.chat.id, prompt_label)

    # Re-verify that stream/download was not disabled while waiting for the file
    stream_enabled = await db.get_link_feature("stream_enabled")
    download_enabled = await db.get_link_feature("download_enabled")
    if not STREAM_MODE or (not stream_enabled and not download_enabled):
        return await message.reply_text("⚠️ <b>Stream and download are currently disabled by the admin.</b>")

    if not msg or msg.media not in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("**Please send me supported media (video or document).**")

    file = getattr(msg, msg.media.value)
    fileid = file.file_id
    user_id = message.from_user.id if message.from_user else 0
    username = message.from_user.mention if message.from_user else "User"

    log_msg = await client.send_cached_media(
        chat_id=LOG_CHANNEL,
        file_id=fileid,
    )
    encoded_name = quote_plus(get_name(log_msg))
    stream = f"{URL}watch/{str(log_msg.id)}/{encoded_name}?hash={get_hash(log_msg)}"
    download = f"{URL}{str(log_msg.id)}/{encoded_name}?hash={get_hash(log_msg)}"

    link_buttons = []
    if download_enabled:
        link_buttons.append(InlineKeyboardButton("🚀 Fast Download 🚀", url=download, style=ButtonStyle.SUCCESS))
    if stream_enabled:
        link_buttons.append(InlineKeyboardButton("🖥️ Watch online 🖥️", url=stream, style=ButtonStyle.SUCCESS))

    rm = InlineKeyboardMarkup([link_buttons]) if link_buttons else None
    await log_msg.reply_text(
        text=f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id} \n•• ᴜꜱᴇʀɴᴀᴍᴇ : {username} \n\n•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {get_name(log_msg)}",
        quote=True,
        disable_web_page_preview=True,
        reply_markup=rm,
    )

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
        "<i><u>Your link is generated!</u></i>\n\n" + "\n\n".join(details),
        quote=True,
        disable_web_page_preview=True,
        reply_markup=rm,
    )
