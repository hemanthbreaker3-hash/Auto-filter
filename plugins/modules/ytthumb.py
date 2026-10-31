import os
import time
import warnings

# ytthumb 2.0.0 uses warnings.deprecated, which was added in Python 3.13.
# Render currently runs this project on Python 3.12, so provide a no-op
# compatibility decorator before importing ytthumb. This only suppresses the
# package's deprecation annotation; it does not change thumbnail behavior.
if not hasattr(warnings, "deprecated"):
    def _compat_deprecated(message=None, *, category=DeprecationWarning, stacklevel=1):
        def decorate(obj):
            return obj
        return decorate
    warnings.deprecated = _compat_deprecated

import ytthumb
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


@Client.on_message(filters.command(["ytthumb"]))
async def send_thumbnail(bot, update):
    message = await update.reply_text(
        text="𝙂𝙚𝙣𝙚𝙧𝙖𝙩𝙞𝙣𝙜 𝙏𝙝𝙪𝙢𝙗𝙣𝙖𝙞𝙡 ...",
        disable_web_page_preview=True,
        quote=True
    )
    try:
        if " | " in update.text:
            video = update.text.split(" | ", -1)[0]
            quality = update.text.split(" | ", -1)[1]
        else:
            video = update.text
            quality = "sd"
        thumbnail = ytthumb.thumbnail(
            video=video,
            quality=quality
        )
        await update.reply_photo(
            photo=thumbnail,
            quote=True
        )
        await message.delete()
    except Exception as error:
        await message.edit_text(
            text="𝗜𝗻𝗰𝗼𝗺𝗽𝗹𝗲𝘁𝗲 𝗖𝗼𝗺𝗺𝗮𝗻𝗱  🤪\n\n➥  𝐆𝐢𝐯𝐞 𝐦𝐞 𝐘𝐓 𝐯𝐢𝐝𝐞𝐨 𝐥𝐢𝐧𝐤 𝐰𝐢𝐭𝐡 𝐭𝐡𝐞 𝐜𝐨𝐦𝐦𝐚𝐧𝐝 !\n\n♻️  𝗘𝘅𝗮𝗺𝗽𝗹𝗲:\n\n`/ytthumb https://youtu.be/9-YmVW4HBPU`",
            disable_web_page_preview=True
        )
