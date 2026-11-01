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
    stream_enabled = bool(await db.get_link_feature("stream_enabled"))
    download_enabled = bool(await db.get_link_feature("download_enabled"))

    # /stream must be blocked whenever streaming is disabled.
    if not STREAM_MODE or not stream_enabled:
        disabled = (
            "⚠️ **Stream and download links are currently disabled by the admin.**"
            if not stream_enabled and not download_enabled
            else "⚠️ **Stream links are currently disabled by the admin.**"
        )
        return await message.reply_text(disabled)

    msg = await client.ask(message.chat.id, "**Now send me your file/video to get the available link(s)**")
    if not msg.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
        return await message.reply("**Please send me supported media.**")
    if msg.media in [enums.MessageMediaType.VIDEO, enums.MessageMediaType.DOCUMENT]:
        file = getattr(msg, msg.media.value)
        filename = file.file_name
        filesize = humanize.naturalsize(file.file_size) 
        fileid = file.file_id
        user_id = message.from_user.id
        username =  message.from_user.mention 

        # Recheck the switches immediately before creating/sending any links.
        stream_enabled = bool(await db.get_link_feature("stream_enabled"))
        download_enabled = bool(await db.get_link_feature("download_enabled"))
        if not stream_enabled and not download_enabled:
            return await message.reply_text(
                "⚠️ **Stream and download links are currently disabled by the admin.**"
            )
        if not stream_enabled:
            return await message.reply_text(
                "⚠️ **Stream links are currently disabled by the admin.**"
            )

        log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=fileid)
        filename = get_name(log_msg)
        stream = f"{URL}watch/{log_msg.id}/{quote_plus(filename)}?hash={get_hash(log_msg)}"
        download = f"{URL}{log_msg.id}/{quote_plus(filename)}?hash={get_hash(log_msg)}"

        buttons = []
        if download_enabled:
            buttons.append(InlineKeyboardButton("🚀 Fast Download 🚀", url=download))
        if stream_enabled:
            buttons.append(InlineKeyboardButton("🖥️ Watch online 🖥️", url=stream))

        markup = InlineKeyboardMarkup([buttons]) if buttons else None
        await log_msg.reply_text(
            text=(
                f"•• ʟɪɴᴋ ɢᴇɴᴇʀᴀᴛᴇᴅ ꜰᴏʀ ɪᴅ #{user_id}\\n"
                f"•• ᴜꜱᴇʀɴᴀᴍᴇ : {username}\\n\\n"
                f"•• ᖴᎥᒪᗴ Nᗩᗰᗴ : {filename}"
            ),
            quote=True,
            disable_web_page_preview=True,
            reply_markup=markup,
        )

        details = [
            "<i><u>𝗬𝗼𝘂𝗿 𝗟𝗶𝗻𝗸 𝗚𝗲𝗻𝗲𝗿𝗮𝘁𝗲𝗱 !</u></i>",
            f"<b>📂 Fɪʟᴇ ɴᴀᴍᴇ :</b> <i>{filename}</i>",
            f"<b>📦 Fɪʟᴇ ꜱɪᴢᴇ :</b> <i>{humanbytes(get_media_file_size(msg))}</i>",
        ]
        if download_enabled:
            details.append(f"<b>📥 Dᴏᴡɴʟᴏᴀᴅ :</b> <i>{download}</i>")
        if stream_enabled:
            details.append(f"<b>🖥 Wᴀᴛᴄʜ :</b> <i>{stream}</i>")
        details.append("<b>🚸 Nᴏᴛᴇ : ʟɪɴᴋ ᴡᴏɴ'ᴛ ᴇxᴘɪʀᴇ ᴛɪʟʟ ɪ ᴅᴇʟᴇᴛᴇ</b>")

        await message.reply_text(
            text="\\n\\n".join(details),
            quote=True,
            disable_web_page_preview=True,
            reply_markup=markup,
        )
