# TGBoxOffice indexing manager
import asyncio
import logging
import re
import uuid

from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified

from info import ADMINS, INDEX_REQ_CHANNEL as LOG_CHANNEL
from utils import temp
from database.ia_filterdb import save_files_batch

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

TASKS = {}
TASK_LOCK = asyncio.Lock()
LINK_RE = re.compile(r"^(?:https?://)?(?:t\.me|telegram\.me|telegram\.dog)/(?:c/)?([0-9]+|[A-Za-z_0-9]+)/([0-9]+)(?:\?.*)?$")

def parse_link(value):
    match = LINK_RE.match(value.strip().rstrip("/"))
    if not match:
        raise ValueError("Invalid Telegram message link.")
    chat, msg_id = match.group(1), int(match.group(2))
    if chat.isnumeric():
        chat = int("-100" + chat)
    return chat, msg_id

def controls(task_id):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 View progress", callback_data=f"idxctl:view:{task_id}"),
         InlineKeyboardButton("✖ Cancel", callback_data=f"idxctl:cancel:{task_id}")],
    ])

def status_text(t):
    return (
        f"<b>📁 INDEX TASK #{t['short']}</b>\n\n"
        f"Status: <b>{t['status']}</b>\n"
        f"Messages scanned: <code>{t['processed']:,}</code>\n"
        f"Files saved: <code>{t['saved']:,}</code>\n"
        f"Duplicates: <code>{t['duplicates']:,}</code>\n"
        f"Deleted: <code>{t['deleted']:,}</code>\n"
        f"Non-media: <code>{t['skipped']:,}</code>\n"
        f"Errors: <code>{t['errors']:,}</code>"
    )

async def run_index(bot, task_id, chat, first_id, last_id, status_msg):
    t = TASKS[task_id]
    batch = []
    last_update = 0
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
        except Exception:
            logger.exception("Index batch write failed")
            t["errors"] += len(pending)

    async def update(force=False):
        nonlocal last_update
        now = asyncio.get_running_loop().time()
        if not force and now - last_update < 4:
            return
        last_update = now
        try:
            await status_msg.edit_text(status_text(t), reply_markup=controls(task_id) if t["status"] == "RUNNING" else None)
        except MessageNotModified:
            pass
        except Exception:
            logger.debug("Unable to update index status", exc_info=True)

    t["status"] = "RUNNING"
    await update(True)
    try:
        async for msg in bot.iter_messages(chat, last_id, first_id):
            if t["cancel"]:
                break
            t["processed"] += 1
            if msg.empty:
                t["deleted"] += 1
            elif not msg.media:
                t["skipped"] += 1
            elif msg.media not in (enums.MessageMediaType.VIDEO, enums.MessageMediaType.AUDIO, enums.MessageMediaType.DOCUMENT):
                t["skipped"] += 1
            else:
                media = getattr(msg, msg.media.value, None)
                if media and getattr(media, "file_id", None):
                    media.caption = msg.caption
                    batch.append(media)
                    if len(batch) >= 100:
                        await flush()
                else:
                    t["skipped"] += 1
            if t["processed"] % 100 == 0:
                await flush()
                await update()
        await flush()
        t["status"] = "CANCELLED" if t["cancel"] else "COMPLETED"
    except Exception as exc:
        await flush()
        t["status"] = "FAILED"
        t["error"] = str(exc)[:300]
        logger.exception("Index task failed")
    await update(True)
    if t.get("error"):
        try:
            await status_msg.edit_text(status_text(t) + f"\n\n<code>{t['error']}</code>")
        except Exception:
            pass

async def start_task(bot, user_id, chat, first_id, last_id):
    try:
        chat_obj = await bot.get_chat(chat)
        chat = chat_obj.id
        await bot.get_messages(chat, last_id)
    except ChannelInvalid:
        raise ValueError("This may be a private channel/group. Add the bot as an admin first.")
    except (UsernameInvalid, UsernameNotModified):
        raise ValueError("Invalid channel or message link.")
    except Exception as exc:
        raise ValueError(f"Cannot access the channel/messages: {exc}")
    task_id = uuid.uuid4().hex[:8]
    status_msg = await bot.send_message(user_id, f"Starting index task <code>{task_id}</code>…")
    TASKS[task_id] = {
        "id": task_id, "short": task_id.upper(), "user": user_id, "chat": chat,
        "first": first_id, "last": last_id, "status": "QUEUED", "cancel": False,
        "processed": 0, "saved": 0, "duplicates": 0, "deleted": 0,
        "skipped": 0, "errors": 0, "message": status_msg,
    }
    TASKS[task_id]["runner"] = asyncio.create_task(run_index(bot, task_id, chat, first_id, last_id, status_msg))
    return task_id

@Client.on_message(filters.private & filters.command("index"))
async def index_command(bot, message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return await message.reply_text("Admin access only.")
    args = message.text.split(maxsplit=1)
    if len(args) > 1:
        value = args[1].strip()
        parts = re.split(r"(?=https?://(?:t\\.me|telegram\\.me|telegram\\.dog)/)", value)
        try:
            if len(parts) == 1:
                first_chat, first_id = parse_link(parts[0])
                last_chat, last_id = first_chat, first_id
            elif len(parts) == 2:
                first_chat, first_id = parse_link(parts[0].rstrip("-"))
                last_chat, last_id = parse_link(parts[1])
            else:
                raise ValueError("Invalid range. Send two Telegram message links separated by a hyphen.")
            if first_chat != last_chat:
                return await message.reply_text("Both links must belong to the same channel/group.")
            if first_id > last_id:
                first_id, last_id = last_id, first_id
            task_id = await start_task(bot, message.from_user.id, first_chat, first_id, last_id)
            return await message.reply_text(f"✅ Index task <code>{task_id}</code> started.\\nUse /indexstatus to manage tasks.")
        except Exception as exc:
            return await message.reply_text(f"❌ {exc}")
    prompt = await message.reply_text(
        "Send one Telegram message link or a range:\n"
        "<code>https://t.me/c/123456/100-https://t.me/c/123456/500</code>"
    )
    try:
        response = await bot.ask(message.chat.id, "Waiting for your link/range…", timeout=120)
        fake = type("M", (), {"text": "/index " + (response.text or ""), "from_user": message.from_user,
                               "reply_text": response.reply_text, "chat": message.chat})()
        await index_command(bot, fake)
    except asyncio.TimeoutError:
        await prompt.edit_text("⌛ Index request timed out.")

@Client.on_message(filters.private & filters.command("indexstatus"))
async def index_status(bot, message):
    if not message.from_user or message.from_user.id not in ADMINS:
        return await message.reply_text("Admin access only.")
    tasks = list(TASKS.values())
    if not tasks:
        return await message.reply_text("No indexing tasks found.")
    rows = []
    for t in tasks[-20:]:
        rows.append([InlineKeyboardButton(
            f"{'🟢' if t['status']=='RUNNING' else '⚪'} {t['short']} · {t['status']} · {t['saved']} saved",
            callback_data=f"idxctl:view:{t['id']}"
        )])
    await message.reply_text("📊 <b>INDEX TASKS</b>\nSelect a task to view progress and actions:", reply_markup=InlineKeyboardMarkup(rows))

@Client.on_callback_query(filters.regex(r"^idxctl:(view|cancel):([a-f0-9]+)$"))
async def index_controls(bot, query):
    if not query.from_user or query.from_user.id not in ADMINS:
        return await query.answer("Admin access only.", show_alert=True)
    _, action, task_id = query.data.split(":")
    t = TASKS.get(task_id)
    if not t:
        return await query.answer("Task not found or bot restarted.", show_alert=True)
    if action == "cancel":
        if t["status"] != "RUNNING":
            return await query.answer(f"Task is already {t['status'].lower()}.", show_alert=True)
        t["cancel"] = True
        await query.answer("Cancellation requested. The current batch will be saved.")
        try:
            await query.message.edit_text(status_text(t) + "\n\n⏳ Cancellation requested…")
        except Exception:
            pass
        return
    await query.answer("Task status updated.")
    await query.message.edit_text(status_text(t), reply_markup=controls(task_id) if t["status"] == "RUNNING" else None)

# Legacy moderator request callback compatibility.
@Client.on_callback_query(filters.regex(r"^index#"))
async def legacy_index_callback(bot, query):
    if query.from_user.id not in ADMINS:
        return await query.answer("Admin access only.", show_alert=True)
    try:
        _, action, chat, msg_id, requester = query.data.split("#")
        if action == "reject":
            await query.message.delete()
            return await bot.send_message(int(requester), "Your indexing request was declined.")
        task_id = await start_task(bot, query.from_user.id, chat, int(msg_id), int(msg_id))
        await query.answer(f"Index task {task_id} started.", show_alert=True)
        await query.message.edit_text(f"Accepted. Task <code>{task_id}</code> started.")
    except Exception as exc:
        await query.answer(str(exc)[:180], show_alert=True)
