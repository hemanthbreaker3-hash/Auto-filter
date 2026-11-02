# MoviesZoneFlix indexing manager
import asyncio
import html
import logging
import re
import time
import uuid

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import (
    ChannelInvalid,
    ChatAdminRequired,
    UsernameInvalid,
    UsernameNotModified,
)

import info
from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from utils import temp
from database.ia_filterdb import save_files_batch
from TechVJ.util.auto_post import process_caption_for_auto_post
from database.users_chats_db import db, normalize_channel_id
from TechVJ.util.telegram_rich import ButtonStyle

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TASKS = {}
TASK_LOCK = asyncio.Lock()

SINGLE_OR_SHORT_RANGE_RE = re.compile(
    r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:(c)/)?([A-Za-z0-9_]+|-?\d+)/(?:(\d+)/)?(\d+)(?:\s*-\s*(\d+))?(?:\?.*)?$",
    re.IGNORECASE,
)

FULL_LINK_FINDER_RE = re.compile(
    r"(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?(?:[A-Za-z0-9_]+|-?\d+)/(?:\d+/)?\d+(?:\?[^\s\-]+)?",
    re.IGNORECASE,
)


def _is_admin(user_id):
    return bool(user_id and int(user_id) in info.ADMINS)


def _normalize_chat_ref(is_private_c, chat_raw):
    chat_str = str(chat_raw).strip()
    if is_private_c or chat_str.lstrip("-").isdigit():
        norm = normalize_channel_id(chat_str)
        if norm is not None:
            return norm
    return chat_str


def parse_link(value):
    """Parse a single Telegram message link and return (chat_ref, msg_id)."""
    cleaned = value.strip().rstrip("/")
    match = SINGLE_OR_SHORT_RANGE_RE.match(cleaned)
    if not match or match.group(5) is not None:
        raise ValueError("Invalid Telegram message link.")
    is_c, chat_raw, _topic_id, msg_id_str, _ = match.groups()
    chat = _normalize_chat_ref(bool(is_c), chat_raw)
    msg_id = int(msg_id_str)
    if msg_id <= 0:
        raise ValueError("Message ID must be a positive number.")
    return chat, msg_id


def parse_link_or_range(value):
    """Parse any supported Telegram message link or range format."""
    raw = (value or "").strip()
    if not raw:
        raise ValueError("Invalid Telegram message link.")

    found_links = FULL_LINK_FINDER_RE.findall(raw)
    if len(found_links) == 2:
        first_chat, first_id = parse_link(found_links[0])
        last_chat, last_id = parse_link(found_links[1])
        if first_chat != last_chat:
            raise ValueError("Both links must belong to the same channel/group.")
        if first_id > last_id:
            first_id, last_id = last_id, first_id
        return first_chat, first_id, last_id, True
    if len(found_links) > 2:
        raise ValueError("Send at most two links per range (start-end).")

    cleaned = raw.rstrip("/")
    match = SINGLE_OR_SHORT_RANGE_RE.match(cleaned)
    if not match:
        raise ValueError("Invalid Telegram message link.")
    is_c, chat_raw, _topic_id, start_str, end_str = match.groups()
    chat = _normalize_chat_ref(bool(is_c), chat_raw)
    first_id = int(start_str)
    if first_id <= 0:
        raise ValueError("Message ID must be a positive number.")
    if end_str is not None:
        last_id = int(end_str)
        if last_id <= 0:
            raise ValueError("Message ID must be a positive number.")
        if first_id > last_id:
            first_id, last_id = last_id, first_id
        return chat, first_id, last_id, True

    skip_start = max(1, int(getattr(temp, "CURRENT", 1) or 1))
    if skip_start == 2 and "SKIP" not in __import__("os").environ:
        skip_start = 1
    if first_id >= skip_start:
        return chat, skip_start, first_id, False
    return chat, 1, first_id, False


def _format_duration(seconds):
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m {s}s"
    if m > 0:
        return f"{m}m {s}s"
    return f"{s}s"


def _progress_bar(pct, width=10):
    pct = max(0.0, min(100.0, float(pct)))
    filled = int(round((pct / 100.0) * width))
    return "█" * filled + "░" * (width - filled)


def _status_badge(status):
    return {
        "QUEUED": "⏳ QUEUED",
        "RUNNING": "🟢 RUNNING",
        "PAUSED": "⏸ PAUSED",
        "COMPLETED": "✅ COMPLETED",
        "CANCELLED": "🛑 CANCELLED",
        "FAILED": "❌ FAILED",
    }.get(status, status)


def status_text(t):
    total_range = max(1, int(t["last"] - t["first"] + 1))
    done = min(total_range, int(t["processed"]))
    pct = (done / total_range) * 100.0 if total_range > 0 else 100.0
    if t["status"] == "COMPLETED":
        pct = 100.0
    now = t.get("finished_at") or time.time()
    elapsed = max(1.0, now - t.get("started_at", now))
    speed = t["processed"] / elapsed if t["processed"] > 0 else 0.0
    remaining_msgs = max(0, total_range - done)
    eta_str = _format_duration(remaining_msgs / speed) if (speed > 0 and t["status"] == "RUNNING") else ("—" if t["status"] != "COMPLETED" else "0s")
    chat_label = html.escape(str(t.get("chat_title") or t["chat"]))
    curr_id = t.get("current", t["first"])

    lines = [
        f"<b>📁 INDEX TASK #{t['short']}</b>",
        f"📡 Channel: <b>{chat_label}</b> (<code>{t['chat']}</code>)",
        f"🔢 Range: <code>{t['first']:,}</code> → <code>{t['last']:,}</code> (<code>{total_range:,}</code> msgs)",
        f"📍 Current ID: <code>{curr_id:,}</code>",
        f"📊 Progress: <code>[{_progress_bar(pct)}] {pct:.1f}%</code>",
        f"⚡ Status: <b>{_status_badge(t['status'])}</b>",
        f"⏱ Elapsed: <code>{_format_duration(elapsed)}</code> • Speed: <code>{speed:.1f} msg/s</code> • ETA: <code>{eta_str}</code>",
        "",
        f"🔎 Messages scanned: <code>{t['processed']:,}</code> / <code>{total_range:,}</code>",
        f"✅ Files saved: <code>{t['saved']:,}</code>",
        f"♻️ Duplicates: <code>{t['duplicates']:,}</code>",
        f"🗑 Deleted/Empty: <code>{t['deleted']:,}</code>",
        f"⏭ Non-media/Skipped: <code>{t['skipped']:,}</code>",
        f"⚠️ Errors: <code>{t['errors']:,}</code>",
    ]
    if t.get("error"):
        lines.append(f"\n❗ <b>Error:</b> <code>{html.escape(str(t['error']))}</code>")
    return "\n".join(lines)


def controls(task_id):
    t = TASKS.get(task_id)
    if not t:
        return InlineKeyboardMarkup([[InlineKeyboardButton("📋 All Tasks", callback_data="idxctl:list:0", style=ButtonStyle.PRIMARY)]])
    status = t["status"]
    rows = []
    if status in ("RUNNING", "QUEUED"):
        rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data=f"idxctl:view:{task_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("ℹ️ Popup Info", callback_data=f"idxctl:popup:{task_id}", style=ButtonStyle.SUCCESS),
        ])
        rows.append([
            InlineKeyboardButton("⏸ Pause", callback_data=f"idxctl:pause:{task_id}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("✖ Cancel", callback_data=f"idxctl:cancel:{task_id}", style=ButtonStyle.DANGER),
        ])
    elif status == "PAUSED":
        rows.append([
            InlineKeyboardButton("▶️ Resume", callback_data=f"idxctl:resume:{task_id}", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton("✖ Cancel", callback_data=f"idxctl:cancel:{task_id}", style=ButtonStyle.DANGER),
        ])
        rows.append([
            InlineKeyboardButton("🔄 Refresh", callback_data=f"idxctl:view:{task_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("ℹ️ Popup Info", callback_data=f"idxctl:popup:{task_id}", style=ButtonStyle.SUCCESS),
        ])
    else:
        action_row = [InlineKeyboardButton("🔁 Re-index Range", callback_data=f"idxctl:rerun:{task_id}", style=ButtonStyle.PRIMARY)]
        if status in ("CANCELLED", "FAILED") and t.get("current", t["first"]) < t["last"]:
            action_row.append(InlineKeyboardButton("▶️ Continue Remaining", callback_data=f"idxctl:continue:{task_id}", style=ButtonStyle.SUCCESS))
        rows.append(action_row)
        rows.append([
            InlineKeyboardButton("ℹ️ Popup Info", callback_data=f"idxctl:popup:{task_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🗑 Remove Task", callback_data=f"idxctl:delete:{task_id}", style=ButtonStyle.DANGER),
        ])
    rows.append([
        InlineKeyboardButton("📋 All Tasks (/indexstatus)", callback_data="idxctl:list:0", style=ButtonStyle.PRIMARY),
        InlineKeyboardButton("➕ New /index", callback_data="idxctl:new:0", style=ButtonStyle.SUCCESS),
    ])
    return InlineKeyboardMarkup(rows)


def _tasks_overview_text_and_markup():
    tasks = list(TASKS.values())
    if not tasks:
        text = (
            "📊 <b>INDEX TASK MANAGER</b>\n\n"
            "No indexing tasks found.\n\n"
            "Use <code>/index https://t.me/c/CHANNEL_ID/START-https://t.me/c/CHANNEL_ID/END</code> "
            "or click the button below to start a new index task."
        )
        markup = InlineKeyboardMarkup([
            [InlineKeyboardButton("➕ Start New /index", callback_data="idxctl:new:0", style=ButtonStyle.SUCCESS)],
            [InlineKeyboardButton("🔄 Refresh", callback_data="idxctl:list:0", style=ButtonStyle.PRIMARY)],
        ])
        return text, markup

    running = sum(1 for t in tasks if t["status"] in ("RUNNING", "QUEUED"))
    paused = sum(1 for t in tasks if t["status"] == "PAUSED")
    completed = sum(1 for t in tasks if t["status"] == "COMPLETED")
    cancelled = sum(1 for t in tasks if t["status"] == "CANCELLED")
    failed = sum(1 for t in tasks if t["status"] == "FAILED")
    total_saved = sum(t["saved"] for t in tasks)
    total_scanned = sum(t["processed"] for t in tasks)

    text = (
        "📊 <b>INDEX TASK MANAGER</b>\n\n"
        f"🟢 Running: <code>{running}</code> • ⏸ Paused: <code>{paused}</code>\n"
        f"✅ Completed: <code>{completed}</code> • 🛑 Cancelled: <code>{cancelled}</code> • ❌ Failed: <code>{failed}</code>\n"
        f"🔎 Total Scanned: <code>{total_scanned:,}</code> • 💾 Total Saved: <code>{total_saved:,}</code>\n\n"
        "<i>Select a task below to view live progress, pause, resume, cancel, or re-run:</i>"
    )

    rows = []
    icon_map = {
        "RUNNING": "🟢",
        "QUEUED": "⏳",
        "PAUSED": "⏸",
        "COMPLETED": "✅",
        "CANCELLED": "🛑",
        "FAILED": "❌",
    }
    style_map = {
        "RUNNING": ButtonStyle.SUCCESS,
        "QUEUED": ButtonStyle.PRIMARY,
        "PAUSED": ButtonStyle.DANGER,
        "COMPLETED": ButtonStyle.PRIMARY,
        "CANCELLED": ButtonStyle.DANGER,
        "FAILED": ButtonStyle.DANGER,
    }
    for t in reversed(tasks[-20:]):
        total_range = max(1, int(t["last"] - t["first"] + 1))
        pct = min(100.0, (t["processed"] / total_range) * 100.0) if t["status"] != "COMPLETED" else 100.0
        icon = icon_map.get(t["status"], "⚪")
        btn_style = style_map.get(t["status"], ButtonStyle.PRIMARY)
        title = (t.get("chat_title") or str(t["chat"]))[:14]
        rows.append([
            InlineKeyboardButton(
                f"{icon} #{t['short']} · {title} · {pct:.0f}% ({t['saved']:,} saved)",
                callback_data=f"idxctl:view:{t['id']}",
                style=btn_style,
            )
        ])

    bulk_row = []
    if running > 0:
        bulk_row.append(InlineKeyboardButton("⏸ Pause All", callback_data="idxctl:pauseall:0", style=ButtonStyle.DANGER))
    if paused > 0:
        bulk_row.append(InlineKeyboardButton("▶️ Resume All", callback_data="idxctl:resumeall:0", style=ButtonStyle.SUCCESS))
    if running > 0 or paused > 0:
        bulk_row.append(InlineKeyboardButton("✖ Cancel All", callback_data="idxctl:cancelall:0", style=ButtonStyle.DANGER))
    if bulk_row:
        rows.append(bulk_row)

    bottom_row = [InlineKeyboardButton("🔄 Refresh List", callback_data="idxctl:list:0", style=ButtonStyle.PRIMARY)]
    if completed + cancelled + failed > 0:
        bottom_row.append(InlineKeyboardButton("🧹 Clear Finished", callback_data="idxctl:clear:0", style=ButtonStyle.DANGER))
    rows.append(bottom_row)
    rows.append([InlineKeyboardButton("➕ Start New /index Task", callback_data="idxctl:new:0", style=ButtonStyle.SUCCESS)])
    return text, InlineKeyboardMarkup(rows)


async def _notify_task_messages(bot, t):
    """Update the primary task status message and any /indexstatus viewer messages."""
    text = status_text(t)
    markup = controls(t["id"])
    targets = []
    status_msg = t.get("message")
    if status_msg:
        targets.append((status_msg.chat.id, status_msg.id))
    for chat_id, msg_id in list(t.get("viewers", set())):
        if (chat_id, msg_id) not in targets:
            targets.append((chat_id, msg_id))
    for chat_id, msg_id in targets:
        try:
            await bot.edit_message_text(chat_id, msg_id, text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        except Exception:
            pass


def _extract_indexable_media(msg):
    """Extract any indexable media object from a message without skipping underscore or extensionless files."""
    if not msg:
        return None
    if getattr(msg, "media", None) and hasattr(msg.media, "value"):
        if msg.media in (
            enums.MessageMediaType.VIDEO,
            enums.MessageMediaType.AUDIO,
            enums.MessageMediaType.DOCUMENT,
            enums.MessageMediaType.ANIMATION,
        ):
            media = getattr(msg, msg.media.value, None)
            if media and getattr(media, "file_id", None):
                return media
    for attr in ("document", "video", "audio", "animation"):
        media = getattr(msg, attr, None)
        if media and getattr(media, "file_id", None):
            return media
    return None


async def run_index(bot, task_id, chat, first_id, last_id, status_msg):
    t = TASKS.get(task_id)
    if not t:
        return
    batch = []
    last_update = 0.0

    async def flush():
        if not batch:
            return
        pending = list(batch)
        batch.clear()
        try:
            saved, duplicates, failed = await save_files_batch(pending)
            t["saved"] += saved
            t["duplicates"] += duplicates
            t["errors"] += failed
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Index batch write failed")
            t["errors"] += len(pending)

    async def update(force=False):
        nonlocal last_update
        now = asyncio.get_running_loop().time()
        if not force and now - last_update < 3.5:
            return
        last_update = now
        await _notify_task_messages(bot, t)

    if not t["cancel"]:
        t["status"] = "RUNNING"
    await update(True)

    current = int(first_id)
    limit = int(last_id)
    try:
        while current <= limit and not t["cancel"]:
            if not t["pause_event"].is_set():
                await update(True)
                await t["pause_event"].wait()
                if t["cancel"]:
                    break
                t["status"] = "RUNNING"
                await update(True)

            chunk_size = min(200, limit - current + 1)
            msg_ids = list(range(current, current + chunk_size))
            while not t["cancel"]:
                try:
                    messages = await bot.get_messages(chat, msg_ids)
                    break
                except FloodWait as e:
                    wait_s = int(getattr(e, "value", getattr(e, "x", 5)) or 5)
                    for _ in range(wait_s):
                        if t["cancel"]:
                            break
                        await asyncio.sleep(1)
            if t["cancel"]:
                break

            if not isinstance(messages, list):
                messages = [messages]

            for msg in messages:
                if t["cancel"]:
                    break
                if not t["pause_event"].is_set():
                    await flush()
                    await update(True)
                    await t["pause_event"].wait()
                    if t["cancel"]:
                        break
                    t["status"] = "RUNNING"

                t["processed"] += 1
                t["current"] = getattr(msg, "id", None) or current
                current += 1

                if not msg or getattr(msg, "empty", False) or getattr(msg, "service", False):
                    t["deleted"] += 1
                else:
                    media = _extract_indexable_media(msg)
                    if media:
                        media.caption = msg.caption
                        batch.append(media)
                        raw_cap = str(msg.caption) if msg.caption else None
                        raw_fname = getattr(media, "file_name", None)
                        if raw_cap or raw_fname:
                            await process_caption_for_auto_post(bot, caption=raw_cap, source_chat_id=chat, file_name=raw_fname)
                        if len(batch) >= 100:
                            await flush()
                    else:
                        t["skipped"] += 1

                if t["processed"] % 100 == 0:
                    await flush()
                    await update()

            await flush()
            await update()

        await flush()
        t["finished_at"] = time.time()
        t["status"] = "CANCELLED" if t["cancel"] else "COMPLETED"
    except asyncio.CancelledError:
        try:
            await flush()
        except Exception:
            pass
        t["cancel"] = True
        t["finished_at"] = time.time()
        t["status"] = "CANCELLED"
    except Exception as exc:
        try:
            await flush()
        except Exception:
            pass
        t["finished_at"] = time.time()
        if t["cancel"]:
            t["status"] = "CANCELLED"
        else:
            t["status"] = "FAILED"
            t["error"] = str(exc)[:300]
            logger.exception("Index task failed")
    await update(True)


async def start_task(bot, user_id, chat, first_id, last_id):
    try:
        chat_obj = await bot.get_chat(chat)
        chat_id = chat_obj.id
        chat_title = chat_obj.title or chat_obj.username or str(chat_id)
        await bot.get_messages(chat_id, last_id)
    except ChannelInvalid:
        raise ValueError("This may be a private channel/group. Add the bot as an admin first.")
    except (UsernameInvalid, UsernameNotModified):
        raise ValueError("Invalid channel or message link.")
    except ChatAdminRequired:
        raise ValueError("Bot must be an admin in that channel/group to read messages.")
    except Exception as exc:
        raise ValueError(f"Cannot access the channel/messages: {exc}")

    try:
        await db.add_managed_channel(chat_id)
    except Exception:
        pass

    task_id = uuid.uuid4().hex[:8]
    pause_event = asyncio.Event()
    pause_event.set()
    t = {
        "id": task_id,
        "short": task_id.upper(),
        "user": user_id,
        "chat": chat_id,
        "chat_title": chat_title,
        "first": int(first_id),
        "last": int(last_id),
        "current": int(first_id),
        "status": "QUEUED",
        "cancel": False,
        "pause_event": pause_event,
        "started_at": time.time(),
        "finished_at": None,
        "processed": 0,
        "saved": 0,
        "duplicates": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": 0,
        "message": None,
        "viewers": set(),
    }
    TASKS[task_id] = t
    status_msg = await bot.send_message(
        user_id,
        status_text(t),
        reply_markup=controls(task_id),
        disable_web_page_preview=True,
    )
    t["message"] = status_msg
    t["runner"] = asyncio.create_task(run_index(bot, task_id, chat_id, int(first_id), int(last_id), status_msg))
    return task_id


def _cancel_task_now(t):
    if t["status"] in ("COMPLETED", "CANCELLED", "FAILED"):
        return False
    t["cancel"] = True
    t["status"] = "CANCELLED"
    t["finished_at"] = time.time()
    if "pause_event" in t:
        t["pause_event"].set()
    runner = t.get("runner")
    if runner and not runner.done():
        runner.cancel()
    return True


async def _process_index_submission(bot, user_id, reply_message, raw_text=None, forwarded_msg=None):
    """Handle one or more link/range inputs or a forwarded channel message and start tasks."""
    if forwarded_msg and getattr(forwarded_msg, "forward_from_chat", None) and getattr(forwarded_msg, "forward_from_message_id", None):
        f_chat = forwarded_msg.forward_from_chat.id
        f_msg_id = int(forwarded_msg.forward_from_message_id)
        try:
            task_id = await start_task(bot, user_id, f_chat, 1, f_msg_id)
            return await reply_message.reply_text(
                f"✅ Index task <code>#{task_id.upper()}</code> started for <code>1</code> → <code>{f_msg_id}</code>.\n"
                "Use /indexstatus to view and manage all running tasks."
            )
        except Exception as exc:
            return await reply_message.reply_text(f"❌ {exc}")

    text = (raw_text or "").strip()
    if not text:
        return await reply_message.reply_text("❌ Invalid Telegram message link.")

    segments = [seg.strip() for seg in re.split(r"[\r\n,]+", text) if seg.strip()]
    if not segments:
        return await reply_message.reply_text("❌ Invalid Telegram message link.")

    started = []
    errors = []
    for seg in segments:
        try:
            chat, first_id, last_id, _ = parse_link_or_range(seg)
            tid = await start_task(bot, user_id, chat, first_id, last_id)
            started.append((tid, first_id, last_id))
        except Exception as exc:
            errors.append(f"• <code>{html.escape(seg[:80])}</code>: {html.escape(str(exc))}")

    out_lines = []
    if started:
        for tid, fid, lid in started:
            out_lines.append(f"✅ Index task <code>#{tid.upper()}</code> started (<code>{fid:,}</code> → <code>{lid:,}</code>).")
        out_lines.append("Use /indexstatus to manage tasks.")
    if errors:
        if len(segments) == 1:
            return await reply_message.reply_text(f"❌ {errors[0].split(': ', 1)[-1]}")
        out_lines.append("\n<b>Failed entries:</b>\n" + "\n".join(errors))
    return await reply_message.reply_text("\n".join(out_lines))


async def _prompt_for_index(bot, chat_id, user_id, reply_to_msg=None):
    prompt_text = (
        "<b>📁 START NEW INDEX TASK</b>\n\n"
        "Send one Telegram message link, a range, or multiple ranges (one per line):\n"
        "• <code>https://t.me/c/123456/100-https://t.me/c/123456/500</code>\n"
        "• <code>https://t.me/c/123456/100-500</code>\n"
        "• <code>https://t.me/c/123456/500</code>\n\n"
        "<i>Or forward a message from the channel. Send /cancel to abort.</i>"
    )
    if reply_to_msg:
        prompt = await reply_to_msg.reply_text(prompt_text)
    else:
        prompt = await bot.send_message(chat_id, prompt_text)
    try:
        response = await bot.ask(chat_id, "Waiting for your link/range…", timeout=180)
        resp_text = (response.text or response.caption or "").strip()
        if resp_text.lower() in ("/cancel", "cancel"):
            return await response.reply_text("🛑 Index request cancelled.")
        if resp_text.startswith("/index"):
            resp_text = resp_text.split(maxsplit=1)[1] if len(resp_text.split(maxsplit=1)) > 1 else ""
        await _process_index_submission(bot, user_id, response, raw_text=resp_text, forwarded_msg=response)
    except asyncio.TimeoutError:
        try:
            await prompt.edit_text("⌛ Index request timed out.")
        except Exception:
            pass


@Client.on_message(filters.private & filters.command("index"))
async def index_command(bot, message):
    if not message.from_user or not _is_admin(message.from_user.id):
        return await message.reply_text("Admin access only.")
    args = (message.text or "").split(maxsplit=1)
    if len(args) > 1 and args[1].strip():
        return await _process_index_submission(bot, message.from_user.id, message, raw_text=args[1].strip())
    if message.reply_to_message:
        r = message.reply_to_message
        if getattr(r, "forward_from_chat", None) and getattr(r, "forward_from_message_id", None):
            return await _process_index_submission(bot, message.from_user.id, message, forwarded_msg=r)
        if r.text or r.caption:
            return await _process_index_submission(bot, message.from_user.id, message, raw_text=(r.text or r.caption))
    await _prompt_for_index(bot, message.chat.id, message.from_user.id, reply_to_msg=message)


@Client.on_message(filters.private & filters.command(["indexstatus", "index_status", "tasks"]))
async def index_status(bot, message):
    if not message.from_user or not _is_admin(message.from_user.id):
        return await message.reply_text("Admin access only.")
    text, markup = _tasks_overview_text_and_markup()
    await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)


@Client.on_message(filters.private & filters.command(["cancelindex", "stopindex"]))
async def cancel_index_command(bot, message):
    if not message.from_user or not _is_admin(message.from_user.id):
        return await message.reply_text("Admin access only.")
    args = (message.text or "").split(maxsplit=1)
    target = args[1].strip().lstrip("#").lower() if len(args) > 1 else "all"
    cancelled = []
    for tid, t in list(TASKS.items()):
        if target in ("all", tid.lower(), t["short"].lower()):
            if _cancel_task_now(t):
                cancelled.append(f"#{t['short']}")
                await _notify_task_messages(bot, t)
    if not cancelled:
        return await message.reply_text("⚠️ No matching running/paused index tasks found to cancel.")
    return await message.reply_text(f"🛑 Cancelled index task(s): <code>{', '.join(cancelled)}</code>")


@Client.on_callback_query(
    filters.regex(r"^idxctl:(view|cancel|pause|resume|popup|rerun|continue|delete|list|clear|cancelall|pauseall|resumeall|new):([A-Za-z0-9_]+)$"),
    group=-1,
)
async def index_controls(bot, query):
    if not query.from_user or not _is_admin(query.from_user.id):
        return await query.answer("Admin access only.", show_alert=True)
    _, action, task_id = query.data.split(":", 2)

    if action == "new":
        await query.answer("Send your Telegram message link or range.")
        asyncio.create_task(_prompt_for_index(bot, query.message.chat.id, query.from_user.id))
        return

    if action == "list":
        text, markup = _tasks_overview_text_and_markup()
        await query.answer("Task list updated.")
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    if action == "clear":
        removed = 0
        for tid, t in list(TASKS.items()):
            if t["status"] in ("COMPLETED", "CANCELLED", "FAILED"):
                TASKS.pop(tid, None)
                removed += 1
        text, markup = _tasks_overview_text_and_markup()
        await query.answer(f"Cleared {removed} finished task(s).", show_alert=True)
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    if action == "cancelall":
        count = 0
        for t in list(TASKS.values()):
            if _cancel_task_now(t):
                count += 1
                await _notify_task_messages(bot, t)
        text, markup = _tasks_overview_text_and_markup()
        await query.answer(f"Cancelled {count} task(s).", show_alert=True)
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    if action == "pauseall":
        count = 0
        for t in list(TASKS.values()):
            if t["status"] == "RUNNING":
                t["pause_event"].clear()
                t["status"] = "PAUSED"
                count += 1
                await _notify_task_messages(bot, t)
        text, markup = _tasks_overview_text_and_markup()
        await query.answer(f"Paused {count} task(s).")
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    if action == "resumeall":
        count = 0
        for t in list(TASKS.values()):
            if t["status"] == "PAUSED":
                t["status"] = "RUNNING"
                t["pause_event"].set()
                count += 1
                await _notify_task_messages(bot, t)
        text, markup = _tasks_overview_text_and_markup()
        await query.answer(f"Resumed {count} task(s).")
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    t = TASKS.get(task_id)
    if not t:
        text, markup = _tasks_overview_text_and_markup()
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except Exception:
            pass
        return await query.answer("Task not found or already removed.", show_alert=True)

    t.setdefault("viewers", set()).add((query.message.chat.id, query.message.id))

    if action == "popup":
        total_range = max(1, int(t["last"] - t["first"] + 1))
        pct = min(100.0, (t["processed"] / total_range) * 100.0) if t["status"] != "COMPLETED" else 100.0
        summary = (
            f"📁 Task #{t['short']} ({t['status']})\n"
            f"Progress: {pct:.1f}% ({t['processed']:,}/{total_range:,})\n"
            f"Saved: {t['saved']:,} | Dup: {t['duplicates']:,}\n"
            f"Deleted: {t['deleted']:,} | Skipped: {t['skipped']:,} | Err: {t['errors']:,}"
        )
        return await query.answer(summary[:200], show_alert=True)

    if action == "cancel":
        if not _cancel_task_now(t):
            return await query.answer(f"Task is already {t['status'].lower()}.", show_alert=True)
        await query.answer("🛑 Index task cancelled!", show_alert=True)
        await _notify_task_messages(bot, t)
        return

    if action == "pause":
        if t["status"] != "RUNNING":
            return await query.answer(f"Cannot pause task in {t['status']} state.", show_alert=True)
        t["pause_event"].clear()
        t["status"] = "PAUSED"
        await query.answer("⏸ Task paused.")
        await _notify_task_messages(bot, t)
        return

    if action == "resume":
        if t["status"] != "PAUSED":
            return await query.answer(f"Task is {t['status'].lower()}.", show_alert=True)
        t["status"] = "RUNNING"
        t["pause_event"].set()
        await query.answer("▶️ Task resumed.")
        await _notify_task_messages(bot, t)
        return

    if action == "rerun":
        try:
            new_id = await start_task(bot, query.from_user.id, t["chat"], t["first"], t["last"])
            await query.answer(f"Started new task #{new_id.upper()}!", show_alert=True)
            new_t = TASKS[new_id]
            new_t.setdefault("viewers", set()).add((query.message.chat.id, query.message.id))
            await query.message.edit_text(status_text(new_t), reply_markup=controls(new_id), disable_web_page_preview=True)
        except Exception as exc:
            await query.answer(str(exc)[:180], show_alert=True)
        return

    if action == "continue":
        resume_from = max(t["first"], int(t.get("current", t["first"])))
        if resume_from > t["last"]:
            return await query.answer("No remaining messages in range.", show_alert=True)
        try:
            new_id = await start_task(bot, query.from_user.id, t["chat"], resume_from, t["last"])
            await query.answer(f"Continuing in task #{new_id.upper()} from {resume_from}!", show_alert=True)
            new_t = TASKS[new_id]
            new_t.setdefault("viewers", set()).add((query.message.chat.id, query.message.id))
            await query.message.edit_text(status_text(new_t), reply_markup=controls(new_id), disable_web_page_preview=True)
        except Exception as exc:
            await query.answer(str(exc)[:180], show_alert=True)
        return

    if action == "delete":
        _cancel_task_now(t)
        TASKS.pop(task_id, None)
        text, markup = _tasks_overview_text_and_markup()
        await query.answer("Task removed.")
        try:
            await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
        except MessageNotModified:
            pass
        return

    await query.answer("Task status updated.")
    try:
        await query.message.edit_text(status_text(t), reply_markup=controls(task_id), disable_web_page_preview=True)
    except MessageNotModified:
        pass


@Client.on_callback_query(filters.regex(r"^index#"), group=-1)
async def legacy_index_callback(bot, query):
    if not query.from_user or not _is_admin(query.from_user.id):
        return await query.answer("Admin access only.", show_alert=True)
    try:
        _, action, chat, msg_id, requester = query.data.split("#")
        if action == "reject":
            await query.message.delete()
            return await bot.send_message(int(requester), "Your indexing request was declined.")
        start_from = max(1, int(getattr(temp, "CURRENT", 1) or 1))
        if start_from == 2 and "SKIP" not in __import__("os").environ:
            start_from = 1
        task_id = await start_task(bot, query.from_user.id, chat, start_from, int(msg_id))
        await query.answer(f"Index task #{task_id.upper()} started.", show_alert=True)
        await query.message.edit_text(f"✅ Accepted. Index task <code>#{task_id.upper()}</code> started.")
    except Exception as exc:
        await query.answer(str(exc)[:180], show_alert=True)
