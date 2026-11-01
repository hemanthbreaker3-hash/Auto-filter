# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

from pyrogram import Client, filters
from info import CHNL_LNK

@Client.on_message(filters.private & filters.command(['set_caption', 'del_caption', 'see_caption']))
async def caption_locked_notice(client, message):
    await message.reply_text(
        f"⚠️ <b>Editing file captions is disabled.</b>\n\n"
        f"Every file keeps its original caption with the update channel hyperlink (<a href=\"{CHNL_LNK}\">Update Channel</a>).",
        disable_web_page_preview=True,
    )
