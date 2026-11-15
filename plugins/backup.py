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
from pymongo.errors import BulkWriteError
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from database.mongo_nodes import all_node_uris
from TechVJ.util.telegram_rich import ButtonStyle

# Per-admin interactive import state.
_WAITING_IMPORT = set()
_PENDING_RESTORE = {}
_IMPORT_LOCKS = {}


def _authorized(message):
    return bool(message.from_user and message.from_user.id in info.ADMINS)


def _database_targets():
    # Cover the bot's configured user, file, secondary-file and auxiliary stores.
    targets = []
    seen = set()
    for uri in (info.USER_DB_URI, info.FILE_DB_URI, info.SEC_FILE_DB_URI, info.OTHER_DB_URI, info.CLONE_DATABASE_URI, info.DATABASE_URI):
        if not uri:
            continue
        db_names = [info.DATABASE_NAME, "referal_user", "JoinReqs"]
        try:
            from urllib.parse import urlsplit
            path_db = urlsplit(uri).path.lstrip("/").split("/")[0].strip()
            if path_db and path_db not in db_names:
                db_names.insert(0, path_db)
        except Exception:
            pass
        for db_name in db_names:
            if not db_name:
                continue
            key = (uri, db_name)
            if key not in seen:
                seen.add(key)
                targets.append((uri, db_name))
    # Include every registered panel-managed file database in both backup and restore.
    try:
        for _node_id, uri, _label, _enabled in all_node_uris():
            if not uri:
                continue
            key = (uri, info.DATABASE_NAME)
            if key not in seen:
                seen.add(key)
                targets.append(key)
    except Exception:
        pass
    return targets


def _make_backup(path):
    """Export all accessible configured collections to gzip JSON safely."""
    collections_count = documents_count = 0
    targets = _database_targets()
    databases_payload = []

    for target_index, (uri, db_name) in enumerate(targets):
        client = None
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=12000, connectTimeoutMS=12000)
            database = client[db_name]
            names = [
                n for n in database.list_collection_names()
                if isinstance(n, str) and n and not n.startswith("system.") and not n.startswith("$")
            ]
            if not names:
                continue
            target_key = hashlib.sha256(uri.encode("utf-8")).hexdigest()
            col_entries = []
            for name in names:
                try:
                    docs = list(database[name].find({}).batch_size(500))
                except Exception as col_exc:
                    print(f"[Backup] Skipping unreadable collection {db_name}.{name}: {col_exc}")
                    continue
                col_entries.append({
                    "name": name,
                    "documents": docs,
                })
                collections_count += 1
                documents_count += len(docs)
            if col_entries:
                databases_payload.append({
                    "target_index": target_index,
                    "target_key": target_key,
                    "name": db_name,
                    "collections": col_entries,
                })
        except Exception as db_exc:
            print(f"[Backup] Skipping unreachable or unauthorized target ({db_name}): {db_exc}")
            continue
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    pass

    snapshot = {
        "format": "TGBOXOFFICE-MONGO-BACKUP",
        "version": 1,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "databases": databases_payload,
    }
    with gzip.open(path, "wt", encoding="utf-8") as stream:
        stream.write(json_util.dumps(snapshot, ensure_ascii=False))
    return collections_count, documents_count


def _read_snapshot_file(path):
    """Read a backup snapshot from .json.gz, .gz,plain .json, or .zip."""
    if zipfile.is_zipfile(path):
        fd, temp_out = tempfile.mkstemp(prefix="tgboxoffice-unpack-", suffix=".json.gz")
        os.close(fd)
        try:
            _unpack_zip_backup(path, temp_out)
            return _read_snapshot_file(temp_out)
        finally:
            if os.path.exists(temp_out):
                os.remove(temp_out)
    try:
        with gzip.open(path, "rt", encoding="utf-8") as stream:
            raw = stream.read()
    except OSError:
        with open(path, "rt", encoding="utf-8") as stream:
            raw = stream.read()
    snapshot = json_util.loads(raw)
    if isinstance(snapshot, list):
        # Support raw collection document list backups as well
        snapshot = {
            "format": "TGBOXOFFICE-MONGO-BACKUP",
            "version": 1,
            "databases": [{
                "name": info.DATABASE_NAME,
                "collections": [{"name": info.COLLECTION_NAME, "documents": snapshot}],
            }],
        }
    return snapshot


def _resolve_restore_target(db_data, targets):
    """Resolve the destination (uri, db_name) even if the bot's MongoDB URI or DB name changed."""
    db_name = db_data.get("name") or info.DATABASE_NAME
    target_index = db_data.get("target_index")
    target_key = db_data.get("target_key")

    # 1. Exact URI hash + db_name match
    if target_key:
        match = next(
            (item for item in targets
             if hashlib.sha256(item[0].encode("utf-8")).hexdigest() == target_key
             and item[1] == db_name),
            None,
        )
        if match:
            return match
        # Same URI hash, fallback to primary DATABASE_NAME
        match_uri = next(
            (item for item in targets
             if hashlib.sha256(item[0].encode("utf-8")).hexdigest() == target_key),
            None,
        )
        if match_uri:
            return (match_uri[0], db_name if db_name in ("referal_user", "JoinReqs") else info.DATABASE_NAME)

    # 2. Target index match
    if isinstance(target_index, int) and 0 <= target_index < len(targets):
        uri, configured_name = targets[target_index]
        if configured_name == db_name:
            return uri, configured_name

    # 3. Auxiliary database name match (referal_user, JoinReqs)
    if db_name in ("referal_user", "JoinReqs"):
        aux_uri = info.OTHER_DB_URI or info.USER_DB_URI or info.DATABASE_URI or (targets[0][0] if targets else None)
        if aux_uri:
            return aux_uri, db_name

    # 4. Exact db_name match on any configured URI
    match_name = next((item for item in targets if item[1] == db_name), None)
    if match_name:
        return match_name

    # 5. Fallback to the primary configured database so backups from another cluster/DB name always restore
    primary_uri = info.USER_DB_URI or info.FILE_DB_URI or info.DATABASE_URI or (targets[0][0] if targets else None)
    if primary_uri:
        return primary_uri, info.DATABASE_NAME
    return None


def _insert_docs_safely(collection, docs):
    collection.delete_many({})
    if not docs:
        return 0
    try:
        res = collection.insert_many(docs, ordered=False)
        return len(res.inserted_ids)
    except BulkWriteError as bwe:
        details = bwe.details or {}
        if "nInserted" in details:
            return int(details["nInserted"])
        write_errors = details.get("writeErrors", [])
        return max(0, len(docs) - len(write_errors))


def _restore_backup(path):
    snapshot = _validate_backup(path)
    targets = _database_targets()
    if not targets:
        raise ValueError("No MongoDB database URI is configured on this bot.")

    restored_collections = restored_documents = 0
    for db_data in snapshot.get("databases", []):
        resolved = _resolve_restore_target(db_data, targets)
        if not resolved:
            continue
        uri, target_db_name = resolved
        client = MongoClient(uri, serverSelectionTimeoutMS=15000, connectTimeoutMS=15000)
        try:
            database = client[target_db_name]
            for collection_data in db_data.get("collections", []):
                name = collection_data.get("name")
                if not isinstance(name, str) or not name or name.startswith("system.") or name.startswith("$"):
                    continue
                docs = collection_data.get("documents", [])
                if not isinstance(docs, list):
                    continue
                try:
                    inserted = _insert_docs_safely(database[name], docs)
                    restored_collections += 1
                    restored_documents += inserted
                    # If this collection holds indexed media files under a legacy collection name,
                    # mirror it into info.COLLECTION_NAME on the primary file DB so searches find them immediately.
                    if (
                        docs
                        and isinstance(docs[0], dict)
                        and "file_id" in docs[0]
                        and "file_name" in docs[0]
                        and name != info.COLLECTION_NAME
                    ):
                        _insert_docs_safely(database[info.COLLECTION_NAME], docs)
                except Exception as col_exc:
                    print(f"[Restore] Error restoring collection {target_db_name}.{name}: {col_exc}")
        finally:
            client.close()

    if not restored_collections:
        raise ValueError("No valid collections were found in this backup archive.")
    return restored_collections, restored_documents


def _validate_backup(path):
    snapshot = _read_snapshot_file(path)
    if not isinstance(snapshot, dict):
        raise ValueError("Unsupported or invalid backup file.")
    if snapshot.get("format") not in (None, "MOVIESZONEFLIX-MONGO-BACKUP", "TGBOXOFFICE-MONGO-BACKUP"):
        raise ValueError("Unsupported or invalid MoviesZoneFlix backup file.")
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
    if zipfile.is_zipfile(zip_path):
        with zipfile.ZipFile(zip_path, "r") as archive:
            members = [item for item in archive.infolist() if not item.is_dir()]
            if not members:
                raise ValueError("Uploaded ZIP archive is empty.")
            preferred = [
                item for item in members
                if os.path.basename(item.filename) == "TGBOXOFFICE-backup.json.gz"
            ]
            if not preferred:
                preferred = [
                    item for item in members
                    if item.filename.lower().endswith((".json.gz", ".gz", ".json"))
                ]
            if not preferred:
                preferred = members
            item = preferred[0]
            if item.file_size > 1900 * 1024 * 1024:
                raise ValueError("Uncompressed backup is too large.")
            with archive.open(item, "r") as source, open(output_path, "wb") as target:
                shutil.copyfileobj(source, target, length=1024 * 1024)
    else:
        shutil.copyfile(zip_path, output_path)
    _validate_backup(output_path)


def _remove_pending(user_id):
    path = _PENDING_RESTORE.pop(user_id, None)
    if path and os.path.exists(path):
        try:
            os.remove(path)
        except Exception:
            pass


async def _refresh_runtime_admins():
    """Reload database-managed admins into info.ADMINS after a backup restore."""
    try:
        from database.users_chats_db import db
        for admin_id in await db.get_admins():
            if admin_id not in info.ADMINS:
                info.ADMINS.append(admin_id)
            if admin_id not in info.AUTH_USERS:
                info.AUTH_USERS.append(admin_id)
    except Exception:
        pass


def _save_menu_markup():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("💾 Backup", callback_data="tgbox_save:backup", style=ButtonStyle.SUCCESS)],
        [InlineKeyboardButton("📥 Import", callback_data="tgbox_save:import", style=ButtonStyle.PRIMARY)],
    ])


async def _process_uploaded_backup_message(client, message, uid):
    """Download, unpack, and immediately restore the database from a backup message."""
    lock = _IMPORT_LOCKS.setdefault(uid, asyncio.Lock())
    async with lock:
        document = getattr(message, "document", None)
        if not document and getattr(message, "reply_to_message", None):
            document = getattr(message.reply_to_message, "document", None)
            if document:
                message = message.reply_to_message
        if not document:
            return await message.reply_text(
                "❌ Please upload your backup <code>.zip</code> file as a document.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❎ Cancel", callback_data="tgbox_save:cancel", style=ButtonStyle.DANGER)]
                ]),
            )
        fname = (document.file_name or "").lower()
        if not fname.endswith((".zip", ".gz", ".json")):
            return await message.reply_text(
                "❌ Please upload a valid backup <code>.zip</code> (or <code>.json.gz</code>) document.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❎ Cancel", callback_data="tgbox_save:cancel", style=ButtonStyle.DANGER)]
                ]),
            )
        if document.file_size and document.file_size > 1900 * 1024 * 1024:
            return await message.reply_text("❌ Backup ZIP is too large for this import command.")

        _WAITING_IMPORT.discard(uid)
        _remove_pending(uid)
        status = await message.reply_text("<b>⏳ Receiving backup ZIP and restoring database…</b>")
        fd, zip_path = tempfile.mkstemp(prefix="tgboxoffice-import-", suffix=os.path.splitext(fname)[1] or ".zip")
        os.close(fd)
        fd, gzip_path = tempfile.mkstemp(prefix="tgboxoffice-import-", suffix=".json.gz")
        os.close(fd)
        try:
            await message.download(file_name=zip_path)
            await asyncio.to_thread(_unpack_zip_backup, zip_path, gzip_path)
            collections, documents = await asyncio.to_thread(_restore_backup, gzip_path)
            await _refresh_runtime_admins()
            await status.edit_text(
                f"<b>✅ Backup restored successfully!</b>\n\n"
                f"📚 Collections restored: <code>{collections:,}</code>\n"
                f"📄 Documents restored: <code>{documents:,}</code>",
                reply_markup=_save_menu_markup(),
            )
        except Exception as exc:
            _WAITING_IMPORT.add(uid)
            await status.edit_text(
                f"<b>❌ Import/Restore failed:</b> <code>{str(exc)[:600]}</code>\n\n"
                "Please upload a valid MoviesZoneFlix backup <code>.zip</code> file or click Cancel.",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❎ Cancel", callback_data="tgbox_save:cancel", style=ButtonStyle.DANGER)]
                ]),
            )
        finally:
            for p in (zip_path, gzip_path):
                if p and os.path.exists(p):
                    try:
                        os.remove(p)
                    except Exception:
                        pass


async def _ask_and_restore_zip(client, chat_id, uid):
    """Interactive client.ask listener for backup ZIP import."""
    try:
        response = await client.ask(
            chat_id,
            "<b>📥 Waiting for your backup <code>.zip</code> file…</b>\n<i>Send /cancel to abort.</i>",
            timeout=300,
        )
    except asyncio.TimeoutError:
        if uid in _WAITING_IMPORT:
            _WAITING_IMPORT.discard(uid)
            try:
                await client.send_message(chat_id, "⌛ Import timed out. Use <code>/save</code> and click Import to try again.")
            except Exception:
                pass
        return
    except Exception:
        return

    if uid not in _WAITING_IMPORT:
        # Already handled by receive_backup_document or cancelled
        return

    text = (getattr(response, "text", None) or getattr(response, "caption", None) or "").strip()
    if text.lower() in ("/cancel", "cancel"):
        _WAITING_IMPORT.discard(uid)
        _remove_pending(uid)
        return await response.reply_text("❎ Import cancelled. No database changes were made.")

    if getattr(response, "document", None):
        await _process_uploaded_backup_message(client, response, uid)


@Client.on_message(filters.command(["save", "import"]) & filters.private)
async def save_menu(client, message):
    if not _authorized(message):
        return await message.reply_text("<b>⛔ Admin access only.</b>")
    # If admin replied directly to a backup .zip/.json.gz with /save or /import, restore immediately
    if message.reply_to_message and getattr(message.reply_to_message, "document", None):
        return await _process_uploaded_backup_message(client, message.reply_to_message, message.from_user.id)
    await message.reply_text(
        "<b>💾 MOVIESZONEFLIX BACKUP CENTER</b>\n\n"
        "Create a complete database backup ZIP or import & restore your data from a backup ZIP.",
        reply_markup=_save_menu_markup(),
    )


@Client.on_callback_query(filters.regex(r"^tgbox_save:"), group=-1)
async def save_callbacks(client, query):
    uid = query.from_user.id
    if uid not in info.ADMINS:
        return await query.answer("Admin access only.", show_alert=True)
    action = query.data.split(":", 1)[1]
    if action == "import":
        _remove_pending(uid)
        _WAITING_IMPORT.add(uid)
        await query.answer("Send your backup ZIP file now.")
        await query.message.reply_text(
            "<b>📥 Send your MoviesZoneFlix backup ZIP now.</b>\n\n"
            "Upload the <code>.zip</code> backup file as a document in this private chat.\n"
            "As soon as the bot receives the ZIP, it will restore your database automatically.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❎ Cancel", callback_data="tgbox_save:cancel", style=ButtonStyle.DANGER)],
            ]),
        )
        asyncio.create_task(_ask_and_restore_zip(client, query.message.chat.id, uid))
        return
    if action == "cancel":
        _remove_pending(uid)
        _WAITING_IMPORT.discard(uid)
        await query.message.edit_text(
            "❎ Import cancelled. No database changes were made.",
            reply_markup=_save_menu_markup(),
        )
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
            await _refresh_runtime_admins()
            await status.edit_text(
                f"<b>✅ Restore completed successfully</b>\n\n"
                f"📚 Collections restored: <code>{collections:,}</code>\n"
                f"📄 Documents restored: <code>{documents:,}</code>",
                reply_markup=_save_menu_markup(),
            )
        except Exception as exc:
            await status.edit_text(
                f"<b>❌ Restore failed:</b> <code>{str(exc)[:700]}</code>",
                reply_markup=_save_menu_markup(),
            )
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
                return await status.edit_text(
                    "⚠️ No database collections were found to back up.",
                    reply_markup=_save_menu_markup(),
                )
            await query.message.reply_document(
                zip_path,
                file_name=f"TGBOXOFFICE-backup-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}.zip",
                caption=(f"<b>✅ MoviesZoneFlix backup created</b>\n\n"
                         f"📚 Collections: <code>{collections:,}</code>\n"
                         f"📄 Documents: <code>{documents:,}</code>\n\n"
                         "<i>Use /save → Import and send this ZIP to restore your data anytime.</i>"),
                reply_markup=_save_menu_markup(),
            )
            await status.delete()
        except Exception as exc:
            await status.edit_text(
                f"<b>❌ Backup failed:</b> <code>{str(exc)[:700]}</code>",
                reply_markup=_save_menu_markup(),
            )
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
    await _process_uploaded_backup_message(client, message, uid)


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
                caption=(f"<b>✅ MoviesZoneFlix backup created</b>\n\n"
                         f"📚 Collections: <code>{collections:,}</code>\n"
                         f"📄 Documents: <code>{documents:,}</code>\n"
                         "<i>Keep this file private; it may contain bot and user data.</i>"),
                reply_markup=_save_menu_markup(),
            )
            await status.delete()
        except Exception as exc:
            await status.edit_text(f"<b>❌ Backup failed:</b> <code>{str(exc)[:700]}</code>")
        finally:
            if os.path.exists(path):
                os.remove(path)
        return
    if action == "load":
        reply = message.reply_to_message
        if not reply or not reply.document:
            return await message.reply_text("Reply to the backup <code>.zip</code> or <code>.json.gz</code> document with <code>/add load</code>.")
        return await _process_uploaded_backup_message(client, reply, message.from_user.id)
    # Let the existing /add filter command handle all other /add arguments.
    return
