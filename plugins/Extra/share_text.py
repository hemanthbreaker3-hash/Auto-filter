# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import os
from pyrogram import Client, filters
from urllib.parse import quote
from info import CHNL_LNK
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from TechVJ.util.telegram_rich import ButtonStyle

@Client.on_message(filters.command(["share_text", "share", "sharetext"]))
async def share_text(client, message):
    vj = await client.ask(chat_id = message.from_user.id, text = "Now Send me your text.")
    if vj and (vj.text or vj.caption):
        input_text = vj.text or vj.caption
    else:
        await vj.reply_text(
            text=f"**Notice:**\n\n1. Send Any Text Messages.\n2. No Media Support\n\n**Join Update Channel**",               
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Updates Channel", url=CHNL_LNK, style=ButtonStyle.PRIMARY)]])
            )                                                   
        return
    await vj.reply_text(
        text=f"**Here is Your Sharing Text 👇**\n\nhttps://t.me/share/url?url=" + quote(input_text),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("♂️ Share", url=f"https://t.me/share/url?url={quote(input_text)}", style=ButtonStyle.PRIMARY)]])       
    )
