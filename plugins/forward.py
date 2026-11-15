"""User-session based batch forwarding.

Session strings are encrypted (Fernet) and stored in MongoDB.
The user account session is used only for /forward so private channels
and channels the bot is not in can still be read/forwarded.
"""
import asyncio
import base64
import hashlib
import logging
import re
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from pyrogram import Client, filters
from pyrogram.errors import (
    FloodWait,
    PeerIdInvalid,
    ChatAdminRequired,
    ChatWriteForbidden,
    UserNotParticipant,
    ChannelPrivate,
    MessageIdInvalid,
    UsernameNotOccupied,
    UsernameInvalid,
    RPCError,
)

from info import API_ID, API_HASH
from database.users_chats_db import db

log = logging.getLogger(__name__)
_sessions = db.db.forward_sessions
_forwarded = db.db.forwarded_messages
_locks = {}

# Prefer an explicit FORWARD_SESSION_KEY; otherwise derive a stable key from API_HASH
# so existing deployments keep working without extra env vars.
from os import environ

_key_material = environ.get("FORWARD_SESSION_KEY") or (API_HASH + ":tgboxoffice-forward-session-v1")
_fernet = Fernet(base64.urlsafe_b64encode(hashlib.sha256(_key_material.encode()).digest()))


def _lock(uid: int) -> asyncio.Lock:
    return _locks.setdefault(uid, asyncio.Lock())


def _encrypt(value: str) -> str:
    return _fernet.encrypt(value.encode()).decode()


def _decrypt(value: str) -> str:
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, TypeError, ValueError):
        raise ValueError("Stored session cannot be decrypted. Please set /ss again.")


def _parse_link(raw: str):
    """Accept t.me/channel/first-last and t.me/c/internal_id/first-last links."""
    raw = (raw or "").strip().strip("<>")
    if not raw:
        raise ValueError("Empty link.")
    if not raw.startswith(("https://", "http://")):
        raw = "https://" + raw.lstrip("@")
    parsed = urlparse(raw)
    host = (parsed.netloc or "").lower()
    if host not in {"t.me", "www.t.me", "telegram.me", "www.telegram.me"}:
        raise ValueError("Send a valid Telegram message-range link (t.me/...).")
    parts = [p for p in parsed.path.split("/") if p]
    if not parts:
        raise ValueError("Link path is empty.")

    if parts[0] == "c":
        # Private channel: https://t.me/c/1234567890/10-20
        if len(parts) < 3 or not parts[1].isdigit():
            raise ValueError(
                "Private channel link must look like https://t.me/c/1234567890/10-20"
            )
        source = int("-100" + parts[1])
        range_part = parts[2]
    else:
        # Public: https://t.me/username/10-20
        if len(parts) < 2:
            raise ValueError("Link must include a channel username and message range.")
        source = parts[0].lstrip("@")
        range_part = parts[1]

    match = re.fullmatch(r"(\d+)(?:-(\d+))?", range_part)
    if not match:
        raise ValueError("Range link must end with a message ID or range, e.g. 10-25.")
    first = int(match.group(1))
    last = int(match.group(2) or first)
    if first < 1 or last < first:
        raise ValueError("Invalid range: ending message ID must be ≥ start.")
    if last - first > 4999:
        raise ValueError("A batch can contain at most 5,000 message IDs.")
    return source, first, last


def _normalize_target(raw: str):
    """Turn user input into something get_chat / resolve_peer can use."""
    raw = (raw or "").strip().lstrip("@")
    if not raw:
        raise ValueError("Target channel ID or @username is empty.")
    # Numeric ID
    if re.fullmatch(r"-?\d+", raw):
        target = int(raw)
        # Users often paste the short positive channel id; Telegram expects -100…
        if target > 0:
            target = int("-100" + str(target))
        return target
    # Username (with or without @)
    return raw


async def _ask(client: Client, chat_id: int, prompt: str):
    answer = await client.ask(
        chat_id, prompt, filters=filters.text & filters.private, timeout=300
    )
    if not answer or (answer.text or "").strip().lower() in {"/cancel", "cancel"}:
        raise asyncio.CancelledError
    return answer


async def _load_session(uid: int) -> str:
    doc = await _sessions.find_one({"_id": uid})
    if not doc or not doc.get("session"):
        raise ValueError("No session saved. Send /ss first.")
    return _decrypt(doc["session"])


async def _resolve_chat(user_client: Client, peer):
    """
    Resolve a peer robustly to avoid PEER_ID_INVALID.

    1. Try get_chat (works when the peer is already in the session cache).
    2. On PeerIdInvalid, call resolve_peer then get_chat again.
    3. Clear error messages for private / inaccessible chats.
    """
    try:
        return await user_client.get_chat(peer)
    except PeerIdInvalid:
        try:
            # Force the session to fetch access_hash / peer info from Telegram.
            await user_client.resolve_peer(peer)
            return await user_client.get_chat(peer)
        except (PeerIdInvalid, ChannelPrivate, UserNotParticipant, ValueError) as e:
            raise ValueError(
                f"Cannot resolve peer {peer!r}. "
                "Make sure the saved account is a member of that chat "
                "and the ID/username is correct. "
                f"({type(e).__name__})"
            ) from e
    except (ChannelPrivate, UserNotParticipant) as e:
        raise ValueError(
            f"The saved account cannot access this chat ({peer!r}). "
            "Join the channel/group with that account first."
        ) from e
    except (UsernameNotOccupied, UsernameInvalid) as e:
        raise ValueError(f"Invalid or non-existent username: {peer!r}") from e


async def _can_post(user_client: Client, chat, me_id: int) -> bool:
    """Return True if the user account can post in the target chat."""
    try:
        member = await user_client.get_chat_member(chat.id, me_id)
    except (UserNotParticipant, PeerIdInvalid, ChannelPrivate):
        return False
    except Exception as e:
        log.warning("get_chat_member failed for %s: %s", chat.id, type(e).__name__)
        return False

    status = str(getattr(member, "status", "") or "").lower()
    if status.endswith(("owner", "creator")):
        return True
    if "administrator" in status or status.endswith("admin"):
        privileges = getattr(member, "privileges", None)
        # Channels need can_post_messages; groups usually allow admins to post.
        if chat.type and str(chat.type.value).lower() == "channel":
            return bool(privileges and getattr(privileges, "can_post_messages", False))
        return True
    # Regular member in a group/supergroup may still be able to send messages
    # unless the group is restricted; we still try later and catch write errors.
    if str(chat.type.value).lower() in {"group", "supergroup"}:
        return "kicked" not in status and "left" not in status and "banned" not in status
    return False


@Client.on_message(filters.command("ss") & filters.private)
async def save_forward_session(client: Client, message):
    if not message.from_user:
        return
    uid = message.from_user.id
    try:
        prompt = await message.reply_text(
            "<b>Send your Telegram session string.</b>\n"
            "It will be validated, encrypted in the database, and used only by /forward.\n"
            "Send /cancel to stop. Never share this string with anyone else."
        )
        reply = await _ask(client, message.chat.id, "Waiting for your session string…")
        session_string = (reply.text or "").strip()
        try:
            await reply.delete()
        except Exception:
            pass

        # Validate before persisting; never log or echo the credential.
        user_client = Client(
            name=f"forward-session-check-{uid}",
            api_id=API_ID,
            api_hash=API_HASH,
            session_string=session_string,
            in_memory=True,
            no_updates=True,
        )
        try:
            await user_client.start()
            account = await user_client.get_me()
            if getattr(account, "is_bot", False):
                raise ValueError(
                    "A user-account session is required; bot sessions are not supported."
                )
        finally:
            if user_client.is_connected:
                await user_client.stop()

        await _sessions.update_one(
            {"_id": uid},
            {
                "$set": {
                    "session": _encrypt(session_string),
                    "account_id": account.id,
                    "account_name": (
                        (account.first_name or "")
                        + (" " + account.last_name if account.last_name else "")
                    ).strip()
                    or None,
                }
            },
            upsert=True,
        )
        await prompt.edit_text(
            f"<b>Session validated and saved securely.</b>\n"
            f"Account: <code>{account.id}</code> "
            f"({account.first_name or 'User'})\n"
            "It will be used only for /forward."
        )
    except asyncio.CancelledError:
        await message.reply_text("Cancelled.")
    except Exception as exc:
        log.warning(
            "Forward session setup failed for user %s: %s: %s",
            uid,
            type(exc).__name__,
            str(exc)[:200],
        )
        await message.reply_text(
            f"<b>Session not saved:</b>\n<code>{str(exc)[:250]}</code>"
        )


@Client.on_message(filters.command("forward") & filters.private)
async def forward_batch(client: Client, message):
    if not message.from_user:
        return
    uid = message.from_user.id
    async with _lock(uid):
        status = await message.reply_text(
            "<b>Batch forwarding setup</b>\n"
            "Send the Telegram message-range link (e.g. https://t.me/c/123/10-50).\n"
            "Send /cancel to stop."
        )
        user_client = None
        try:
            session_string = await _load_session(uid)

            link_msg = await _ask(client, message.chat.id, "Send the batch range link…")
            source, first_id, last_id = _parse_link(link_msg.text)
            try:
                await link_msg.delete()
            except Exception:
                pass

            target_msg = await _ask(
                client, message.chat.id, "Now send the target channel ID or @username…"
            )
            target = _normalize_target(target_msg.text)
            try:
                await target_msg.delete()
            except Exception:
                pass

            user_client = Client(
                name=f"forward-run-{uid}",
                api_id=API_ID,
                api_hash=API_HASH,
                session_string=session_string,
                in_memory=True,
                no_updates=True,
                sleep_threshold=60,
            )
            await user_client.start()
            me = await user_client.get_me()

            # Resolve both peers with the authenticated user account.
            # This populates Pyrogram's peer cache and avoids PEER_ID_INVALID.
            await status.edit_text("<b>Resolving source and target…</b>")
            source_chat = await _resolve_chat(user_client, source)
            target_chat = await _resolve_chat(user_client, target)

            if not await _can_post(user_client, target_chat, me.id):
                raise PermissionError(
                    "The saved Telegram account must be able to post in the target "
                    "(owner / admin with post permission for channels, or member for groups)."
                )

            total = last_id - first_id + 1
            await status.edit_text(
                f"<b>Starting batch…</b>\n"
                f"Source: <code>{source_chat.id}</code> ({getattr(source_chat, 'title', '') or source})\n"
                f"Target: <code>{target_chat.id}</code> ({getattr(target_chat, 'title', '') or target})\n"
                f"Range: <code>{first_id}–{last_id}</code> ({total} messages)"
            )

            sent = skipped = failed = 0
            # Small delay between successful forwards to reduce FloodWait risk.
            DELAY = 0.35

            for msg_id in range(first_id, last_id + 1):
                # Unique key prevents a re-run from re-forwarding already sent items.
                key = {
                    "user_id": uid,
                    "source_id": source_chat.id,
                    "message_id": msg_id,
                    "target_id": target_chat.id,
                }
                if await _forwarded.find_one(key, {"_id": 1}):
                    skipped += 1
                    continue

                try:
                    source_message = await user_client.get_messages(
                        source_chat.id, msg_id
                    )
                    if not source_message or getattr(source_message, "empty", False):
                        skipped += 1
                        continue

                    await user_client.forward_messages(
                        chat_id=target_chat.id,
                        from_chat_id=source_chat.id,
                        message_ids=msg_id,
                    )
                    await _forwarded.update_one(
                        key, {"$setOnInsert": {**key}}, upsert=True
                    )
                    sent += 1
                    await asyncio.sleep(DELAY)

                except FloodWait as exc:
                    wait = int(getattr(exc, "value", 5)) + 1
                    log.info("FloodWait %ss (user=%s, msg=%s)", wait, uid, msg_id)
                    await status.edit_text(
                        f"<b>FloodWait</b> — sleeping {wait}s…\n"
                        f"Sent: {sent} | Skipped: {skipped} | Failed: {failed}"
                    )
                    await asyncio.sleep(wait)
                    try:
                        await user_client.forward_messages(
                            target_chat.id, source_chat.id, msg_id
                        )
                        await _forwarded.update_one(
                            key, {"$setOnInsert": {**key}}, upsert=True
                        )
                        sent += 1
                    except Exception:
                        failed += 1
                        log.exception(
                            "Forward retry failed (user=%s, message=%s)", uid, msg_id
                        )

                except MessageIdInvalid:
                    skipped += 1

                except (PeerIdInvalid, ChannelPrivate, UserNotParticipant) as exc:
                    failed += 1
                    log.warning(
                        "Source/peer inaccessible (user=%s, message=%s): %s",
                        uid,
                        msg_id,
                        type(exc).__name__,
                    )
                    # If the whole source becomes inaccessible, abort early.
                    if isinstance(exc, (ChannelPrivate, UserNotParticipant)) and failed >= 3:
                        raise PermissionError(
                            "Lost access to the source chat. "
                            "Ensure the saved account is still a member."
                        ) from exc

                except (ChatAdminRequired, ChatWriteForbidden) as exc:
                    raise PermissionError(
                        "The saved account cannot post to the target. "
                        "Grant it posting permission and retry."
                    ) from exc

                except RPCError as exc:
                    failed += 1
                    log.warning(
                        "RPCError forward (user=%s, message=%s): %s %s",
                        uid,
                        msg_id,
                        type(exc).__name__,
                        str(exc)[:120],
                    )

                except Exception as exc:
                    failed += 1
                    log.warning(
                        "Forward failed (user=%s, message=%s): %s",
                        uid,
                        msg_id,
                        type(exc).__name__,
                    )

                processed = sent + skipped + failed
                if processed % 25 == 0 or processed == total:
                    try:
                        await status.edit_text(
                            f"<b>Forwarding…</b>\n"
                            f"Sent: <code>{sent}</code> | "
                            f"Skipped: <code>{skipped}</code> | "
                            f"Failed: <code>{failed}</code>\n"
                            f"Processed through message <code>{msg_id}</code> "
                            f"({processed}/{total})."
                        )
                    except Exception:
                        pass

            await status.edit_text(
                f"<b>Batch completed.</b>\n"
                f"Sent: <code>{sent}</code>\n"
                f"Skipped / already sent / empty: <code>{skipped}</code>\n"
                f"Failed: <code>{failed}</code>"
            )

        except asyncio.CancelledError:
            try:
                await status.edit_text("Forwarding cancelled.")
            except Exception:
                await message.reply_text("Forwarding cancelled.")
        except Exception as exc:
            log.exception("Batch forwarding failed for user %s", uid)
            try:
                await status.edit_text(
                    f"<b>Could not complete forwarding:</b>\n<code>{str(exc)[:700]}</code>"
                )
            except Exception:
                await message.reply_text(
                    f"<b>Could not complete forwarding:</b>\n<code>{str(exc)[:700]}</code>"
                )
        finally:
            if user_client and user_client.is_connected:
                try:
                    await user_client.stop()
                except Exception:
                    pass
