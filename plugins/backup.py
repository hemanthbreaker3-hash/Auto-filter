"""Compressed MongoDB backup and restore for TGBOXOFFICE."""
import asyncio
import gzip
import os
import tempfile
import zipfile
import shutil
import hashlib
from datetime import datetime, timezone

from bson import json_util
from pymongo import MongoClient
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from database.mongo_nodes import all_node_uris

# Per-admin interactive import state. Pending files are kept only until confirmation/cancel.
_WAITING_IMPORT = set()
_PENDING_RESTORE = {}

def _authorized(message):
    return bool(message.from_user and message.from_user.id in info.ADMINS)


def _database_targets():
    # Cover the bot's configured user, file, secondary-file and auxiliary stores.
    targets = []
    seen = set()
    for uri in (info.USER_DB_URI, info.FILE_DB_URI, info.SEC_FILE_DB_URI, info.OTHER_DB_URI, info.CLONE_DATABASE_URI):
        if not uri:
            continue
        for db_name in (info.DATABASE_NAME, "referal_user", "JoinReqs"):
            key = (uri, db_name)
            if key not in seen:
                seen.add(key)
                targets.append((uri, db_name))
    # Include every registered panel-managed file database in both backup and restore.
    for _node_id, uri, _label, _enabled in all_node_uris():
        key = (uri, info.DATABASE_NAME)
        if key not in seen:
            seen.add(key)
            targets.append(key)
    return targets


def _make_backup(path):
    """Stream all configured collections to gzip to avoid loading the whole DB into RAM."""
    collections_count = documents_count = 0
    targets = _database_targets()
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write('{"format":"TGBOXOFFICE-MONGO-BACKUP","version":1,')
        stream.write('"created_at":' + json_util.dumps(datetime.now(timezone.utc).isoformat()) + ',"databases":[')
        first_database = True
        for target_index, (uri, db_name) in enumerate(targets):
            client = MongoClient(uri, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
            try:
                database = client[db_name]
                names = database.list_collection_names()
                if not names:
                    continue
                if not first_database:
                    stream.write(',')
                first_database = False
                target_key = hashlib.sha256(uri.encode("utf-8")).hexdigest()
                stream.write('{"target_index":' + str(target_index) + ',"target_key":' + json_util.dumps(target_key) + ',"name":' + json_util.dumps(db_name) + ',"collections":[')
                first_collection = True
                for name in names:
                    if not first_collection:
                        stream.write(',')
                    first_collection = False
                    stream.write('{"name":' + json_util.dumps(name) + ',"documents":[')
                    first_document = True
                    cursor = database[name].find({}).batch_size(500)
                    for document in cursor:
                        if not first_document:
                            stream.write(',')
                        first_document = False
                        stream.write(json_util.dumps(document, ensure_ascii=False))
                        documents_count += 1
                    stream.write(']}')
                    collections_count += 1
                stream.write(']}')
            finally:
                client.close()
        stream.write(']}')
    return collections_count, documents_count


def _restore_backup(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        snapshot = json_util.loads(stream.read())
    if snapshot.get("format") != "TGBOXOFFICE-MONGO-BACKUP" or snapshot.get("version") != 1:
        raise ValueError("Unsupported or invalid TGBOXOFFICE backup file.")
    targets = _database_targets()
    restored_collections = restored_documents = 0
    for db_data in snapshot.get("databases", []):
        db_name = db_data.get("name")
        target_index = db_data.get("target_index")
        target_key = db_data.get("target_key")
        if target_key:
            match = next((item for item in targets
                          if hashlib.sha256(item[0].encode("utf-8")).hexdigest() == target_key
                          and item[1] == db_name), None)
            if not match:
                continue
            uri, configured_name = match
        else:
            # Backward compatibility with older TGBOXOFFICE backup archives.
            if not isinstance(target_index, int) or not 0 <= target_index < len(targets):
                continue
            uri, configured_name = targets[target_index]
            if configured_name != db_name:
                continue
        client = MongoClient(uri, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
        try:
            database = client[db_name]
            for collection_data in db_data.get("collections", []):
                name = collection_data.get("name")
                if not isinstance(name, str) or not name or name.startswith("system.") or name.startswith("$"):
                    continue
                docs = collection_data.get("documents", [])
                if not isinstance(docs, list):
                    continue
                collection = database[name]
                collection.delete_many({})
                if docs:
                    collection.insert_many(docs, ordered=False)
                restored_collections += 1
                restored_documents += len(docs)
        finally:
            client.close()
    if not restored_collections:
        raise ValueError("No matching configured database collections were found in this backup.")
    return restored_collections, restored_documents


def _validate_backup(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        snapshot = json_util.loads(stream.read())
    if snapshot.get("format") != "TGBOXOFFICE-MONGO-BACKUP" or snapshot.get("version") != 1:
        raise ValueError("Unsupported or invalid TGBOXOFFICE backup file.")
    if not isinstance(snapshot.get("databases"), list):
        raise ValueError("Backup database section is invalid.")
    return snapshot


def _make_zip_backup(zip_path, gzip_path):
    collections, documents = _make_backup(gzip_path)
    if not collections:
        return 0, 0
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        archive.write(gzip_path, arcname="TGBOXOFFICE-backup.json.gz")
    return collections, documents


def _unpack_zip_backup(zip_path, output_path):
    with zipfile.ZipFile(zip_path, "r") as archive:
        candidates = [item for item in archive.infolist()
                      if not item.is_dir() and item.filename == "TGBOXOFFICE-backup.json.gz"]
        if len(candidates) != 1:
            raise ValueError("ZIP must contain exactly one TGBOXOFFICE-backup.json.gz file.")
        item = candidates[0]
        if item.file_size > 1900 * 1024 * 1024:
            raise ValueError("Uncompressed backup is too large.")
        with archive.open(item, "r") as source, open(output_path, "wb") as target:
            shutil.copyfileobj(source, target, length=1024 * 1024)
    _validate_backup(output_path)


def _remove_pending(user_id):
    path = _PENDING_RESTORE.pop(user_id, None)
    if path and os.path.exists(path):
        os.remove(path)


@Client.on_message(filters.command("save") & filters.private)
async def save_menu(client, message):
    if not _authorized(message):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    await message.reply_text(
        "<b>💾 TGBOXOFFICE BACKUP CENTER</b>\n\n"
        "Create a complete database backup or restore your data from a backup ZIP.\n\n"
        "<i>Restore replaces matching collections. Create a fresh backup first.</i>",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("💾 Backup", callback_data="tgbox_save:backup")],
            [InlineKeyboardButton("📥 Import", callback_data="tgbox_save:import")],
        ]))


@Client.on_callback_query(filters.regex(r"^tgbox_save:"))
async def save_callbacks(client, query):
    uid = query.from_user.id
    if uid not in info.ADMINS:
        return await query.answer("Admin access only.", show_alert=True)
    action = query.data.split(":", 1)[1]
    if action == "import":
        _remove_pending(uid)
        _WAITING_IMPORT.add(uid)
        await query.message.reply_text(
            "<b>📥 Send your TGBOXOFFICE backup ZIP now.</b>\n\n"
            "Upload the <code>.zip</code> file as a document in this private chat.\n"
            "I will validate it and ask for confirmation before restoring.")
        return await query.answer("Waiting for backup ZIP")
    if action == "cancel":
        _remove_pending(uid)
        _WAITING_IMPORT.discard(uid)
        await query.message.edit_text("❎ Import cancelled. No database changes were made.")
        return await query.answer("Cancelled")
    if action == "confirm":
        path = _PENDING_RESTORE.get(uid)
        if not path or not os.path.isfile(path):
            _remove_pending(uid)
            return await query.answer("Upload the backup ZIP again; the pending file expired.", show_alert=True)
        await query.answer("Restoring database…")
        status = await query.message.edit_text("<b>⏳ Restoring database backup…</b>")
        try:
            collections, documents = await asyncio.to_thread(_restore_backup, path)
            await status.edit_text(
                f"<b>✅ Restore completed successfully</b>\n\n"
                f"📚 Collections restored: <code>{collections:,}</code>\n"
                f"📄 Documents restored: <code>{documents:,}</code>")
        except Exception as exc:
            await status.edit_text(f"<b>❌ Restore failed:</b> <code>{str(exc)[:700]}</code>")
        finally:
            _remove_pending(uid)
        return
    if action == "backup":
        await query.answer("Creating backup…")
        status = await query.message.reply_text("<b>⏳ Creating compressed database backup ZIP…</b>")
        fd, gzip_path = tempfile.mkstemp(prefix="tgboxoffice-backup-", suffix=".json.gz")
        os.close(fd)
        zip_path = gzip_path[:-7] + ".zip"
        try:
            collections, documents = await asyncio.to_thread(_make_zip_backup, zip_path, gzip_path)
            if not collections:
                return await status.edit_text("⚠️ No database collections were found to back up.")
            await query.message.reply_document(
                zip_path,
                file_name=f"TGBOXOFFICE-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip",
                caption=(f"<b>✅ TGBOXOFFICE backup created</b>\n\n"
                         f"📚 Collections: <code>{collections:,}</code>\n"
                         f"📄 Documents: <code>{documents:,}</code>\n\n"
                         "<i>Keep this file private; it may contain bot and user data.</i>"))
            await status.delete()
        except Exception as exc:
            await status.edit_text(f"<b>❌ Backup failed:</b> <code>{str(exc)[:700]}</code>")
        finally:
            for path in (gzip_path, zip_path):
                if os.path.exists(path):
                    os.remove(path)
        return
    await query.answer("Unknown action.", show_alert=True)


@Client.on_message(filters.private & filters.document, group=-2)
async def receive_backup_document(client, message):
    uid = message.from_user.id if message.from_user else None
    if uid not in info.ADMINS or uid not in _WAITING_IMPORT:
        return
    document = message.document
    if not document.file_name or not document.file_name.lower().endswith(".zip"):
        return await message.reply_text("❌ Please upload a backup <code>.zip</code> document.")
    if document.file_size and document.file_size > 1900 * 1024 * 1024:
        return await message.reply_text("❌ Backup ZIP is too large for this import command.")
    status = await message.reply_text("<b>⏳ Downloading and validating backup ZIP…</b>")
    fd, zip_path = tempfile.mkstemp(prefix="tgboxoffice-import-", suffix=".zip")
    os.close(fd)
    fd, gzip_path = tempfile.mkstemp(prefix="tgboxoffice-import-", suffix=".json.gz")
    os.close(fd)
    try:
        await message.download(file_name=zip_path)
        await asyncio.to_thread(_unpack_zip_backup, zip_path, gzip_path)
        _remove_pending(uid)
        _PENDING_RESTORE[uid] = gzip_path
        gzip_path = None
        _WAITING_IMPORT.discard(uid)
        await status.edit_text(
            "<b>✅ Backup validated.</b>\n\n"
            "⚠️ <b>Confirm database restore?</b> Matching collections will be replaced by the uploaded backup.\n"
            "Create a current backup first if you may need to roll back.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("⚠️ Confirm Restore", callback_data="tgbox_save:confirm")],
                [InlineKeyboardButton("❎ Cancel", callback_data="tgbox_save:cancel")],
            ]))
    except Exception as exc:
        _WAITING_IMPORT.add(uid)
        await status.edit_text(f"<b>❌ Invalid backup ZIP:</b> <code>{str(exc)[:600]}</code>\nYou can upload another ZIP.")
    finally:
        for path in (zip_path, gzip_path):
            if path and os.path.exists(path):
                os.remove(path)


@Client.on_message(filters.command("add") & filters.private, group=-1)
async def database_backup(client, message):
    if not _authorized(message):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    args = message.command[1:]
    action = args[0].lower() if args else "help"
    if action == "save":
        status = await message.reply_text("<b>⏳ Creating compressed database backup…</b>")
        fd, path = tempfile.mkstemp(prefix="tgboxoffice-backup-", suffix=".json.gz")
        os.close(fd)
        try:
            collections, documents = await asyncio.to_thread(_make_backup, path)
            if not collections:
                return await status.edit_text("⚠️ No database collections were found to back up.")
            await message.reply_document(
                path, file_name=f"TGBOXOFFICE-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.json.gz",
                caption=(f"<b>✅ TGBOXOFFICE backup created</b>\n\n"
                         f"📚 Collections: <code>{collections:,}</code>\n"
                         f"📄 Documents: <code>{documents:,}</code>\n"
                         "<i>Keep this file private; it may contain bot and user data.</i>"))
            await status.delete()
        except Exception as exc:
            await status.edit_text(f"<b>❌ Backup failed:</b> <code>{str(exc)[:700]}</code>")
        finally:
            if os.path.exists(path):
                os.remove(path)
        return
    if action == "load":
        reply = message.reply_to_message
        if len(args) < 2 or args[1].lower() != "confirm":
            return await message.reply_text(
                "<b>⚠️ Restore replaces matching collections.</b>\n"
                "Reply to the backup document with <code>/add load confirm</code> to proceed.")
        if not reply or not reply.document:
            return await message.reply_text("Reply to the backup <code>.json.gz</code> document with <code>/add load confirm</code>.")
        if reply.document.file_size and reply.document.file_size > 1900 * 1024 * 1024:
            return await message.reply_text("❌ Backup is too large for this restore command.")
        status = await message.reply_text("<b>⏳ Validating and restoring database backup…</b>")
        fd, path = tempfile.mkstemp(prefix="tgboxoffice-restore-", suffix=".json.gz")
        os.close(fd)
        try:
            await reply.download(file_name=path)
            collections, documents = await asyncio.to_thread(_restore_backup, path)
            await status.edit_text(
                f"<b>✅ Restore completed</b>\n\n📚 Collections: <code>{collections:,}</code>\n"
                f"📄 Documents: <code>{documents:,}</code>")
        except Exception as exc:
            await status.edit_text(f"<b>❌ Restore failed:</b> <code>{str(exc)[:700]}</code>")
        finally:
            if os.path.exists(path):
                os.remove(path)
        return
    # Let the existing /add filter command handle all other /add arguments.
    return
