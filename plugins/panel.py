"""Owner/admin control panel for managing source channels and bot admins."""
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from info import OWNER_ID, ADMINS, CHANNELS
from database.users_chats_db import db

LOG = logging.getLogger(__name__)


def _uid(message):
    return message.from_user.id if message.from_user else 0


async def _is_manager(user_id):
    if not user_id:
        return False
    managed = await db.get_managed_items("managed_admins")
    blocked = await db.get_managed_items("blocked_admins")
    return user_id == OWNER_ID or (user_id not in blocked and (user_id in ADMINS or user_id in managed))


def _menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📢 Channels", callback_data="panel:channels"),
         InlineKeyboardButton("👮 Admins", callback_data="panel:admins")],
        [InlineKeyboardButton("➕ Add channel", callback_data="panel:help_channel"),
         InlineKeyboardButton("➕ Add admin", callback_data="panel:help_admin")],
        [InlineKeyboardButton("❌ Close", callback_data="panel:close")]
    ])


@Client.on_message(filters.private & filters.command("panel"))
async def panel_home(client, message):
    if not await _is_manager(_uid(message)):
        return await message.reply_text("⛔ This panel is restricted to the bot owner and authorized admins.")
    parts = (message.text or "").split()
    if len(parts) == 3:
        action, raw_id = parts[1].lower(), parts[2]
        if action not in {"addchannel", "delchannel", "addadmin", "deladmin"}:
            return await message.reply_text("Unknown action. Open /panel for help.")
        try:
            target = int(raw_id)
            if target == 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("❌ ID must be a valid non-zero numeric Telegram ID.")
        if action.endswith("admin"):
            if target == OWNER_ID:
                return await message.reply_text("🔒 The configured owner cannot be changed here.")
            key = "managed_admins"
            if action == "addadmin":
                await db.remove_managed_item("blocked_admins", target)
                await db.add_managed_item(key, target)
                return await message.reply_text(f"✅ Admin <code>{target}</code> added.")
            await db.remove_managed_item(key, target)
            await db.add_managed_item("blocked_admins", target)
            return await message.reply_text(f"✅ Admin <code>{target}</code> removed from panel access.")
        key = "managed_channels"
        if action == "addchannel":
            await db.remove_managed_item("blocked_channels", target)
            await db.add_managed_item(key, target)
            return await message.reply_text(f"✅ Channel <code>{target}</code> added. Make sure the bot is an administrator there.")
        await db.remove_managed_item(key, target)
        await db.add_managed_item("blocked_channels", target)
        return await message.reply_text(f"✅ Channel <code>{target}</code> removed from source channels.")

    await message.reply_text(
        "<b>⚙️ BOT MANAGEMENT PANEL</b>\n\n"
        "Manage source channels and trusted bot admins. Changes are saved in MongoDB.\n\n"
        "<code>/panel addchannel -1001234567890</code>\n"
        "<code>/panel delchannel -1001234567890</code>\n"
        "<code>/panel addadmin 123456789</code>\n"
        "<code>/panel deladmin 123456789</code>",
        reply_markup=_menu()
    )


@Client.on_callback_query(filters.regex(r"^panel:"))
async def panel_callbacks(client, query):
    if not await _is_manager(query.from_user.id):
        return await query.answer("Not authorized", show_alert=True)
    action = query.data.split(":", 1)[1]
    if action == "close":
        return await query.message.delete()
    if action == "home":
        await query.message.edit_text("<b>⚙️ BOT MANAGEMENT PANEL</b>", reply_markup=_menu())
        return await query.answer()
    if action == "help_channel":
        return await query.answer("Use /panel addchannel -1001234567890", show_alert=True)
    if action == "help_admin":
        return await query.answer("Use /panel addadmin 123456789", show_alert=True)
    if action.startswith("rmc:") or action.startswith("rma:"):
        kind, raw_target = action.split(":", 1)
        try:
            target = int(raw_target)
        except ValueError:
            return await query.answer("Invalid target ID", show_alert=True)
        if kind == "rma":
            if target == OWNER_ID:
                return await query.answer("The owner cannot be removed", show_alert=True)
            await db.remove_managed_item("managed_admins", target)
            await db.add_managed_item("blocked_admins", target)
            return await query.message.edit_text(f"✅ Admin <code>{target}</code> removed from panel access.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="panel:admins")], [InlineKeyboardButton("🏠 Panel", callback_data="panel:home")]]))
        await db.remove_managed_item("managed_channels", target)
        await db.add_managed_item("blocked_channels", target)
        return await query.message.edit_text(f"✅ Channel <code>{target}</code> removed from source channels.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("↩️ Back", callback_data="panel:channels")], [InlineKeyboardButton("🏠 Panel", callback_data="panel:home")]]))
    if action == "channels":
        configured = list(CHANNELS)
        managed = await db.get_managed_items("managed_channels")
        blocked = await db.get_managed_items("blocked_channels")
        all_channels = [x for x in dict.fromkeys(configured + managed) if x not in blocked]
        body = "<b>📢 SOURCE CHANNELS</b>\n\n" + ("\n".join(f"• <code>{x}</code>" for x in all_channels) if all_channels else "No channels configured.") + "\n\nUse /panel addchannel ID to add a channel."
    elif action == "admins":
        managed = await db.get_managed_items("managed_admins")
        blocked = await db.get_managed_items("blocked_admins")
        all_admins = [x for x in dict.fromkeys(list(ADMINS) + managed + ([OWNER_ID] if OWNER_ID else [])) if x == OWNER_ID or x not in blocked]
        body = "<b>👮 AUTHORIZED ADMINS</b>\n\n" + ("\n".join(f"• <code>{x}</code>" for x in all_admins) if all_admins else "No admins configured.") + "\n\nUse /panel addadmin ID to add an admin."
    else:
        return await query.answer("Unknown panel action.", show_alert=True)
    buttons = []
    if action == "channels":
        buttons.extend([[InlineKeyboardButton(f"🗑 Remove {target}", callback_data=f"panel:rmc:{target}")] for target in all_channels[:15]])
    else:
        buttons.extend([[InlineKeyboardButton(f"🗑 Remove {target}", callback_data=f"panel:rma:{target}")] for target in all_admins[:15] if target != OWNER_ID])
    buttons.append([InlineKeyboardButton("↩️ Back", callback_data="panel:home")])
    await query.message.edit_text(body, reply_markup=InlineKeyboardMarkup(buttons))
    await query.answer()
