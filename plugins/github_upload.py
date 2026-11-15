"""Per-user GitHub credential setup and safe ZIP-to-branch publishing."""
import asyncio
import base64
import hashlib
import html
import logging
import os
import re
import shutil
import tempfile
import zipfile
from urllib.parse import quote, urlparse

import requests
from cryptography.fernet import Fernet, InvalidToken
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from database.users_chats_db import db

log = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 150 * 1024 * 1024
MAX_FILES = 500

# Interactive setup state is intentionally in-memory: only the user currently
# configuring credentials can submit the next value. Credentials themselves
# are persisted encrypted in MongoDB.
_GITHUB_SETUP_PENDING = {}


def _fernet():
    # Stable per-deployment key; credentials are encrypted before being written to MongoDB.
    seed = (str(getattr(info, "BOT_TOKEN", "")) + "|" + str(getattr(info, "DATABASE_URI", ""))).encode()
    if not seed.strip(b"|"):
        raise RuntimeError("Bot encryption key is not configured")
    key = base64.urlsafe_b64encode(hashlib.sha256(seed).digest())
    return Fernet(key)


def _credentials_collection():
    return db.config


async def _save_credentials(user_id, username=None, token=None):
    update = {}
    if username is not None:
        update["github.username"] = username
    if token is not None:
        update["github.token_enc"] = _fernet().encrypt(token.encode()).decode()
    await _credentials_collection().update_one(
        {"_id": f"github_user:{int(user_id)}"}, {"$set": update}, upsert=True
    )


async def _get_credentials(user_id):
    doc = await _credentials_collection().find_one({"_id": f"github_user:{int(user_id)}"}) or {}
    cfg = doc.get("github", {})
    username = cfg.get("username")
    encrypted = cfg.get("token_enc")
    if not username or not encrypted:
        return None
    try:
        token = _fernet().decrypt(encrypted.encode()).decode()
    except (InvalidToken, ValueError):
        log.error("Unable to decrypt GitHub credential for user %s", user_id)
        return None
    return username, token


def _repo_parts(raw):
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        raise ValueError("Repository link is missing")
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", raw):
        owner, repo = raw.split("/", 1)
    else:
        parsed = urlparse(raw if "://" in raw else "https://" + raw)
        if parsed.netloc.lower() not in {"github.com", "www.github.com"}:
            raise ValueError("Use a github.com repository URL")
        parts = [p for p in parsed.path.split("/") if p]
        if len(parts) < 2:
            raise ValueError("Repository URL must look like https://github.com/owner/repo")
        owner, repo = parts[0], parts[1]
    repo = repo.removesuffix(".git")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner) or not re.fullmatch(r"[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository owner or name")
    return owner, repo


def _gh_request(method, path, token, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MoviesZoneFlix-GitHub-Uploader",
    }
    response = requests.request(method, GITHUB_API + path, headers=headers, timeout=(15, 90), **kwargs)
    if response.status_code >= 400:
        try:
            detail = response.json().get("message", response.reason)
        except Exception:
            detail = response.reason
        # Never include request headers or token in surfaced errors.
        raise RuntimeError(f"GitHub API {response.status_code}: {str(detail)[:350]}")
    if response.status_code == 204 or not response.content:
        return {}
    return response.json()


def _zip_entries(zip_path):
    entries = []
    total = 0
    with zipfile.ZipFile(zip_path) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES:
            raise ValueError(f"ZIP contains too many files (maximum {MAX_FILES})")
        # Remove a single common wrapper directory (e.g. project-main/).
        first_parts = [i.filename.replace("\\", "/").split("/") for i in infos]
        common_root = first_parts[0][0] if first_parts and first_parts[0] else ""
        strip_root = (
            bool(common_root)
            and common_root not in (".", "..")
            and not re.match(r"^[A-Za-z]:$", common_root)
            and all(len(parts) > 1 and parts[0] == common_root for parts in first_parts)
        )
        for item in infos:
            name = item.filename.replace("\\", "/")
            if name.startswith("/") or re.match(r"^[A-Za-z]:/", name):
                raise ValueError(f"Unsafe absolute ZIP path: {item.filename}")
            parts = name.split("/")
            if strip_root:
                parts = parts[1:]
            if not parts or any(p in ("", ".", "..") for p in parts):
                raise ValueError(f"Unsafe ZIP path: {item.filename}")
            path = "/".join(parts)
            if path.startswith(".git/") or path == ".git" or path.startswith("__MACOSX/"):
                continue
            # Do not allow symlinks or special files in archives.
            unix_mode = (item.external_attr >> 16) & 0xFFFF
            if (unix_mode & 0o170000) == 0o120000:
                raise ValueError(f"Symlinks are not allowed: {path}")
            total += item.file_size
            if item.file_size > 95 * 1024 * 1024:
                raise ValueError(f"File exceeds GitHub's 100 MB blob limit: {path}")
            if total > MAX_UNPACKED_BYTES:
                raise ValueError(f"Uncompressed ZIP exceeds {MAX_UNPACKED_BYTES // (1024 * 1024)} MB")
            data = archive.read(item)
            entries.append((path, data))
    if not entries:
        raise ValueError("ZIP contains no uploadable files")
    return entries


def _publish_zip(owner, repo, branch, token, expected_login, zip_path):
    # Validate token and repository permissions first.
    user = _gh_request("GET", "/user", token)
    authenticated_login = (user.get("login") or "").lower()
    actual_login = user.get("login") or "unknown"
    if authenticated_login != str(expected_login).lower():
        raise RuntimeError(f"Configured username does not match the token account ({actual_login})")
    repository = _gh_request("GET", f"/repos/{quote(owner)}/{quote(repo)}", token)
    if repository.get("archived"):
        raise RuntimeError("Repository is archived and cannot be updated")
    if repository.get("permissions", {}).get("push") is False:
        raise RuntimeError("This token does not have push access to the repository")

    branch_path = quote(branch, safe="")
    try:
        ref = _gh_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch_path}", token)
        parent_sha = ref["object"]["sha"]
    except RuntimeError as exc:
        if "404" not in str(exc):
            raise
        default_branch = repository.get("default_branch")
        if not default_branch:
            raise RuntimeError("Could not determine the repository default branch")
        default_ref = _gh_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{quote(default_branch, safe='')}", token)
        parent_sha = default_ref["object"]["sha"]
        # Create requested branch from the repository's default branch only.
        _gh_request("POST", f"/repos/{owner}/{repo}/git/refs", token,
                    json={"ref": f"refs/heads/{branch}", "sha": parent_sha})

    parent_commit = _gh_request("GET", f"/repos/{owner}/{repo}/git/commits/{parent_sha}", token)
    base_tree = parent_commit["tree"]["sha"]
    entries = _zip_entries(zip_path)
    tree_items = []
    for path, content in entries:
        blob = _gh_request("POST", f"/repos/{owner}/{repo}/git/blobs", token,
                           json={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"})
        tree_items.append({"path": path, "mode": "100644", "type": "blob", "sha": blob["sha"]})
    tree = _gh_request("POST", f"/repos/{owner}/{repo}/git/trees", token,
                       json={"base_tree": base_tree, "tree": tree_items})
    commit = _gh_request("POST", f"/repos/{owner}/{repo}/git/commits", token,
                         json={"message": "Update files via MoviesZoneFlix /uploadto", "tree": tree["sha"], "parents": [parent_sha]})
    try:
        _gh_request("PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch_path}", token,
                    json={"sha": commit["sha"], "force": False})
    except RuntimeError:
        # A concurrent branch update is not force-pushed; report conflict safely.
        raise RuntimeError("Branch changed during upload. No force push was performed; retry the command.")
    return len(entries), commit.get("html_url"), authenticated_login


@Client.on_message(filters.command("github") & filters.private)
async def github_settings(client, message):
    if not message.from_user:
        return
    doc = await _credentials_collection().find_one({"_id": f"github_user:{message.from_user.id}"}) or {}
    cfg = doc.get("github", {})
    username = html.escape(cfg.get("username") or "Not configured")
    token_state = "Configured" if cfg.get("token_enc") else "Not configured"
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👤 Set GitHub Username", callback_data="ghcfg:username")],
        [InlineKeyboardButton("🔑 Set / Replace Personal Access Token", callback_data="ghcfg:token")],
        [InlineKeyboardButton("🗑 Remove GitHub Credentials", callback_data="ghcfg:remove")],
    ])
    await message.reply_text(
        "<b>GitHub Configuration</b>\n\n"
        f"Username: <code>{username}</code>\nToken: <b>{token_state}</b>\n\n"
        "Choose a button below. Your token is encrypted before it is stored. "
        "Use a fine-grained PAT with repository Contents: Read and write permission.\n\n"
        "Send /cancel to stop setup.",
        reply_markup=keyboard,
    )


@Client.on_callback_query(filters.regex(r"^ghcfg:(username|token|remove)$"), group=-2)
async def github_settings_callback(client, query):
    uid = query.from_user.id
    # Buttons are private and user-specific; prevent other users from changing
    # the credentials belonging to the person who opened /github.
    if not query.message or query.message.chat.type != enums.ChatType.PRIVATE or query.message.chat.id != uid:
        return await query.answer("Open /github in your own private chat.", show_alert=True)
    action = query.data.split(":", 1)[1]
    await query.answer()
    if action == "remove":
        _GITHUB_SETUP_PENDING.pop(uid, None)
        await _credentials_collection().delete_one({"_id": f"github_user:{uid}"})
        return await query.message.edit_text("<b>GitHub credentials removed.</b>")

    _GITHUB_SETUP_PENDING[uid] = action
    if action == "username":
        prompt = "Send your GitHub username in your next message.\n\n/cancel to stop."
    else:
        prompt = (
            "Send your GitHub Personal Access Token in your next message. "
            "It will be encrypted before storage and the message will be deleted where possible.\n\n"
            "/cancel to stop."
        )
    await query.message.reply_text(prompt)


@Client.on_message(filters.private & filters.text, group=-1)
async def github_setup_input(client, message):
    if not message.from_user:
        return
    uid = message.from_user.id
    action = _GITHUB_SETUP_PENDING.get(uid)
    if not action:
        return
    value = (message.text or "").strip()
    # Let normal bot commands continue to their own handlers while setup is pending.
    if value.startswith("/") and value.lower() != "/cancel":
        return
    if value.lower() == "/cancel":
        _GITHUB_SETUP_PENDING.pop(uid, None)
        return await message.reply_text("GitHub setup cancelled. Run /github to open settings again.")

    if action == "username":
        if not re.fullmatch(r"[A-Za-z0-9-]{1,39}", value):
            return await message.reply_text("Invalid GitHub username. Use 1–39 letters, numbers or hyphens, then try again or send /cancel.")
        await _save_credentials(uid, username=value)
        _GITHUB_SETUP_PENDING.pop(uid, None)
        try:
            await message.delete()
        except Exception:
            pass
        return await message.reply_text("<b>GitHub username saved.</b> Now choose Set / Replace Personal Access Token in /github.")

    if action == "token":
        if len(value) < 20 or any(ch.isspace() for ch in value):
            return await message.reply_text("That token does not look valid. Please send a valid GitHub PAT or /cancel.")
        await _save_credentials(uid, token=value)
        _GITHUB_SETUP_PENDING.pop(uid, None)
        try:
            await message.delete()
        except Exception:
            pass
        return await message.reply_text("<b>GitHub token saved securely.</b> Run /uploadto by replying to a ZIP file.")


@Client.on_message(filters.command("uploadto"))
async def upload_zip_to_github(client, message):
    if not message.from_user:
        return
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text(
            "Reply to a ZIP document with:\n<code>/uploadto https://github.com/owner/repo branch-name</code>"
        )
    args = message.text.split(maxsplit=2)
    if len(args) != 3:
        return await message.reply_text("Usage: <code>/uploadto repo_link branch_name</code>")
    try:
        owner, repo = _repo_parts(args[1])
        branch = args[2].strip()
        if not branch or branch.startswith("-") or ".." in branch or branch.endswith(("/", ".", ".lock")) or not re.fullmatch(r"[A-Za-z0-9._/-]+", branch):
            raise ValueError("Invalid branch name")
        if any(part in ("", ".", "..") for part in branch.split("/")):
            raise ValueError("Invalid branch name")
    except ValueError as exc:
        return await message.reply_text(f"<b>Invalid input:</b> {exc}")

    credentials = await _get_credentials(message.from_user.id)
    if not credentials:
        return await message.reply_text("Configure your GitHub username and token first using /github in a private chat.")
    doc = message.reply_to_message.document
    if not (doc.file_name or "").lower().endswith(".zip"):
        return await message.reply_text("The replied document must be a .zip file.")
    if doc.file_size and doc.file_size > MAX_ZIP_BYTES:
        return await message.reply_text(f"ZIP is too large. Maximum supported size is {MAX_ZIP_BYTES // (1024 * 1024)} MB.")

    status = await message.reply_text(f"⏳ Preparing upload to <b>{html.escape(owner)}/{html.escape(repo)}</b> · branch <code>{html.escape(branch)}</code>…")
    temp_dir = tempfile.mkdtemp(prefix="mzf_github_")
    zip_path = os.path.join(temp_dir, "upload.zip")
    try:
        downloaded = await message.reply_to_message.download(file_name=zip_path)
        if not downloaded or not zipfile.is_zipfile(downloaded):
            raise ValueError("The replied file is not a valid ZIP archive")
        count, commit_url, login = await asyncio.to_thread(
            _publish_zip, owner, repo, branch, credentials[1], credentials[0], downloaded
        )
        result = (f"<b>GitHub upload successful</b>\n\n"
                  f"Repository: <code>{html.escape(owner)}/{html.escape(repo)}</code>\nBranch: <code>{html.escape(branch)}</code>\n"
                  f"Files uploaded: <code>{count}</code>\nAuthenticated account: <code>{login}</code>")
        if commit_url:
            result += f"\n<a href=\"{commit_url}\">View commit</a>"
        await status.edit_text(result, disable_web_page_preview=True)
    except Exception as exc:
        log.exception("GitHub ZIP upload failed for user %s to %s/%s:%s", message.from_user.id, owner, repo, branch)
        detail = str(exc)[:500]
        await status.edit_text(
            f"<b>GitHub upload failed</b>\n\nRepository: <code>{html.escape(owner)}/{html.escape(repo)}</code>\n"
            f"Branch: <code>{html.escape(branch)}</code>\nReason: <code>{html.escape(detail)}</code>\n\n"
            "Check that your PAT has Contents: Read and write access and that the branch is writable."
        )
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
