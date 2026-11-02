"""Interactive MoviesZoneFlix administration panel with Shortener Mode Selection & Interactive Wizards."""
import asyncio
import re
from html import escape

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from info import CHANNELS, AUTH_CHANNEL, LOG_CHANNEL, REQST_CHANNEL, INDEX_REQ_CHANNEL
from pyrogram.enums import ChatMemberStatus, ChatType
from database.users_chats_db import db, normalize_channel_id, parse_duration_to_seconds, format_seconds_human
from database.ia_filterdb import col, sec_col, count_all_file_documents
from database.mongo_nodes import list_nodes, add_node, set_node_enabled, remove_node, mask_uri
from TechVJ.util.telegram_rich import ButtonStyle

BRAND = "MoviesZoneFlix"
PREFIX = "tgbox_panel"

_CHANNEL_LINK_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:(c)/)?([A-Za-z0-9_]+|-?\d+)(?:/(\d+))?(?:/(\d+))?/?(?:\?.*)?$",
    re.IGNORECASE,
)

MODE_LABELS = {
    "time": "⏱ Time / Expire Duration Mode",
    "credits": "💳 Credits Mode (Files per Verify)",
    "link": "🔗 Every-File Shortlink Mode",
    "off": "🔴 Disabled (Direct Files)",
}


def _is_admin(user_id):
    try:
        uid = int(user_id)
        admins = {int(value) for value in getattr(info, "ADMINS", [])}
        owners = {int(value) for value in getattr(info, "OWNER_ADMINS", ())}
        return uid in admins or uid in owners
    except (TypeError, ValueError):
        return False


def _is_owner(user_id):
    try:
        uid = int(user_id)
        return uid in {int(value) for value in getattr(info, "OWNER_ADMINS", ())}
    except (TypeError, ValueError):
        return False


def _normalize_shortener_domain(value):
    return str(value or "").strip().lower().removeprefix("https://").removeprefix("http://").strip("/")


async def _resolve_channel_input(client, raw_value):
    """Resolve a channel ID, positive ID, @username, or t.me link into (channel_id, title)."""
    val = (raw_value or "").strip()
    if not val:
        raise ValueError("Empty channel input.")
    m = _CHANNEL_LINK_RE.match(val)
    if m:
        is_c, target, _seg1, _seg2 = m.groups()
        if is_c or target.lstrip("-").isdigit():
            val = str(normalize_channel_id(target) or target)
        else:
            val = "@" + target.lstrip("@")
    norm = normalize_channel_id(val)
    lookup = norm if norm is not None else val
    try:
        chat = await client.get_chat(lookup)
        if chat.type not in (ChatType.CHANNEL, ChatType.SUPERGROUP, ChatType.GROUP):
            raise ValueError("Target must be a Telegram channel or supergroup.")
        return int(chat.id), (chat.title or chat.username or str(chat.id))
    except Exception:
        if norm is not None:
            return int(norm), str(norm)
        raise ValueError("Cannot resolve channel. Send a valid channel ID (e.g. -100123456789), @username, or channel message link.")


def _button_rows(page="home", channels=None, shortener_cfg=None, shortener_items=None):
    if page == "fsub":
        return [
            [{"text": "➕ Add FSub", "callback_data": f"{PREFIX}:fsub_help_add", "style": "success"},
             {"text": "➖ Remove FSub", "callback_data": f"{PREFIX}:fsub_help_remove", "style": "danger"}],
            [{"text": "⏯ Toggle FSub ON/OFF", "callback_data": f"{PREFIX}:fsub_toggle", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:fsub", "style": "primary"}],
        ]
    if page == "channels":
        rows = [
            [{"text": "➕ Add Channel", "callback_data": f"{PREFIX}:chan_add_prompt", "style": "success"},
             {"text": "➖ Remove Channel", "callback_data": f"{PREFIX}:chan_remove_prompt", "style": "danger"}],
            [{"text": "⏯ Toggle Auto-Index", "callback_data": f"{PREFIX}:chan_toggle_auto", "style": "primary"},
             {"text": "🎬 Auto-Post (/auto)", "callback_data": "mzf_auto:menu", "style": "success"}],
        ]
        for cid in (channels or [])[:10]:
            rows.append([
                {"text": f"🗑 Remove {cid}", "callback_data": f"{PREFIX}:chan_del_{cid}", "style": "danger"},
            ])
        rows.extend([
            [{"text": "📁 Open /indexstatus", "callback_data": "idxctl:list:0", "style": "primary"},
             {"text": "➕ Start /index", "callback_data": "idxctl:new:0", "style": "success"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:channels", "style": "primary"}],
        ])
        return rows
    if page == "mongo":
        rows = []
        for node in list_nodes()[:15]:
            action = "disable" if node.get("enabled", True) else "enable"
            label = "⏸ Disable" if action == "disable" else "▶️ Enable"
            rows.append([{"text": f"{label} Mongo #{node['_id']}", "callback_data": f"{PREFIX}:mongo_{action}_{node['_id']}", "style": "danger" if action == "disable" else "success"}])
        rows.extend([
            [{"text": "➕ Add MongoDB", "callback_data": f"{PREFIX}:mongo_help_add", "style": "success"},
             {"text": "📋 Refresh list", "callback_data": f"{PREFIX}:mongo", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"}],
        ])
        return rows
    if page == "shorteners":
        cfg = shortener_cfg or {}
        mode = cfg.get("mode", "time")
        exp_human = cfg.get("expire_human", "24h")
        creds = cfg.get("credits_per_verify", 5)
        return [
            [
                {"text": f"{'✅ ' if mode == 'time' else ''}⏱ Mode: Time ({exp_human})", "callback_data": f"{PREFIX}:smode_time", "style": "success" if mode == "time" else "primary"},
                {"text": f"{'✅ ' if mode == 'credits' else ''}💳 Mode: Credits ({creds})", "callback_data": f"{PREFIX}:smode_credits", "style": "success" if mode == "credits" else "primary"},
            ],
            [
                {"text": f"{'✅ ' if mode == 'link' else ''}🔗 Mode: Every File", "callback_data": f"{PREFIX}:smode_link", "style": "success" if mode == "link" else "primary"},
                {"text": f"{'✅ ' if mode == 'off' else ''}🔴 Mode: Off", "callback_data": f"{PREFIX}:smode_off", "style": "danger" if mode == "off" else "primary"},
            ],
            [
                {"text": f"⏳ Set Expire Time ({exp_human})", "callback_data": f"{PREFIX}:shortener_time_menu", "style": "primary"},
                {"text": f"🎟 Set Credits ({creds})", "callback_data": f"{PREFIX}:shortener_credits_menu", "style": "primary"},
            ],
            [
                {"text": "➕ Add Shortener", "callback_data": f"{PREFIX}:shortener_add", "style": "success"},
                {"text": "🗑 Delete Shortener", "callback_data": f"{PREFIX}:shortener_delete", "style": "danger"},
            ],
            [
                {"text": "🎬 Set Tutorial Link", "callback_data": f"{PREFIX}:shortener_tutorial", "style": "primary"},
                {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:shorteners", "style": "primary"},
            ],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"}],
        ]
    if page == "shortener_time_menu":
        cfg = shortener_cfg or {}
        cur_secs = int(cfg.get("expire_seconds", 86400))
        presets = [
            ("30m", 1800), ("1h", 3600), ("3h", 10800), ("6h", 21600),
            ("12h", 43200), ("24h", 86400), ("2d", 172800), ("7d", 604800),
        ]
        rows = []
        for i in range(0, len(presets), 4):
            row = []
            for label, secs in presets[i:i + 4]:
                active = (cur_secs == secs)
                row.append({
                    "text": f"{'✅ ' if active else ''}{label}",
                    "callback_data": f"{PREFIX}:stime_{secs}",
                    "style": "success" if active else "primary",
                })
            rows.append(row)
        rows.append([{"text": "✏️ Set Custom Duration (e.g. 4h, 45m, 3d)", "callback_data": f"{PREFIX}:stime_custom", "style": "success"}])
        rows.append([{"text": "⬅️ Back to Shortener Manager", "callback_data": f"{PREFIX}:shorteners", "style": "danger"}])
        return rows
    if page == "shortener_credits_menu":
        cfg = shortener_cfg or {}
        cur_creds = int(cfg.get("credits_per_verify", 5))
        presets = [1, 2, 3, 5, 10, 15, 20, 50]
        rows = []
        for i in range(0, len(presets), 4):
            row = []
            for count in presets[i:i + 4]:
                active = (cur_creds == count)
                row.append({
                    "text": f"{'✅ ' if active else ''}{count} Credit{'s' if count > 1 else ''}",
                    "callback_data": f"{PREFIX}:scred_{count}",
                    "style": "success" if active else "primary",
                })
            rows.append(row)
        rows.append([{"text": "✏️ Set Custom Credits Count", "callback_data": f"{PREFIX}:scred_custom", "style": "success"}])
        rows.append([{"text": "⬅️ Back to Shortener Manager", "callback_data": f"{PREFIX}:shorteners", "style": "danger"}])
        return rows
    if page == "shortener_delete_menu":
        items = shortener_items or []
        rows = []
        for idx, item in enumerate(items, 1):
            domain = str(item.get("url", ""))
            rows.append([{
                "text": f"🗑 Delete #{idx} — {domain}",
                "callback_data": f"{PREFIX}:sdel_{idx}",
                "style": "danger",
            }])
        rows.append([{"text": "⬅️ Back to Shortener Manager", "callback_data": f"{PREFIX}:shorteners", "style": "primary"}])
        return rows
    if page == "links":
        return [
            [{"text": "⏯ Toggle Stream", "callback_data": f"{PREFIX}:link_toggle_stream", "style": "primary"},
             {"text": "⏯ Toggle Download", "callback_data": f"{PREFIX}:link_toggle_download", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:links", "style": "primary"}],
        ]
    if page == "admins":
        return [
            [{"text": "➕ Add admin", "callback_data": f"{PREFIX}:help_add", "style": "success"},
             {"text": "➖ Remove admin", "callback_data": f"{PREFIX}:help_remove", "style": "danger"}],
            [{"text": "👥 List admins", "callback_data": f"{PREFIX}:admins", "style": "primary"}],
            [{"text": "⬅️ Dashboard", "callback_data": f"{PREFIX}:home", "style": "danger"},
             {"text": "🔄 Refresh", "callback_data": f"{PREFIX}:refresh", "style": "primary"}],
        ]
    return [
        [{"text": "🔀 Shortener & Mode Manager", "callback_data": f"{PREFIX}:shorteners", "style": "success"}],
        [{"text": "🎬 Auto-Post Manager (/auto)", "callback_data": "mzf_auto:menu", "style": "success"}],
        [{"text": "👥 Admins", "callback_data": f"{PREFIX}:admins", "style": "primary"},
         {"text": "📡 Channels", "callback_data": f"{PREFIX}:channels", "style": "primary"}],
        [{"text": "📊 Statistics", "callback_data": f"{PREFIX}:stats", "style": "success"},
         {"text": "💾 Backup & Restore", "callback_data": f"{PREFIX}:backup", "style": "success"}],
        [{"text": "🔒 Force Subscribe", "callback_data": f"{PREFIX}:fsub", "style": "primary"},
         {"text": "🔗 Stream / Download", "callback_data": f"{PREFIX}:links", "style": "primary"}],
        [{"text": "🗄 MongoDB Manager", "callback_data": f"{PREFIX}:mongo", "style": "primary"},
         {"text": "💎 Plan Manager", "callback_data": f"{PREFIX}:plans", "style": "success"}],
        [{"text": "📁 Index Tasks (/indexstatus)", "callback_data": "idxctl:list:0", "style": "primary"}],
        [{"text": "🔄 Refresh Dashboard", "callback_data": f"{PREFIX}:refresh", "style": "primary"}],
    ]


def _keyboard_from_rows(rows):
    kb = []
    for row in rows:
        kb_row = []
        for btn in row:
            style_str = btn.get("style", "primary")
            st = ButtonStyle.SUCCESS if style_str == "success" else (ButtonStyle.DANGER if style_str == "danger" else ButtonStyle.PRIMARY)
            kb_row.append(InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"], style=st))
        kb.append(kb_row)
    return InlineKeyboardMarkup(kb)


async def _build_page_rows(page="home"):
    channels = await db.get_managed_channels() if page == "channels" else None
    shortener_cfg = await db.get_shortener_config() if page.startswith("shortener") else None
    shortener_items = await db.get_shortener_pool() if page in ("shorteners", "shortener_delete_menu") else None
    return _button_rows(page, channels=channels, shortener_cfg=shortener_cfg, shortener_items=shortener_items)


async def _send_panel(client, chat_id, text, page="home"):
    from TechVJ.util.telegram_rich import make_inline_keyboard, send_styled_message
    rows = await _build_page_rows(page)
    try:
        return await send_styled_message(client, chat_id, text, buttons=rows, disable_web_page_preview=True)
    except Exception:
        return await client.send_message(chat_id, text, reply_markup=_keyboard_from_rows(rows), disable_web_page_preview=True)


async def _edit_panel(client, query, text, page="home"):
    from TechVJ.util.telegram_rich import api_request, make_inline_keyboard
    rows = await _build_page_rows(page)
    markup = make_inline_keyboard(rows)
    try:
        await api_request(client, "editMessageText", {
            "chat_id": query.message.chat.id,
            "message_id": query.message.id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
            "reply_markup": markup,
        })
    except Exception:
        try:
            await query.message.edit_text(text, reply_markup=_keyboard_from_rows(rows), disable_web_page_preview=True)
        except Exception:
            pass


async def _stats():
    users = await db.total_users_count()
    chats = await db.total_chat_count()
    channels = await db.get_managed_channels()
    try:
        files = await asyncio.to_thread(count_all_file_documents)
    except Exception:
        files = 0
    return users, chats, files, channels


def _ping_mongo_node_sync(node):
    try:
        from pymongo import MongoClient
        test = MongoClient(node["uri"], serverSelectionTimeoutMS=2500, connectTimeoutMS=2500)
        try:
            test.admin.command("ping")
            count = test[info.DATABASE_NAME][info.COLLECTION_NAME].estimated_document_count()
            return "ONLINE", count
        finally:
            test.close()
    except Exception:
        return "OFFLINE", 0


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
                f"Status: <b>{'🟢 ENABLED' if enabled else '🔴 DISABLED'}</b>\n"
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
        ping_results = await asyncio.gather(
            *(asyncio.to_thread(_ping_mongo_node_sync, node) for node in visible_nodes),
            return_exceptions=True,
        )
        for node, res in zip(visible_nodes, ping_results):
            status = "🟢 ENABLED" if node.get("enabled", True) else "⚪ DISABLED"
            if isinstance(res, tuple):
                state, count = res
            else:
                state, count = "OFFLINE", 0
            lines.append(f"• <b>{escape(node.get('label', 'Mongo'))}</b> — <code>#{escape(str(node['_id']))}</code> {status} / {state} / <code>{count:,}</code> files\n  <code>{escape(mask_uri(node['uri']))}</code>")
        try:
            base_count = await asyncio.to_thread(col.estimated_document_count)
            if info.SEC_FILE_DB_URI != info.FILE_DB_URI:
                base_count += await asyncio.to_thread(sec_col.estimated_document_count)
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
                "<i>When disabled, stream/download buttons and /stream will not generate links and will show a disabled message/popup.</i>")
    if page == "channels":
        auto_idx = await db.auto_index_enabled()
        post_chan = await db.get_auto_post_channel()
        chan_lines = []
        for cid in channels:
            label = f"<code>{escape(str(cid))}</code>"
            if client:
                try:
                    chat = await client.get_chat(cid)
                    label = f"{escape(chat.title or chat.username or str(cid))} (<code>{cid}</code>)"
                except Exception:
                    pass
            chan_lines.append(f"• {label}")
        lines = "\n".join(chan_lines) or "• No file channels configured"
        return (f"<b>📡 {BRAND} • CHANNELS & AUTO-INDEX</b>\n\n"
                f"Auto-index incoming files: <b>{'🟢 ENABLED' if auto_idx else '🔴 DISABLED'}</b>\n"
                f"Auto-post destination (/auto): <code>{post_chan or 'Not set'}</code>\n\n"
                f"<b>Configured file-index channels ({len(channels)})</b>\n{lines}\n\n"
                f"Force subscribe: <code>{AUTH_CHANNEL or 'Not set'}</code>\n"
                f"Log: <code>{LOG_CHANNEL or 'Not set'}</code>\n"
                f"Request: <code>{REQST_CHANNEL or 'Not set'}</code>\n"
                f"Index requests: <code>{INDEX_REQ_CHANNEL or 'Not set'}</code>\n\n"
                "<b>Commands:</b>\n"
                "<code>/panel add -100123456789</code>\n"
                "<code>/panel remove -100123456789</code>\n"
                "<code>/panel autoindex on|off</code>\n"
                "<code>/auto</code> — Configure 3-quality Movie & Series auto-post channel")
    if page in ("shorteners", "shortener_time_menu", "shortener_credits_menu", "shortener_delete_menu"):
        items = await db.get_shortener_pool()
        scfg = await db.get_shortener_config()
        mode = scfg.get("mode", "time")
        mode_title = MODE_LABELS.get(mode, mode.upper())
        exp_human = scfg.get("expire_human", "24h")
        exp_secs = scfg.get("expire_seconds", 86400)
        creds = scfg.get("credits_per_verify", 5)
        tut = scfg.get("tutorial_url") or "Not set"
        if items:
            lines = [
                f"{i}. <b>{escape(str(item.get('url', '')))}</b> — API: <code>{escape(str(item.get('api', ''))[:10])}…</code>"
                for i, item in enumerate(items, 1)
            ]
            listing = "\n".join(lines)
        else:
            fallback_info = f" (Fallback: <code>{escape(info.SHORTLINK_URL or info.VERIFY_SHORTLINK_URL)}</code>)" if (info.SHORTLINK_URL or info.VERIFY_SHORTLINK_URL) else ""
            listing = f"• No panel shorteners added yet.{fallback_info}"

        if page == "shortener_time_menu":
            return (
                f"<b>⏳ {BRAND} • SET VERIFIED EXPIRE TIME</b>\n\n"
                f"Current Verified Duration: <b>{exp_human}</b> (<code>{exp_secs:,}s</code>)\n"
                f"Active Mode: <b>{mode_title}</b>\n\n"
                "Select how long a verified user gets unlimited direct file access before needing to verify again, or tap <b>Custom Duration</b>:"
            )
        if page == "shortener_credits_menu":
            return (
                f"<b>🎟 {BRAND} • SET VERIFIED CREDITS COUNT</b>\n\n"
                f"Current Credits per Verification: <b>{creds} Credit{'s' if creds != 1 else ''}</b>\n"
                f"Active Mode: <b>{mode_title}</b>\n\n"
                "Select how many file downloads a user unlocks after completing 1 verification, or tap <b>Custom Credits Count</b>:"
            )
        if page == "shortener_delete_menu":
            return (
                f"<b>🗑 {BRAND} • DELETE SHORTENER</b>\n\n"
                f"<b>Saved shorteners ({len(items)}):</b>\n{listing}\n\n"
                "Tap a shortener below to remove it from rotation:"
            )
        return (
            f"<b>🔀 {BRAND} • SHORTENER & MODE MANAGER</b>\n\n"
            f"<blockquote>🎛 <b>Active Mode:</b> <b>{mode_title}</b>\n"
            f"⏳ <b>Verified Expire Duration:</b> <code>{exp_human}</code> ({exp_secs:,}s)\n"
            f"🎟 <b>Credits Per Verification:</b> <code>{creds} files</code>\n"
            f"🎬 <b>Tutorial Link:</b> <code>{escape(str(tut)[:100])}</code></blockquote>\n\n"
            f"<b>Saved Shorteners Pool ({len(items)})</b>\n{listing}\n\n"
            "<b>Quick Commands</b>\n"
            "• <code>/shortmode</code> — Open this Shortener & Mode selector\n"
            "• <code>/panel shortener mode time|credits|link|off</code>\n"
            "• <code>/panel shortener time 12h</code> (or <code>30m</code>, <code>6h</code>, <code>1d</code>, <code>2d</code>)\n"
            "• <code>/panel shortener credits 5</code> (set how many credits per verify)\n"
            "• <code>/panel shortener add DOMAIN API_KEY</code>\n"
            "• <code>/panel shortener delete NUMBER</code>\n"
            "• <code>/panel shortener tutorial URL</code>"
        )
    if page == "plans":
        plan_cfg = await db.config.find_one({"_id": "panel_plan_settings"}) or {}
        enabled = plan_cfg.get("enabled", True)
        qr = plan_cfg.get("payment_qr", getattr(info, "PAYMENT_QR", "")) or "Not set"
        upi = plan_cfg.get("upi_id", "demo@okxyz") or "Not set"
        text = plan_cfg.get("payment_text", getattr(info, "PAYMENT_TEXT", "")) or "Not set"
        return (f"<b>💎 {BRAND} | Plan Manager</b>\n\n"
                f"Plans: <b>{'🟢 ENABLED' if enabled else '🔴 DISABLED'}</b>\n"
                f"Payment QR: <code>{escape(str(qr)[:180])}</code>\n"
                f"UPI ID: <code>{escape(str(upi)[:100])}</code>\n\n"
                f"<b>Current plan/payment message:</b>\n{escape(str(text)[:900])}\n\n"
                "<b>Admin commands</b>\n"
                "<code>/panel plans on</code> or <code>/panel plans off</code>\n"
                "<code>/panel plans qr IMAGE_URL</code>\n"
                "<code>/panel plans upi YOUR_UPI_ID</code>\n"
                "<code>/panel plans text YOUR_PLAN_MESSAGE</code>\n"
                "<i>Settings are saved in MongoDB and apply without a restart.</i>")
    if page == "stats":
        scfg = await db.get_shortener_config()
        auto_cfg = await db.get_auto_post_settings()
        return (f"<b>📊 {BRAND} • LIVE STATISTICS</b>\n\n"
                f"👤 Users: <code>{users:,}</code>\n👥 Groups: <code>{chats:,}</code>\n"
                f"📁 Indexed files: <code>{files:,}</code>\n📡 File channels: <code>{len(channels):,}</code>\n"
                f"🛡 Admins: <code>{len(set(info.ADMINS))}</code>\n"
                f"🔀 Shortener Mode: <code>{scfg['mode'].upper()}</code> (Time: {scfg['expire_human']} | Credits: {scfg['credits_per_verify']})\n"
                f"🎬 Auto-Post (/auto): <code>{'ON' if auto_cfg['auto_index'] else 'OFF'}</code> (Dest: <code>{auto_cfg['post_channel_id'] or 'None'}</code>)")
    if page == "backup":
        return (f"<b>💾 {BRAND} • BACKUP & RESTORE</b>\n\n"
                "<code>/save</code> — open the interactive backup and import menu.\n"
                "💾 Backup sends a compressed <code>.zip</code> database archive.\n"
                "📥 Import asks for a backup ZIP and restores your database immediately upon receiving it.\n\n"
                "<b>⚠️ Restore replaces matching collections.</b> Keep a fresh backup before restoring.\n"
                "Legacy commands: <code>/add save</code> and <code>/add load</code>.")
    scfg = await db.get_shortener_config()
    auto_cfg = await db.get_auto_post_settings()
    return (f"<b>✦ {BRAND} CONTROL CENTER ✦</b>\n"
            "<i>High-speed administration • live bot overview</i>\n\n"
            f"<blockquote>📊 <b>Overview</b>\n"
            f"👤 Users: <code>{users:,}</code> • 👥 Groups: <code>{chats:,}</code>\n"
            f"📁 Indexed Files: <code>{files:,}</code> • 📡 Channels: <code>{len(channels):,}</code>\n"
            f"🔀 Shortener Mode: <b>{MODE_LABELS.get(scfg['mode'], scfg['mode'])}</b>\n"
            f"🎬 Auto-Post (/auto): <b>{'🟢 Enabled' if auto_cfg['auto_index'] else '🔴 Disabled'}</b></blockquote>\n\n"
            "<i>Select a module below to configure your bot:</i>")


async def _interactive_channel_action(client, chat_id, action):
    prompt_text = (
        f"<b>{'➕ ADD' if action == 'add' else '➖ REMOVE'} AUTO-INDEX CHANNEL</b>\n\n"
        "Send the channel ID (e.g. <code>-100123456789</code>), channel link, @username, "
        "or forward any message from that channel.\n\n"
        "<i>Send /cancel to abort.</i>"
    )
    prompt = await client.send_message(chat_id, prompt_text)
    try:
        resp = await client.ask(chat_id, "Waiting for channel ID / link / forwarded message…", timeout=120)
        text = (resp.text or resp.caption or "").strip()
        if text.lower() in ("/cancel", "cancel"):
            return await resp.reply_text("🛑 Cancelled.")
        if getattr(resp, "forward_from_chat", None):
            cid = int(resp.forward_from_chat.id)
            title = resp.forward_from_chat.title or str(cid)
        else:
            cid, title = await _resolve_channel_input(client, text)
        if action == "add":
            cid = await db.add_managed_channel(cid)
            await resp.reply_text(
                f"<b>✅ Channel added for auto-indexing:</b> {escape(title)} (<code>{cid}</code>)\n"
                "All new incoming files in this channel will now be indexed automatically."
            )
        else:
            removed = await db.remove_managed_channel(cid)
            await resp.reply_text(
                f"<b>{'✅ Channel removed' if removed else '⚠️ Could not remove channel'}:</b> {escape(title)} (<code>{cid}</code>)"
            )
    except asyncio.TimeoutError:
        try:
            await prompt.edit_text("⌛ Request timed out.")
        except Exception:
            pass
    except Exception as exc:
        await client.send_message(chat_id, f"❌ {escape(str(exc))}")


async def _interactive_shortener_add(client, chat_id):
    prompt_text = (
        "<b>➕ ADD SHORTENER TO POOL</b>\n\n"
        "Send your shortener <b>Domain</b> and <b>API Key</b> separated by a space:\n"
        "<code>example.com YOUR_API_KEY</code>\n\n"
        "<i>Or send just the domain first, and I will ask for the API key next. Send /cancel to abort.</i>"
    )
    prompt = await client.send_message(chat_id, prompt_text)
    try:
        resp = await client.ask(chat_id, "Send `DOMAIN API_KEY` now…", timeout=120)
        text = (resp.text or "").strip()
        if text.lower() in ("/cancel", "cancel"):
            return await resp.reply_text("🛑 Cancelled.")
        parts = text.split()
        if len(parts) >= 2:
            raw_domain, api = parts[0], parts[1].strip()
        else:
            raw_domain = parts[0]
            resp2 = await client.ask(chat_id, f"Now send the <b>API Key</b> for <code>{escape(raw_domain)}</code>:", timeout=120)
            api = (resp2.text or "").strip()
            if api.lower() in ("/cancel", "cancel"):
                return await resp2.reply_text("🛑 Cancelled.")
        domain = _normalize_shortener_domain(raw_domain)
        if not domain or not api:
            return await client.send_message(chat_id, "❌ Both domain and API key are required.")
        items = await db.get_shortener_pool()
        if any(_normalize_shortener_domain(x.get("url", "")) == domain and str(x.get("api", "")).strip() == api for x in items):
            return await client.send_message(chat_id, "⚠️ That shortener domain and API key are already saved.")
        items.append({"url": domain, "api": api})
        await db.set_shortener_pool(items)
        await client.send_message(
            chat_id,
            f"✅ <b>Shortener added!</b>\nDomain: <code>{escape(domain)}</code>\nAPI Key: <code>{escape(api[:10])}…</code>",
        )
        await _send_panel(client, chat_id, await _panel_text("shorteners", client), "shorteners")
    except asyncio.TimeoutError:
        try:
            await prompt.edit_text("⌛ Request timed out.")
        except Exception:
            pass
    except Exception as exc:
        await client.send_message(chat_id, f"❌ {escape(str(exc))}")


async def _interactive_shortener_custom(client, chat_id, kind):
    if kind == "time":
        prompt_text = (
            "<b>⏳ SET CUSTOM VERIFIED EXPIRE DURATION</b>\n\n"
            "Send the duration a verified user should keep direct access:\n"
            "Examples: <code>30m</code>, <code>2h</code>, <code>6h</code>, <code>12h</code>, <code>24h</code>, <code>2d</code>, <code>7d</code>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
    elif kind == "credits":
        prompt_text = (
            "<b>🎟 SET CUSTOM CREDITS PER VERIFICATION</b>\n\n"
            "Send how many file download credits a user should receive after 1 verification:\n"
            "Examples: <code>3</code>, <code>5</code>, <code>10</code>, <code>25</code>\n\n"
            "<i>Send /cancel to abort.</i>"
        )
    else:
        prompt_text = (
            "<b>🎬 SET SHORTENER TUTORIAL LINK</b>\n\n"
            "Send the tutorial video/channel URL (e.g. <code>https://t.me/...</code>), or send <code>off</code> to clear it.\n\n"
            "<i>Send /cancel to abort.</i>"
        )
    prompt = await client.send_message(chat_id, prompt_text)
    try:
        resp = await client.ask(chat_id, "Send value now…", timeout=120)
        val = (resp.text or "").strip()
        if val.lower() in ("/cancel", "cancel"):
            return await resp.reply_text("🛑 Cancelled.")
        if kind == "time":
            secs = parse_duration_to_seconds(val, default=0)
            if secs <= 0:
                return await resp.reply_text("❌ Invalid duration. Use formats like <code>30m</code>, <code>6h</code>, <code>12h</code>, <code>1d</code>.")
            scfg = await db.update_shortener_config(mode="time", expire_seconds=secs)
            await resp.reply_text(f"✅ Verified expire duration set to <b>{scfg['expire_human']}</b> (<code>{secs:,}s</code>) and mode set to <b>Time Mode</b>.")
        elif kind == "credits":
            if not val.isdigit() or int(val) < 1:
                return await resp.reply_text("❌ Please send a positive number of credits (e.g. <code>5</code>).")
            scfg = await db.update_shortener_config(mode="credits", credits_per_verify=int(val))
            await resp.reply_text(f"✅ Credits per verification set to <b>{scfg['credits_per_verify']} credits</b> and mode set to <b>Credits Mode</b>.")
        else:
            tut = "" if val.lower() in ("off", "none", "clear", "remove") else val
            await db.update_shortener_config(tutorial_url=tut)
            await resp.reply_text(f"✅ Tutorial link {'cleared' if not tut else f'set to <code>{escape(tut)}</code>'}.")
        await _send_panel(client, chat_id, await _panel_text("shorteners", client), "shorteners")
    except asyncio.TimeoutError:
        try:
            await prompt.edit_text("⌛ Request timed out.")
        except Exception:
            pass
    except Exception as exc:
        await client.send_message(chat_id, f"❌ {escape(str(exc))}")


@Client.on_message(filters.command(["shortmode", "mode", "shortener"]))
async def shortmode_command(client, message):
    """Direct command to open or configure the Shortener Mode & Pool Manager."""
    uid = message.from_user.id if message.from_user else None
    if not _is_admin(uid):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    args = (message.command or [])[1:]
    if not args:
        return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
    # Forward arguments to /panel shortener handler
    message.command = ["panel", "shortener", *args]
    return await panel(client, message)


@Client.on_message(filters.command("panel"))
async def panel(client, message):
    uid = message.from_user.id if message.from_user else None
    if not _is_admin(uid):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    command_parts = getattr(message, "command", None) or []
    args = command_parts[1:] if command_parts else []
    if args and args[0].lower() in {"channel", "channels"}:
        if len(args) == 1:
            return await _send_panel(client, message.chat.id, await _panel_text("channels", client=client), page="channels")
        args = args[1:]
    if args and args[0].lower() == "autoindex":
        if len(args) != 2 or args[1].lower() not in {"on", "off"}:
            return await message.reply_text("Usage: <code>/panel autoindex on</code> or <code>/panel autoindex off</code>")
        state = args[1].lower() == "on"
        await db.set_auto_index_enabled(state)
        return await message.reply_text(f"<b>✅ Channel auto-indexing {'ENABLED' if state else 'DISABLED'}.</b>")
    if args and args[0].lower() in {"add", "remove"}:
        if len(args) != 2:
            return await message.reply_text("Usage: <code>/panel add -100123456789</code> or <code>/panel remove -100123456789</code>")
        try:
            channel_id, title = await _resolve_channel_input(client, args[1])
        except ValueError as exc:
            return await message.reply_text(str(exc))
        if args[0].lower() == "add":
            channel_id = await db.add_managed_channel(channel_id)
            return await message.reply_text(
                f"<b>✅ Channel added for auto-indexing:</b> {escape(title)} (<code>{channel_id}</code>)\n"
                "Ensure the bot is an administrator there. Incoming files will be indexed automatically."
            )
        removed = await db.remove_managed_channel(channel_id)
        return await message.reply_text(f"<b>{'✅ Channel removed' if removed else '⚠️ Could not remove channel'}:</b> <code>{channel_id}</code>")
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
                node_id = await asyncio.to_thread(add_node, args[2])
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
                changed = await asyncio.to_thread(remove_node, node_id)
                return await message.reply_text("✅ MongoDB node removed from rotation. Existing data is not deleted." if changed else "⚠️ MongoDB node ID not found.")
            changed = await asyncio.to_thread(set_node_enabled, node_id, action == "enable")
            return await message.reply_text(("✅ Node enabled." if action == "enable" else "✅ Node disabled; its existing data remains searchable and included in backups.") if changed else "⚠️ MongoDB node ID not found.")
        return await message.reply_text("Invalid MongoDB command. Use <code>/panel mongo</code> for help.")
    if args and args[0].lower() in {"shortener", "shorteners", "mode"}:
        if args[0].lower() == "mode":
            args = ["shortener", "mode", *args[1:]]
        items = await db.get_shortener_pool()
        if len(args) == 1 or args[1].lower() in {"list", "menu", "status"}:
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        action = args[1].lower()
        if action in {"mode", "setmode"}:
            if len(args) < 3:
                return await message.reply_text(
                    "Usage: <code>/panel shortener mode time|credits|link|off</code>\n"
                    "• <code>time</code> — Verified user gets direct access until expire duration\n"
                    "• <code>credits</code> — Verified user gets N file download credits\n"
                    "• <code>link</code> — Shortlink generated on every file\n"
                    "• <code>off</code> — Disable shortener"
                )
            chosen = args[2].lower()
            scfg = await db.update_shortener_config(mode=chosen)
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        if action in {"time", "duration", "expire", "expiry"}:
            if len(args) < 3:
                return await message.reply_text("Usage: <code>/panel shortener time 12h</code> (supports <code>30m</code>, <code>6h</code>, <code>12h</code>, <code>24h</code>, <code>2d</code>)")
            secs = parse_duration_to_seconds(" ".join(args[2:]), default=0)
            if secs <= 0:
                return await message.reply_text("Invalid duration. Example: <code>/panel shortener time 12h</code> or <code>/panel shortener time 1d</code>")
            await db.update_shortener_config(mode="time", expire_seconds=secs)
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        if action in {"credits", "credit", "count"}:
            if len(args) < 3 or not args[2].isdigit() or int(args[2]) < 1:
                return await message.reply_text("Usage: <code>/panel shortener credits 5</code> (number of files per verification)")
            await db.update_shortener_config(mode="credits", credits_per_verify=int(args[2]))
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        if action in {"tutorial", "tut"}:
            if len(args) < 3:
                return await message.reply_text("Usage: <code>/panel shortener tutorial https://t.me/...</code> (or <code>off</code>)")
            tut = "" if args[2].lower() in {"off", "none", "clear"} else args[2].strip()
            await db.update_shortener_config(tutorial_url=tut)
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        if action == "add":
            if len(args) < 4:
                return await message.reply_text("Usage: <code>/panel shortener add DOMAIN API_KEY</code>")
            domain = _normalize_shortener_domain(args[2])
            api = args[3].strip()
            if not domain or not api:
                return await message.reply_text("Domain and API key are required.")
            exact_pair_exists = any(
                _normalize_shortener_domain(x.get("url", "")) == domain
                and str(x.get("api", "")).strip() == api
                for x in items
            )
            api_exists = any(str(x.get("api", "")).strip() == api for x in items)
            if exact_pair_exists:
                return await message.reply_text("That shortener domain and API key are already saved.")
            if api_exists:
                return await message.reply_text("That API key is already saved.")
            items.append({"url": domain, "api": api})
            await db.set_shortener_pool(items)
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        if action in {"delete", "remove", "del"}:
            if len(args) != 3 or not args[2].isdigit() or not 1 <= int(args[2]) <= len(items):
                return await message.reply_text("Usage: <code>/panel shortener delete NUMBER</code> (use list number)")
            removed = items.pop(int(args[2]) - 1)
            await db.set_shortener_pool(items)
            await message.reply_text(f"✅ Deleted shortener <code>{escape(removed.get('url', ''))}</code>.")
            return await _send_panel(client, message.chat.id, await _panel_text("shorteners", client), "shorteners")
        return await message.reply_text(
            "Use:\n"
            "• <code>/panel shortener mode time|credits|link|off</code>\n"
            "• <code>/panel shortener time 12h</code>\n"
            "• <code>/panel shortener credits 5</code>\n"
            "• <code>/panel shortener add DOMAIN API_KEY</code>\n"
            "• <code>/panel shortener delete NUMBER</code>"
        )
    if args and args[0].lower() in {"plan", "plans"}:
        if len(args) < 2:
            return await _send_panel(client, message.chat.id, await _panel_text("plans", client), "plans")
        action = args[1].lower()
        if action in {"on", "off"}:
            await db.config.update_one({"_id": "panel_plan_settings"}, {"$set": {"enabled": action == "on"}}, upsert=True)
            return await message.reply_text(f"✅ Premium plans {'enabled' if action == 'on' else 'disabled'}.")
        if action in {"qr", "upi", "text"}:
            value = message.text.split(None, 3)[3].strip() if len(message.text.split(None, 3)) > 3 else ""
            if not value:
                return await message.reply_text(f"Send value: <code>/panel plans {action} VALUE</code>")
            key = {"qr": "payment_qr", "upi": "upi_id", "text": "payment_text"}[action]
            await db.config.update_one({"_id": "panel_plan_settings"}, {"$set": {key: value}}, upsert=True)
            if action == "upi":
                old = await db.config.find_one({"_id": "panel_plan_settings"}) or {}
                payment_text = old.get("payment_text", getattr(info, "PAYMENT_TEXT", ""))
                payment_text = re.sub(r"(<b>UPI ID:</b>\s*<code>).*?(</code>)", lambda m: m.group(1) + escape(value) + m.group(2), payment_text, flags=re.I)
                await db.config.update_one({"_id": "panel_plan_settings"}, {"$set": {"payment_text": payment_text}}, upsert=True)
            return await message.reply_text(f"✅ Plan {action.upper()} setting saved in MongoDB.")
        return await message.reply_text("Unknown action. Open <code>/panel</code> → 💎 Plan Manager.")
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


@Client.on_callback_query(filters.regex(r"^tgbox_panel:"), group=-1)
async def panel_callbacks(client, query):
    if not _is_admin(query.from_user.id):
        return await query.answer("Admin access only.", show_alert=True)
    action = query.data.split(":", 1)[1]

    if action == "fsub_toggle":
        cur = await db.force_subscribe_enabled()
        await db.set_force_subscribe_enabled(not cur)
        await _edit_panel(client, query, await _panel_text("fsub", client), "fsub")
        return await query.answer(f"Force Subscribe {'ENABLED' if not cur else 'DISABLED'}.")

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

    # Shortener Mode Selection callbacks
    if action.startswith("smode_"):
        chosen_mode = action.split("_", 1)[1]
        scfg = await db.update_shortener_config(mode=chosen_mode)
        await _edit_panel(client, query, await _panel_text("shorteners", client), "shorteners")
        return await query.answer(f"Shortener Mode set to: {MODE_LABELS.get(scfg['mode'], scfg['mode'])}", show_alert=True)

    if action == "shortener_time_menu":
        await _edit_panel(client, query, await _panel_text("shortener_time_menu", client), "shortener_time_menu")
        return await query.answer("Select verified expire duration")

    if action.startswith("stime_"):
        val = action.split("_", 1)[1]
        if val == "custom":
            await query.answer("Send custom duration in chat…")
            asyncio.create_task(_interactive_shortener_custom(client, query.message.chat.id, "time"))
            return
        secs = int(val)
        scfg = await db.update_shortener_config(mode="time", expire_seconds=secs)
        await _edit_panel(client, query, await _panel_text("shorteners", client), "shorteners")
        return await query.answer(f"✅ Verified duration set to {scfg['expire_human']} (Time Mode active)", show_alert=True)

    if action == "shortener_credits_menu":
        await _edit_panel(client, query, await _panel_text("shortener_credits_menu", client), "shortener_credits_menu")
        return await query.answer("Select credits per verification")

    if action.startswith("scred_"):
        val = action.split("_", 1)[1]
        if val == "custom":
            await query.answer("Send custom credits count in chat…")
            asyncio.create_task(_interactive_shortener_custom(client, query.message.chat.id, "credits"))
            return
        count = int(val)
        scfg = await db.update_shortener_config(mode="credits", credits_per_verify=count)
        await _edit_panel(client, query, await _panel_text("shorteners", client), "shorteners")
        return await query.answer(f"✅ Credits set to {count} per verification (Credits Mode active)", show_alert=True)

    if action == "shortener_add":
        await query.answer("Send DOMAIN API_KEY in chat…")
        asyncio.create_task(_interactive_shortener_add(client, query.message.chat.id))
        return

    if action == "shortener_tutorial":
        await query.answer("Send tutorial URL in chat…")
        asyncio.create_task(_interactive_shortener_custom(client, query.message.chat.id, "tutorial"))
        return

    if action == "shortener_delete":
        items = await db.get_shortener_pool()
        if not items:
            return await query.answer("No saved shorteners to delete.", show_alert=True)
        await _edit_panel(client, query, await _panel_text("shortener_delete_menu", client), "shortener_delete_menu")
        return await query.answer("Tap a shortener to delete")

    if action.startswith("sdel_"):
        idx = int(action.split("_", 1)[1])
        items = await db.get_shortener_pool()
        if 1 <= idx <= len(items):
            removed = items.pop(idx - 1)
            await db.set_shortener_pool(items)
            await query.answer(f"Deleted {removed.get('url', '')}", show_alert=True)
        else:
            await query.answer("Entry not found.", show_alert=True)
        next_page = "shortener_delete_menu" if items else "shorteners"
        await _edit_panel(client, query, await _panel_text(next_page, client), next_page)
        return

    if action == "mongo_help_add":
        await query.answer("Send /panel mongo add mongodb+srv://USER:PASS@HOST/DB in this private chat", show_alert=True)
        return
    if action in {"chan_add_prompt", "chan_remove_prompt"}:
        mode = "add" if action == "chan_add_prompt" else "remove"
        await query.answer(f"Send channel ID or link to {mode}.")
        asyncio.create_task(_interactive_channel_action(client, query.message.chat.id, mode))
        return
    if action == "chan_toggle_auto":
        current = await db.auto_index_enabled()
        await db.set_auto_index_enabled(not current)
        await _edit_panel(client, query, await _panel_text("channels", client), "channels")
        return await query.answer(f"Channel auto-index {'ENABLED' if not current else 'DISABLED'}.", show_alert=True)
    if action.startswith("chan_del_"):
        cid_raw = action[len("chan_del_"):]
        await db.remove_managed_channel(cid_raw)
        await _edit_panel(client, query, await _panel_text("channels", client), "channels")
        return await query.answer(f"Channel {cid_raw} removed from auto-index.")
    if action in {"link_toggle_stream", "link_toggle_download"}:
        feature = "stream_enabled" if action.endswith("stream") else "download_enabled"
        current = await db.get_link_feature(feature)
        await db.set_link_feature(feature, not current)
        await _edit_panel(client, query, await _panel_text("links", client), "links")
        return await query.answer(f"{'Enabled' if not current else 'Disabled'} successfully.")
    if action.startswith("mongo_enable_") or action.startswith("mongo_disable_"):
        mode, node_id = action.split("_", 2)[1:]
        changed = await asyncio.to_thread(set_node_enabled, node_id, mode == "enable")
        if not changed:
            return await query.answer("MongoDB node not found.", show_alert=True)
        await _edit_panel(client, query, await _panel_text("mongo", client), "mongo")
        return await query.answer("MongoDB node enabled." if mode == "enable" else "MongoDB node disabled.")
    page = {"refresh": "home", "shortener": "shorteners", "plan": "plans"}.get(action, action)
    if page not in {"home", "admins", "channels", "fsub", "stats", "backup", "mongo", "links", "shorteners", "plans"}:
        return await query.answer("Unknown panel section.", show_alert=True)
    await _edit_panel(client, query, await _panel_text(page, client), page)
    await query.answer("Updated")
