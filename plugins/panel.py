"""Interactive TGBOXOFFICE administration panel."""
from html import escape

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from info import CHANNELS, AUTH_CHANNEL, LOG_CHANNEL, REQST_CHANNEL, INDEX_REQ_CHANNEL
from pyrogram.enums import ChatMemberStatus, ChatType
from database.users_chats_db import db
from database.ia_filterdb import col, sec_col, count_all_file_documents
from database.mongo_nodes import list_nodes, add_node, set_node_enabled, remove_node, mask_uri

BRAND = "TGBOXOFFICE"
PREFIX = "tgbox_panel"


def _is_admin(user_id):
    return bool(user_id and int(user_id) in info.ADMINS)


def _is_owner(user_id):
    return bool(user_id and int(user_id) in info.OWNER_ADMINS)


def _keyboard(page="home"):
    if page == "fsub":
        rows = [
            [InlineKeyboardButton("➕ Add FSub", callback_data=f"{PREFIX}:fsub_help_add"),
             InlineKeyboardButton("➖ Remove FSub", callback_data=f"{PREFIX}:fsub_help_remove")],
            [InlineKeyboardButton("📋 List destinations", callback_data=f"{PREFIX}:fsub")],
            [InlineKeyboardButton("⬅️ Dashboard", callback_data=f"{PREFIX}:home"),
             InlineKeyboardButton("🔄 Refresh", callback_data=f"{PREFIX}:refresh")],
        ]
    elif page == "mongo":
        rows = []
        for node in list_nodes()[:15]:
            action = "disable" if node.get("enabled", True) else "enable"
            label = "⏸ Disable" if action == "disable" else "▶️ Enable"
            rows.append([InlineKeyboardButton(f"{label} Mongo #{node['_id']}", callback_data=f"{PREFIX}:mongo_{action}_{node['_id']}")])
        rows.extend([
            [InlineKeyboardButton("➕ Add MongoDB", callback_data=f"{PREFIX}:mongo_help_add"),
             InlineKeyboardButton("📋 Refresh list", callback_data=f"{PREFIX}:mongo")],
            [InlineKeyboardButton("⬅️ Dashboard", callback_data=f"{PREFIX}:home")],
        ])
    elif page == "links":
        rows = [
            [InlineKeyboardButton("⏯ Toggle Stream", callback_data=f"{PREFIX}:link_toggle_stream")],
            [InlineKeyboardButton("⏯ Toggle Download", callback_data=f"{PREFIX}:link_toggle_download")],
            [InlineKeyboardButton("⬅️ Dashboard", callback_data=f"{PREFIX}:home"), InlineKeyboardButton("🔄 Refresh", callback_data=f"{PREFIX}:links")],
        ]
    elif page == "admins":
        rows = [
            [InlineKeyboardButton("➕ Add admin", callback_data=f"{PREFIX}:help_add"),
             InlineKeyboardButton("➖ Remove admin", callback_data=f"{PREFIX}:help_remove")],
            [InlineKeyboardButton("👥 List admins", callback_data=f"{PREFIX}:admins")],
            [InlineKeyboardButton("⬅️ Dashboard", callback_data=f"{PREFIX}:home"),
             InlineKeyboardButton("🔄 Refresh", callback_data=f"{PREFIX}:refresh")],
        ]
    else:
        rows = [
            [InlineKeyboardButton("👥 Admins", callback_data=f"{PREFIX}:admins"),
             InlineKeyboardButton("📡 Channels", callback_data=f"{PREFIX}:channels")],
            [InlineKeyboardButton("📊 Statistics", callback_data=f"{PREFIX}:stats"),
             InlineKeyboardButton("💾 Backup help", callback_data=f"{PREFIX}:backup")],
            [InlineKeyboardButton("🔒 Force Subscribe", callback_data=f"{PREFIX}:fsub")],
            [InlineKeyboardButton("🗄 MongoDB Manager", callback_data=f"{PREFIX}:mongo")],
            [InlineKeyboardButton("🔗 Stream / Download", callback_data=f"{PREFIX}:links")],
            [InlineKeyboardButton("🔄 Refresh", callback_data=f"{PREFIX}:refresh")],
        ]
    return InlineKeyboardMarkup(rows)


def _button_rows(page="home"):
    if page == "fsub":
        return [
            [{"text": "➕ Add FSub", "callback_data": f"{PREFIX}:fsub_help_add", "style": "success"},
             {"text": "➖ Remove FSub", "callback_data": f"{PREFIX}:fsub_help_remove", "style": "danger"}],
            [{"text": "📋 List destinations", "callback_data": f"{PREFIX}:fsub", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:refresh"}],
        ]
    if page == "mongo":
        rows = []
        for node in list_nodes()[:15]:
            action = "disable" if node.get("enabled", True) else "enable"
            label = "⏸ Disable" if action == "disable" else "▶️ Enable"
            rows.append([{"text": f"{label} Mongo #{node['_id']}", "callback_data": f"{PREFIX}:mongo_{action}_{node['_id']}", "style": "danger" if action == "disable" else "success"}])
        rows.extend([
            [{"text": "➕ Add MongoDB", "callback_data": f"{PREFIX}:mongo_help_add", "style": "success"},
             {"text": "📋 Refresh list", "callback_data": f"{PREFIX}:mongo", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home"}],
        ])
        return rows
    if page == "links":
        return [
            [{"text": "⏯ Toggle Stream", "callback_data": f"{PREFIX}:link_toggle_stream", "style": "primary"}],
            [{"text": "⏯ Toggle Download", "callback_data": f"{PREFIX}:link_toggle_download", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home"}, {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:links"}],
        ]
    if page == "admins":
        return [
            [{"text": "➕ Add admin", "callback_data": f"{PREFIX}:help_add", "style": "success"},
             {"text": "➖ Remove admin", "callback_data": f"{PREFIX}:help_remove", "style": "danger"}],
            [{"text": "👥 List admins", "callback_data": f"{PREFIX}:admins", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:refresh"}],
        ]
    return [
        [{"text": "👥 Admins", "callback_data": f"{PREFIX}:admins", "style": "primary"},
         {"text": "📡 Channels", "callback_data": f"{PREFIX}:channels", "style": "primary"}],
        [{"text": "📊 Statistics", "callback_data": f"{PREFIX}:stats", "style": "success"},
         {"text": "💾 Backup help", "callback_data": f"{PREFIX}:backup"}],
        [{"text": "🔒 Force Subscribe", "callback_data": f"{PREFIX}:fsub", "style": "primary"}],
        [{"text": "🗄 MongoDB Manager", "callback_data": f"{PREFIX}:mongo", "style": "primary"}],
        [{"text": "🔗 Stream / Download", "callback_data": f"{PREFIX}:links", "style": "primary"}],
        [{"text": "🔄 Refresh", "callback_data": f"{PREFIX}:refresh"}],
    ]


async def _send_panel(client, chat_id, text, page="home"):
    # Prefer Telegram's newer Rich Message API; gracefully fall back to the
    # standard Bot API with native primary/success/danger button styles.
    from TechVJ.util.telegram_rich import make_inline_keyboard, send_rich_message, send_styled_message
    markup = make_inline_keyboard(_button_rows(page))
    try:
        return await send_rich_message(client, chat_id, text, reply_markup=markup)
    except Exception:
        try:
            return await send_styled_message(client, chat_id, text, buttons=_button_rows(page))
        except Exception:
            return await client.send_message(chat_id, text, reply_markup=_keyboard(page), disable_web_page_preview=True)


async def _edit_panel(client, query, text, page="home"):
    from TechVJ.util.telegram_rich import api_request, edit_rich_message, make_inline_keyboard
    markup = make_inline_keyboard(_button_rows(page))
    try:
        await edit_rich_message(client, query.message.chat.id, query.message.id, text, reply_markup=markup)
    except Exception:
        try:
            await api_request(client, "editMessageText", {
                "chat_id": query.message.chat.id,
                "message_id": query.message.id,
                "text": text,
                "parse_mode": "HTML",
                "reply_markup": markup,
            })
        except Exception:
            await query.message.edit_text(text, reply_markup=_keyboard(page), disable_web_page_preview=True)


async def _stats():
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    channels = await db.get_managed_channels()
    try:
        files = count_all_file_documents()
    except Exception:
        files = 0
    return users, chats, files, channels


async def _panel_text(page="home", client=None, page_number=1):
    users, chats, files, channels = await _stats()
    if page == "admins":
        admin_lines = "\n".join(f"• <code>{uid}</code>" for uid in sorted(set(info.ADMINS))) or "• No admins configured"
        return (f"<b>👥 {BRAND} • ADMIN MANAGEMENT</b>\n\n"
                f"<b>Current administrators ({len(set(info.ADMINS))})</b>\n{admin_lines}\n\n"
                "<i>Only the deployment owner can manage admins. Environment admins are protected.</i>\n"
                "<code>/panel admin add USER_ID</code>\n<code>/panel admin remove USER_ID</code>")
    if page == "fsub":
        fsub_chats = await db.get_force_subscribe_chats()
        enabled = await db.force_subscribe_enabled()
        destinations = []
        for chat_id in fsub_chats:
            label, kind = str(chat_id), "Chat"
            if client:
                try:
                    chat = await client.get_chat(chat_id)
                    label = escape(chat.title or chat.username or str(chat_id))
                    kind = "Group" if chat.type in (ChatType.GROUP, ChatType.SUPERGROUP) else "Channel"
                except Exception:
                    pass
            destinations.append(f"• <b>{label}</b> — {kind} <code>{chat_id}</code>")
        lines = "\n".join(destinations) or "• No panel-managed destinations configured"
        return (f"<b>🔒 {BRAND} • FORCE SUBSCRIBE</b>\n\n"
                f"Status: <b>{'ENABLED' if enabled else 'DISABLED'}</b>\n"
                f"Legacy environment channel: <code>{AUTH_CHANNEL or 'Not set'}</code>\n"
                f"Panel destinations ({len(fsub_chats)}):\n{lines}\n\n"
                "<code>/panel fsub add -100123456789</code>\n"
                "<code>/panel fsub remove -100123456789</code>\n"
                "<code>/panel fsub on</code> or <code>/panel fsub off</code>\n"
                "<i>Channels and groups both supported. Bot must be an administrator to verify membership.</i>")
    if page == "mongo":
        nodes = list_nodes()
        page_size = 15
        page_number = max(1, int(page_number or 1))
        page_count = max(1, (len(nodes) + page_size - 1) // page_size)
        page_number = min(page_number, page_count)
        visible_nodes = nodes[(page_number - 1) * page_size:page_number * page_size]
        lines = []
        for node in visible_nodes:
            status = "🟢 ENABLED" if node.get("enabled", True) else "⚪ DISABLED"
            try:
                from pymongo import MongoClient
                test = MongoClient(node["uri"], serverSelectionTimeoutMS=2500, connectTimeoutMS=2500)
                try:
                    test.admin.command("ping")
                    state = "ONLINE"
                    count = test[info.DATABASE_NAME][info.COLLECTION_NAME].count_documents({})
                finally:
                    test.close()
            except Exception:
                state, count = "OFFLINE", 0
            lines.append(f"• <b>{escape(node.get('label', 'Mongo'))}</b> — <code>#{escape(str(node['_id']))}</code> {status} / {state} / <code>{count:,}</code> files\n  <code>{escape(mask_uri(node['uri']))}</code>")
        try:
            base_count = col.count_documents({})
            if info.SEC_FILE_DB_URI != info.FILE_DB_URI:
                base_count += sec_col.count_documents({})
        except Exception:
            base_count = 0
        details = "\n".join(lines) or "• No additional MongoDB nodes added yet."
        return (f"<b>🗄 {BRAND} • MONGODB MANAGER</b>\n\n"
                f"Built-in file DB records: <code>{base_count:,}</code>\n"
                f"Additional nodes: <code>{len(nodes)}</code> (unlimited) • Page <code>{page_number}/{page_count}</code>\n\n{details}\n\n"
                "<b>Commands</b>\n<code>/panel mongo add mongodb+srv://USER:PASS@HOST/DB</code>\n"
                "<code>/panel mongo list [PAGE]</code>\n<code>/panel mongo stats</code>\n"
                "<code>/panel mongo enable ID</code> / <code>/panel mongo disable ID</code>\n"
                "<code>/panel mongo remove ID</code>\n\n"
                "<i>New indexed files are balanced across enabled nodes; search, delete, backup and restore include all registered nodes.</i>")
    if page == "links":
        stream = await db.get_link_feature("stream_enabled")
        download = await db.get_link_feature("download_enabled")
        return (f"<b>🔗 {BRAND} • LINK CONTROLS</b>\n\n"
                f"Stream links: <b>{'🟢 ENABLED' if stream else '🔴 DISABLED'}</b>\n"
                f"Download links: <b>{'🟢 ENABLED' if download else '🔴 DISABLED'}</b>\n\n"
                "Use the buttons below to toggle each feature, or run\n"
                "<code>/panel stream on|off</code>\n<code>/panel download on|off</code>\n\n"
                "<i>Disabled links cannot be generated.</i>")
    if page == "channels":
        lines = "\n".join(f"• <code>{escape(str(cid))}</code>" for cid in channels) or "• No file channels configured"
        return (f"<b>📡 {BRAND} • CHANNELS</b>\n\n<b>File-index channels ({len(channels)})</b>\n{lines}\n\n"
                f"Force subscribe: <code>{AUTH_CHANNEL or 'Not set'}</code>\n"
                f"Log: <code>{LOG_CHANNEL or 'Not set'}</code>\n"
                f"Request: <code>{REQST_CHANNEL or 'Not set'}</code>\n"
                f"Index requests: <code>{INDEX_REQ_CHANNEL or 'Not set'}</code>\n\n"
                "<code>/panel add -100123456789</code>\n<code>/panel remove -100123456789</code>")
    if page == "stats":
        return (f"<b>📊 {BRAND} • LIVE STATISTICS</b>\n\n"
                f"👤 Users: <code>{users:,}</code>\n👥 Groups: <code>{chats:,}</code>\n"
                f"📁 Indexed files: <code>{files:,}</code>\n📡 File channels: <code>{len(channels):,}</code>\n"
                f"🛡 Admins: <code>{len(set(info.ADMINS))}</code>")
    if page == "backup":
        return (f"<b>💾 {BRAND} • BACKUP & RESTORE</b>\n\n"
                "<code>/save</code> — open the interactive backup and import menu.\n"
                "💾 Backup sends a compressed <code>.zip</code> database archive.\n"
                "📥 Import asks for a backup ZIP, validates it, then requests confirmation.\n\n"
                "<b>⚠️ Restore replaces matching collections.</b> Keep a fresh backup before restoring.\n"
                "Legacy commands: <code>/add save</code> and <code>/add load confirm</code>.")
    return (f"<b>✦ {BRAND} CONTROL CENTER</b>\n"
            "<i>Premium administration • live bot overview</i>\n\n"
            f"<b>📊 Overview</b>\n👤 Users: <code>{users:,}</code>\n"
            f"👥 Groups: <code>{chats:,}</code>\n📁 Indexed files: <code>{files:,}</code>\n"
            f"📡 File channels: <code>{len(channels):,}</code>\n🛡 Admins: <code>{len(set(info.ADMINS))}</code>\n\n"
            "<i>Select a section below to manage your bot.</i>")


@Client.on_message(filters.command("panel") & filters.private)
async def panel(client, message):
    uid = message.from_user.id if message.from_user else None
    if not _is_admin(uid):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    args = message.command[1:]
    if args and args[0].lower() in {"add", "remove"}:
        if len(args) != 2:
            return await message.reply_text("Usage: <code>/panel add -100123456789</code> or <code>/panel remove -100123456789</code>")
        try:
            channel_id = int(args[1])
            if channel_id >= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("Send a valid negative Telegram channel ID, usually starting with <code>-100</code>.")
        if args[0].lower() == "add":
            await db.add_managed_channel(channel_id)
            return await message.reply_text(f"<b>✅ Channel added:</b> <code>{channel_id}</code>\nEnsure the bot is an administrator there.")
        removed = await db.remove_managed_channel(channel_id)
        return await message.reply_text(f"<b>{'✅ Channel removed' if removed else '⚠️ Cannot remove environment-configured channel'}:</b> <code>{channel_id}</code>")
    if args and args[0].lower() == "fsub":
        if len(args) < 2:
            return await message.reply_text("<code>/panel fsub add CHAT_ID</code>\n<code>/panel fsub remove CHAT_ID</code>\n<code>/panel fsub on</code>\n<code>/panel fsub off</code>")
        action = args[1].lower()
        if action in {"on", "off"} and len(args) == 2:
            await db.set_force_subscribe_enabled(action == "on")
            return await message.reply_text(f"<b>✅ Panel-managed Force Subscribe {action.upper()}.</b>")
        if action == "list":
            return await message.reply_text(await _panel_text("fsub", client))
        if action not in {"add", "remove"} or len(args) != 3:
            return await message.reply_text("Usage: <code>/panel fsub add CHAT_ID</code> or <code>/panel fsub remove CHAT_ID</code>")
        try:
            chat = await client.get_chat(args[2])
        except Exception as exc:
            if action == "remove":
                try:
                    chat_id = int(args[2])
                    await db.remove_force_subscribe_chat(chat_id)
                    return await message.reply_text(f"<b>✅ Removed from panel-managed FSub:</b> <code>{chat_id}</code>")
                except ValueError:
                    pass
            return await message.reply_text(f"<b>Cannot access that chat.</b> Add the bot as an administrator and check the ID/username.\n<code>{escape(str(exc)[:250])}</code>")
        if chat.type not in (ChatType.CHANNEL, ChatType.GROUP, ChatType.SUPERGROUP):
            return await message.reply_text("Only Telegram channels, groups and supergroups can be used for FSub.")
        chat_id = int(chat.id)
        if action == "add":
            try:
                me = await client.get_me()
                member = await client.get_chat_member(chat_id, me.id)
                if member.status not in (ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER):
                    return await message.reply_text("<b>Bot must be an administrator</b> in that channel/group so it can check membership.")
            except Exception as exc:
                return await message.reply_text(f"Could not verify bot permissions: <code>{escape(str(exc)[:200])}</code>")
            await db.add_force_subscribe_chat(chat_id)
            return await message.reply_text(f"<b>✅ Force Subscribe destination added.</b>\n{escape(chat.title)}\n<code>{chat_id}</code>")
        await db.remove_force_subscribe_chat(chat_id)
        return await message.reply_text(f"<b>✅ Removed from panel-managed FSub:</b>\n{escape(chat.title)}\n<code>{chat_id}</code>")
    if args and args[0].lower() in {"stream", "download"}:
        if len(args) != 2 or args[1].lower() not in {"on", "off"}:
            return await message.reply_text(f"Usage: <code>/panel {args[0].lower()} on</code> or <code>/panel {args[0].lower()} off</code>")
        feature = "stream_enabled" if args[0].lower() == "stream" else "download_enabled"
        await db.set_link_feature(feature, args[1].lower() == "on")
        return await message.reply_text(f"<b>✅ {args[0].title()} links {'ENABLED' if args[1].lower() == 'on' else 'DISABLED'}.</b>")
    if args and args[0].lower() == "mongo":
        if len(args) < 2:
            return await message.reply_text("<code>/panel mongo add MONGODB_URI</code>\n<code>/panel mongo list</code>\n<code>/panel mongo stats</code>\n<code>/panel mongo enable ID</code>\n<code>/panel mongo disable ID</code>\n<code>/panel mongo remove ID</code>")
        action = args[1].lower()
        if action == "add":
            if len(args) != 3:
                return await message.reply_text("Send one URI without spaces: <code>/panel mongo add mongodb+srv://USER:PASS@HOST/DB</code>")
            status = await message.reply_text("⏳ Testing MongoDB connection and registering node…")
            try:
                node_id = await __import__('asyncio').to_thread(add_node, args[2])
                return await status.edit_text(f"✅ MongoDB node added and connection verified.\nID: <code>{node_id}</code>\nNew files will be balanced across all enabled databases.")
            except Exception as exc:
                return await status.edit_text(f"❌ Could not add MongoDB: <code>{escape(str(exc)[:500])}</code>")
        if action in {"list", "stats"} and len(args) in {2, 3}:
            try:
                page_number = int(args[2]) if len(args) == 3 else 1
                if page_number < 1:
                    raise ValueError
            except ValueError:
                return await message.reply_text("Page must be a positive number. Example: <code>/panel mongo list 2</code>")
            return await message.reply_text(await _panel_text("mongo", client, page_number))
        if action in {"enable", "disable", "remove"} and len(args) == 3:
            node_id = args[2]
            if action == "remove":
                changed = await __import__('asyncio').to_thread(remove_node, node_id)
                return await message.reply_text("✅ MongoDB node removed from rotation. Existing data is not deleted." if changed else "⚠️ MongoDB node ID not found.")
            changed = await __import__('asyncio').to_thread(set_node_enabled, node_id, action == "enable")
            return await message.reply_text(("✅ Node enabled." if action == "enable" else "✅ Node disabled; its existing data remains searchable and included in backups.") if changed else "⚠️ MongoDB node ID not found.")
        return await message.reply_text("Invalid MongoDB command. Use <code>/panel mongo</code> for help.")
    if args and args[0].lower() == "admin":
        if not _is_owner(uid):
            return await message.reply_text("<b>⛔ Only the deployment owner can manage administrators.</b>")
        if len(args) != 3 or args[1].lower() not in {"add", "remove"}:
            return await message.reply_text("<code>/panel admin add USER_ID</code>\n<code>/panel admin remove USER_ID</code>")
        try:
            target = int(args[2])
            if target <= 0:
                raise ValueError
        except ValueError:
            return await message.reply_text("Send a valid positive Telegram user ID.")
        if args[1].lower() == "add":
            await db.add_admin(target)
            if target not in info.ADMINS:
                info.ADMINS.append(target)
            if target not in info.AUTH_USERS:
                info.AUTH_USERS.append(target)
            return await message.reply_text(f"✅ Admin added: <code>{target}</code>")
        if target in info.OWNER_ADMINS:
            return await message.reply_text("⚠️ The deployment owner cannot be removed.")
        await db.remove_admin(target)
        info.ADMINS[:] = [x for x in info.ADMINS if x != target]
        if target not in info.AUTH_USERS:
            info.AUTH_USERS[:] = [x for x in info.AUTH_USERS if x != target]
        return await message.reply_text(f"✅ Admin removed: <code>{target}</code>")
    await _send_panel(client, message.chat.id, await _panel_text(client=client))


@Client.on_callback_query(filters.regex(r"^tgbox_panel:"))
async def panel_callbacks(client, query):
    if not _is_admin(query.from_user.id):
        return await query.answer("Admin access only.", show_alert=True)
    action = query.data.split(":", 1)[1]
    if action in {"fsub_help_add", "fsub_help_remove"}:
        command = "add" if action == "fsub_help_add" else "remove"
        await query.answer(f"Use /panel fsub {command} CHAT_ID", show_alert=True)
        return
    if action in {"help_add", "help_remove"}:
        if not _is_owner(query.from_user.id):
            return await query.answer("Only deployment owners can manage admins.", show_alert=True)
        command = "add" if action == "help_add" else "remove"
        await query.answer(f"Use /panel admin {command} USER_ID", show_alert=True)
        return
    if action == "mongo_help_add":
        await query.answer("Send /panel mongo add mongodb+srv://USER:PASS@HOST/DB in this private chat", show_alert=True)
        return
    if action in {"link_toggle_stream", "link_toggle_download"}:
        feature = "stream_enabled" if action.endswith("stream") else "download_enabled"
        current = await db.get_link_feature(feature)
        await db.set_link_feature(feature, not current)
        await _edit_panel(client, query, await _panel_text("links", client), "links")
        return await query.answer(f"{'Enabled' if not current else 'Disabled'} successfully.")
    if action.startswith("mongo_enable_") or action.startswith("mongo_disable_"):
        mode, node_id = action.split("_", 2)[1:]
        changed = await __import__('asyncio').to_thread(set_node_enabled, node_id, mode == "enable")
        if not changed:
            return await query.answer("MongoDB node not found.", show_alert=True)
        await _edit_panel(client, query, await _panel_text("mongo", client), "mongo")
        return await query.answer("MongoDB node enabled." if mode == "enable" else "MongoDB node disabled.")
    page = {"refresh": "home"}.get(action, action)
    if page not in {"home", "admins", "channels", "fsub", "stats", "backup", "mongo", "links"}:
        return await query.answer("Unknown panel section.", show_alert=True)
    await _edit_panel(client, query, await _panel_text(page, client), page)
    await query.answer("Updated")
