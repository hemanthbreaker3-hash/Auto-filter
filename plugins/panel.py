from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import ADMINS, CHANNELS, AUTH_CHANNEL, LOG_CHANNEL, REQST_CHANNEL, INDEX_REQ_CHANNEL
from database.users_chats_db import db
from database.ia_filterdb import col, sec_col

BRAND = "TGBOXOFFICE"

def _is_admin(user_id):
    return bool(user_id and user_id in ADMINS)

async def _panel_text():
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    channels = await db.get_managed_channels()
    try:
        files = col.count_documents({})
        if sec_col is not col:
            files += sec_col.count_documents({}) if sec_col.name != col.name or sec_col.database.name != col.database.name else 0
    except Exception:
        files = 0
    channel_lines = "\n".join(f"• <code>{cid}</code>" for cid in channels) or "• <i>No file channels configured</i>"
    return (
        f"<b>✦ {BRAND} CONTROL PANEL</b>\n"
        f"<i>Bot overview • channel management</i>\n\n"
        f"<b>📊 Total information</b>\n"
        f"• Users: <code>{users:,}</code>\n"
        f"• Groups: <code>{chats:,}</code>\n"
        f"• Indexed files: <code>{files:,}</code>\n"
        f"• File channels: <code>{len(channels)}</code>\n\n"
        f"<b>📡 Channel configuration</b>\n"
        f"• File-index: <code>{len(channels)}</code> channel(s)\n"
        f"• Force-subscribe: <code>{AUTH_CHANNEL or 'Not set'}</code>\n"
        f"• Log channel: <code>{LOG_CHANNEL or 'Not set'}</code>\n"
        f"• Request channel: <code>{REQST_CHANNEL or 'Not set'}</code>\n"
        f"• Index-request channel: <code>{INDEX_REQ_CHANNEL or 'Not set'}</code>\n\n"
        f"<b>Managed file channels</b>\n{channel_lines}\n\n"
        f"<i>Commands:</i>\n"
        f"<code>/panel add -100123456789</code> — add channel\n"
        f"<code>/panel remove -100123456789</code> — remove panel-added channel\n"
        f"\n<i>Environment-configured channels cannot be removed here.</i>"
    )

@Client.on_message(filters.command("panel") & filters.private)
async def panel(client, message):
    if not _is_admin(message.from_user.id if message.from_user else None):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    args = message.command[1:]
    if args:
        if len(args) != 2 or args[0].lower() not in {"add", "remove"}:
            return await message.reply_text("<b>Usage:</b> <code>/panel add -100123456789</code> or <code>/panel remove -100123456789</code>")
        try:
            channel_id = int(args[1])
            if channel_id >= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("Send a valid Telegram channel ID, usually starting with <code>-100</code>.")
        if args[0].lower() == "add":
            await db.add_managed_channel(channel_id)
            await message.reply_text(f"<b>✅ Channel added:</b> <code>{channel_id}</code>\nMake sure the bot is an administrator there.")
        else:
            removed = await db.remove_managed_channel(channel_id)
            if removed:
                await message.reply_text(f"<b>✅ Channel removed:</b> <code>{channel_id}</code>")
            else:
                await message.reply_text("<b>⚠️ This channel is set in deployment environment variables and cannot be removed from the panel.</b>")
        return
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="tgbox_panel_refresh")]])
    await message.reply_text(await _panel_text(), reply_markup=keyboard, disable_web_page_preview=True)

@Client.on_callback_query(filters.regex(r"^tgbox_panel_refresh$"))
async def panel_refresh(client, query):
    if not _is_admin(query.from_user.id):
        return await query.answer("Admin access only.", show_alert=True)
    await query.message.edit_text(
        await _panel_text(),
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔄 Refresh", callback_data="tgbox_panel_refresh")]]),
        disable_web_page_preview=True
    )
    await query.answer("Updated")
