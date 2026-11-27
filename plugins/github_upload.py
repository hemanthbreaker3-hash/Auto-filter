"""Per-user GitHub credential setup and high-speed ZIP-to-branch publishing."""
import asyncio
import base64
import hashlib
import html
import logging
import os
import random
import re
import shutil
import subprocess
import tempfile
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import quote, urlparse

import requests
from requests.adapters import HTTPAdapter
from cryptography.fernet import Fernet, InvalidToken
from pyrogram import Client, filters, enums
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

import info
from database.users_chats_db import db

log = logging.getLogger(__name__)
GITHUB_API = "https://api.github.com"
MAX_ZIP_BYTES = 50 * 1024 * 1024
MAX_UNPACKED_BYTES = 1024 * 1024 * 1024  # 1 GiB safety ceiling
MAX_FILES = 10000
# Keep REST fallback concurrency modest to avoid triggering GitHub secondary rate limits.
BLOB_WORKERS = 4
MAX_API_RETRIES = 6
RETRYABLE_STATUS_CODES = {403, 429, 500, 502, 503, 504}
_INVALID_BRANCH_CHARS_RE = re.compile(r"[\x00-\x1f\x7f ~^:?*\[\\]")

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
    raw = (raw or "").strip().strip("<>").rstrip("/")
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


def validate_branch_name(branch):
    """Validate Git branch names without rejecting valid names like 'main'."""
    branch = (branch or "").strip()
    if branch.startswith("refs/heads/"):
        branch = branch[len("refs/heads/"):]
    if not branch:
        raise ValueError("Branch name is required")
    if (
        branch.startswith("-")
        or branch.startswith(".")
        or branch.startswith("/")
        or branch.endswith("/")
        or branch.endswith(".")
        or branch.endswith(".lock")
        or ".." in branch
        or "@{" in branch
        or "//" in branch
        or _INVALID_BRANCH_CHARS_RE.search(branch)
    ):
        raise ValueError(f"Invalid branch name: {branch!r}")
    return branch


def parse_uploadto_command(raw_text):
    """Parse /uploadto[@BotUsername] <repo_url> <branch> <commit_message>."""
    text = (raw_text or "").strip()
    if not text:
        raise ValueError("Command text is empty")
    match = re.match(r"^/uploadto(?:@[A-Za-z0-9_]+)?(?:\s+(.*))?$", text, flags=re.IGNORECASE | re.DOTALL)
    if not match:
        raise ValueError("Command must start with /uploadto")
    args_text = (match.group(1) or "").strip()
    if not args_text:
        raise ValueError("Missing repository link, branch, and commit message")
    fields = args_text.split(maxsplit=2)
    if len(fields) == 1:
        raise ValueError("Missing branch name and commit message")
    if len(fields) == 2:
        raise ValueError("Missing commit message")
    repo_input, branch_input, commit_input = fields
    owner, repo = _repo_parts(repo_input)
    branch = validate_branch_name(branch_input)
    commit_message = commit_input.strip()
    if not commit_message:
        raise ValueError("Commit message is required")
    return owner, repo, branch, commit_message


class _GitHubRateLimiter:
    """Thread-safe shared cooldown and gentle mutation pacing across workers."""

    def __init__(self, min_mutation_interval=0.06):
        self._lock = threading.Lock()
        self._cooldown_until = 0.0
        self._next_mutation_at = 0.0
        self._min_mutation_interval = min_mutation_interval

    def wait_turn(self, is_mutation=False):
        while True:
            with self._lock:
                now = time.monotonic()
                wait_for = max(0.0, self._cooldown_until - now)
                if is_mutation and wait_for == 0.0:
                    if now < self._next_mutation_at:
                        wait_for = self._next_mutation_at - now
                    else:
                        self._next_mutation_at = now + self._min_mutation_interval
                        return
                elif wait_for == 0.0:
                    return
            time.sleep(min(wait_for, 5.0))

    def trigger_cooldown(self, seconds):
        if seconds <= 0:
            return
        with self._lock:
            target = time.monotonic() + seconds
            if target > self._cooldown_until:
                self._cooldown_until = target


def _create_session():
    session = requests.Session()
    adapter = HTTPAdapter(pool_connections=max(8, BLOB_WORKERS * 2), pool_maxsize=max(8, BLOB_WORKERS * 2))
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def _retry_delay_seconds(response, detail, attempt):
    retry_after = response.headers.get("Retry-After")
    if retry_after:
        try:
            return max(1.0, float(retry_after))
        except ValueError:
            pass
    if response.status_code == 403 and response.headers.get("X-RateLimit-Remaining") == "0":
        reset_hdr = response.headers.get("X-RateLimit-Reset")
        if reset_hdr:
            try:
                wait = float(reset_hdr) - time.time() + 1.0
                if 0 < wait <= 300:
                    return wait
            except ValueError:
                pass
    detail_lower = (detail or "").lower()
    if response.status_code in (403, 429) and ("rate limit" in detail_lower or response.status_code == 429):
        base = min(120.0, 15.0 * (2 ** attempt))
    elif response.status_code >= 500:
        base = min(30.0, 2.0 * (2 ** attempt))
    else:
        return None
    return base + random.uniform(0.5, 2.5)


def _gh_request(method, path, token, session=None, rate_limiter=None, **kwargs):
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "MoviesZoneFlix-GitHub-Uploader",
    }
    requester = session.request if session is not None else requests.request
    is_mutation = method.upper() in {"POST", "PUT", "PATCH", "DELETE"}

    for attempt in range(MAX_API_RETRIES + 1):
        if rate_limiter is not None:
            rate_limiter.wait_turn(is_mutation=is_mutation)
        try:
            response = requester(method, GITHUB_API + path, headers=headers, timeout=(15, 90), **kwargs)
        except requests.RequestException as exc:
            if attempt < MAX_API_RETRIES:
                delay = min(30.0, 2.0 * (2 ** attempt)) + random.uniform(0.2, 1.0)
                log.warning("GitHub request %s %s network error (%s); retrying in %.1fs", method, path, exc, delay)
                time.sleep(delay)
                continue
            raise RuntimeError(f"GitHub network error after {MAX_API_RETRIES + 1} attempts: {str(exc)[:300]}") from exc

        if response.status_code >= 400:
            try:
                detail = response.json().get("message", response.reason)
            except Exception:
                detail = response.reason
            if response.status_code in RETRYABLE_STATUS_CODES and attempt < MAX_API_RETRIES:
                delay = _retry_delay_seconds(response, detail, attempt)
                if delay is not None:
                    log.warning(
                        "GitHub API %s on %s %s (attempt %d/%d); backing off %.1fs: %s",
                        response.status_code, method, path, attempt + 1, MAX_API_RETRIES + 1, delay, str(detail)[:200],
                    )
                    if rate_limiter is not None:
                        rate_limiter.trigger_cooldown(delay)
                    time.sleep(delay)
                    continue
            # Never include request headers or token in surfaced errors.
            raise RuntimeError(f"GitHub API {response.status_code}: {str(detail)[:350]}")

        if response.status_code == 204 or not response.content:
            return {}
        return response.json()


def _git_blob_sha(content):
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()


def _zip_entries(zip_path):
    entries = []
    total = 0
    with zipfile.ZipFile(zip_path) as archive:
        infos = [i for i in archive.infolist() if not i.is_dir()]
        if len(infos) > MAX_FILES:
            raise ValueError(f"ZIP contains too many files (maximum {MAX_FILES:,})")
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


def _fetch_existing_blob_shas(owner, repo, commit_sha, token, session, rate_limiter):
    """Fetch existing blob SHAs on the target/base commit to skip unchanged uploads."""
    try:
        commit_data = _gh_request(
            "GET", f"/repos/{owner}/{repo}/git/commits/{commit_sha}", token,
            session=session, rate_limiter=rate_limiter,
        )
        tree_sha = (commit_data.get("tree") or {}).get("sha")
        if not tree_sha:
            return set()
        tree_data = _gh_request(
            "GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}?recursive=1", token,
            session=session, rate_limiter=rate_limiter,
        )
        return {
            item["sha"]
            for item in tree_data.get("tree", [])
            if item.get("type") == "blob" and item.get("sha")
        }
    except Exception as exc:
        log.debug("Could not prefetch existing tree blobs for %s/%s@%s: %s", owner, repo, commit_sha, exc)
        return set()


def _run_git(args, cwd=None, env=None, token=None, timeout=300):
    proc = subprocess.run(
        ["git", *args],
        cwd=cwd,
        env=env,
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or f"git {args[0]} failed").strip()
        if token:
            err = err.replace(token, "***")
        raise RuntimeError(err[:400])
    return proc.stdout.strip()


def _publish_zip_via_git(
    owner,
    repo,
    branch,
    token,
    actual_login,
    entries,
    commit_message,
    branch_exists,
    clone_branch,
    repo_is_empty,
):
    """High-speed packfile upload using native git CLI (single HTTPS push for 1,000+ files)."""
    work_root = tempfile.mkdtemp(prefix="mzf_gitpush_")
    try:
        askpass_path = os.path.join(work_root, "askpass.sh")
        with open(askpass_path, "w", encoding="utf-8") as fh:
            fh.write(
                "#!/bin/sh\n"
                "case \"$1\" in\n"
                "  *Username*) printf '%s\\n' \"$GH_ASKPASS_USER\" ;;\n"
                "  *) printf '%s\\n' \"$GH_ASKPASS_TOKEN\" ;;\n"
                "esac\n"
            )
        os.chmod(askpass_path, 0o700)

        env = {
            **os.environ,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_ASKPASS": askpass_path,
            "GH_ASKPASS_USER": actual_login,
            "GH_ASKPASS_TOKEN": token,
        }
        repo_url = f"https://github.com/{quote(owner)}/{quote(repo)}.git"
        repo_dir = os.path.join(work_root, "repo")

        if not repo_is_empty:
            _run_git(
                ["clone", "--depth", "1", "--branch", clone_branch, "--single-branch", repo_url, repo_dir],
                env=env,
                token=token,
                timeout=300,
            )
            if not branch_exists:
                _run_git(["checkout", "-B", branch], cwd=repo_dir, env=env, token=token)
            # Replace the entire branch tree: remove all existing files before writing ZIP entries.
            for name in os.listdir(repo_dir):
                if name == ".git":
                    continue
                target = os.path.join(repo_dir, name)
                if os.path.isdir(target) and not os.path.islink(target):
                    shutil.rmtree(target)
                else:
                    os.unlink(target)
        else:
            os.makedirs(repo_dir, exist_ok=True)
            _run_git(["init"], cwd=repo_dir, env=env, token=token)
            _run_git(["checkout", "-B", branch], cwd=repo_dir, env=env, token=token)
            _run_git(["remote", "add", "origin", repo_url], cwd=repo_dir, env=env, token=token)

        for rel_path, content in entries:
            dest_path = os.path.join(repo_dir, *rel_path.split("/"))
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as fh:
                fh.write(content)

        _run_git(["config", "user.name", actual_login], cwd=repo_dir, env=env, token=token)
        _run_git(["config", "user.email", f"{actual_login}@users.noreply.github.com"], cwd=repo_dir, env=env, token=token)
        _run_git(["add", "-A"], cwd=repo_dir, env=env, token=token)

        status_out = _run_git(["status", "--porcelain"], cwd=repo_dir, env=env, token=token)
        if not status_out and branch_exists:
            head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo_dir, env=env, token=token)
            return len(entries), f"https://github.com/{quote(owner)}/{quote(repo)}/commit/{head_sha}", actual_login.lower()

        _run_git(["commit", "-m", commit_message], cwd=repo_dir, env=env, token=token)
        try:
            _run_git(["push", "origin", f"refs/heads/{branch}"], cwd=repo_dir, env=env, token=token, timeout=300)
        except RuntimeError as exc:
            err_lower = str(exc).lower()
            if "non-fast-forward" in err_lower or "fetch first" in err_lower or "rejected" in err_lower:
                raise RuntimeError("Branch changed during upload. No force push was performed; retry the command.") from exc
            if "workflow" in err_lower and "scope" in err_lower:
                raise RuntimeError("PAT lacks 'workflow' scope required to push .github/workflows files.") from exc
            raise

        head_sha = _run_git(["rev-parse", "HEAD"], cwd=repo_dir, env=env, token=token)
        return len(entries), f"https://github.com/{quote(owner)}/{quote(repo)}/commit/{head_sha}", actual_login.lower()
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def _publish_zip_via_api(
    owner,
    repo,
    branch,
    token,
    authenticated_login,
    entries,
    commit_message,
    branch_exists,
    parent_sha,
    session,
    rate_limiter,
):
    """Fallback Git Data REST API uploader with deduplication and 403 rate-limit backoff."""
    branch_path = quote(branch, safe="")
    if not branch_exists:
        _gh_request(
            "POST", f"/repos/{owner}/{repo}/git/refs", token,
            session=session, rate_limiter=rate_limiter,
            json={"ref": f"refs/heads/{branch}", "sha": parent_sha},
        )

    existing_shas = _fetch_existing_blob_shas(owner, repo, parent_sha, token, session, rate_limiter)
    entry_shas = [_git_blob_sha(content) for _, content in entries]
    blobs_to_upload = {}
    for (_, content), sha in zip(entries, entry_shas):
        if sha not in existing_shas and sha not in blobs_to_upload:
            blobs_to_upload[sha] = content

    uploaded_shas = {}
    if blobs_to_upload:
        def upload_blob(item):
            local_sha, content = item
            blob = _gh_request(
                "POST", f"/repos/{owner}/{repo}/git/blobs", token,
                session=session, rate_limiter=rate_limiter,
                json={"content": base64.b64encode(content).decode("ascii"), "encoding": "base64"},
            )
            return local_sha, blob["sha"]

        with ThreadPoolExecutor(max_workers=BLOB_WORKERS) as pool:
            futures = [pool.submit(upload_blob, item) for item in blobs_to_upload.items()]
            for future in as_completed(futures):
                local_sha, remote_sha = future.result()
                uploaded_shas[local_sha] = remote_sha

    tree_items = [
        {
            "path": path,
            "mode": "100644",
            "type": "blob",
            "sha": sha if sha in existing_shas else uploaded_shas[sha],
        }
        for (path, _), sha in zip(entries, entry_shas)
    ]

    # Omitting base_tree replaces the entire branch tree so stale files are removed.
    tree = _gh_request(
        "POST", f"/repos/{owner}/{repo}/git/trees", token,
        session=session, rate_limiter=rate_limiter,
        json={"tree": tree_items},
    )
    commit = _gh_request(
        "POST", f"/repos/{owner}/{repo}/git/commits", token,
        session=session, rate_limiter=rate_limiter,
        json={"message": commit_message, "tree": tree["sha"], "parents": [parent_sha]},
    )
    try:
        _gh_request(
            "PATCH", f"/repos/{owner}/{repo}/git/refs/heads/{branch_path}", token,
            session=session, rate_limiter=rate_limiter,
            json={"sha": commit["sha"], "force": False},
        )
    except RuntimeError as exc:
        raise RuntimeError("Branch changed during upload. No force push was performed; retry the command.") from exc
    return len(entries), commit.get("html_url"), authenticated_login


def _publish_zip(owner, repo, branch, token, expected_login, zip_path, commit_message):
    session = _create_session()
    rate_limiter = _GitHubRateLimiter()
    try:
        # Validate token and repository permissions first.
        user = _gh_request("GET", "/user", token, session=session, rate_limiter=rate_limiter)
        authenticated_login = (user.get("login") or "").lower()
        actual_login = user.get("login") or "unknown"
        if authenticated_login != str(expected_login).lower():
            raise RuntimeError(f"Configured username does not match the token account ({actual_login})")
        repository = _gh_request("GET", f"/repos/{quote(owner)}/{quote(repo)}", token, session=session, rate_limiter=rate_limiter)
        if repository.get("archived"):
            raise RuntimeError("Repository is archived and cannot be updated")
        if repository.get("permissions", {}).get("push") is False:
            raise RuntimeError("This token does not have push access to the repository")

        branch_path = quote(branch, safe="")
        branch_exists = False
        repo_is_empty = False
        clone_branch = branch
        parent_sha = None

        try:
            ref = _gh_request("GET", f"/repos/{owner}/{repo}/git/ref/heads/{branch_path}", token, session=session, rate_limiter=rate_limiter)
            parent_sha = ref["object"]["sha"]
            branch_exists = True
        except RuntimeError as exc:
            err_text = str(exc)
            if "404" not in err_text and "409" not in err_text:
                raise
            default_branch = repository.get("default_branch") or "main"
            try:
                default_ref = _gh_request(
                    "GET", f"/repos/{owner}/{repo}/git/ref/heads/{quote(default_branch, safe='')}",
                    token, session=session, rate_limiter=rate_limiter,
                )
                parent_sha = default_ref["object"]["sha"]
                clone_branch = default_branch
            except RuntimeError as default_exc:
                if "404" in str(default_exc) or "409" in str(default_exc):
                    repo_is_empty = True
                else:
                    raise

        entries = _zip_entries(zip_path)

        # Prefer native git packfile push for high-speed 1,000+ file uploads without REST blob rate limits.
        if shutil.which("git"):
            return _publish_zip_via_git(
                owner=owner,
                repo=repo,
                branch=branch,
                token=token,
                actual_login=actual_login,
                entries=entries,
                commit_message=commit_message,
                branch_exists=branch_exists,
                clone_branch=clone_branch,
                repo_is_empty=repo_is_empty,
            )

        if repo_is_empty:
            raise RuntimeError(
                "Repository is empty (no initial commit) and git CLI is unavailable. "
                "Initialize the repository with a README on GitHub first, then retry."
            )

        return _publish_zip_via_api(
            owner=owner,
            repo=repo,
            branch=branch,
            token=token,
            authenticated_login=authenticated_login,
            entries=entries,
            commit_message=commit_message,
            branch_exists=branch_exists,
            parent_sha=parent_sha,
            session=session,
            rate_limiter=rate_limiter,
        )
    finally:
        session.close()


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


@Client.on_message(filters.command("uploadto", case_sensitive=False))
async def upload_zip_to_github(client, message):
    if not message.from_user:
        return
    if not message.reply_to_message or not message.reply_to_message.document:
        return await message.reply_text(
            "Reply to a ZIP document with:\n<code>/uploadto repo_link branch commit_message</code>"
        )
    raw_text = (message.text or message.caption or "").strip()
    usage = "Usage: <code>/uploadto repo_link branch commit_message</code>\n\nThis replaces ALL files on the target branch with the ZIP contents."
    if not raw_text:
        return await message.reply_text(usage)
    try:
        owner, repo, branch, commit_message = parse_uploadto_command(raw_text)
    except ValueError as exc:
        return await message.reply_text(
            f"<b>Invalid input:</b> {html.escape(str(exc))}\n\n"
            f"Parsed command: <code>{html.escape(raw_text)}</code>\n\n{usage}"
        )

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
            _publish_zip, owner, repo, branch, credentials[1], credentials[0], downloaded, commit_message
        )
        result = (
            f"<b>GitHub upload successful</b>\n\n"
            f"Repository: <code>{html.escape(owner)}/{html.escape(repo)}</code>\nBranch: <code>{html.escape(branch)}</code>\n"
            f"Files uploaded: <code>{count}</code>\nCommit message: <code>{html.escape(commit_message)}</code>\n"
            f"Branch contents replaced: <b>Yes</b>\nAuthenticated account: <code>{html.escape(login)}</code>"
        )
        if commit_url:
            result += f"\n<a href=\"{html.escape(commit_url, quote=True)}\">View commit</a>"
        await status.edit_text(result, disable_web_page_preview=True)
    except Exception as exc:
        log.exception("GitHub ZIP upload failed for user %s to %s/%s:%s", message.from_user.id, owner, repo, branch)
        detail = str(exc)[:500]
        hint = "Check that your PAT has Contents: Read and write access and that the branch is writable."
        if "rate limit" in detail.lower():
            hint = "GitHub rate-limited the upload even after automatic retries. Wait 1–2 minutes and try again."
        try:
            await status.edit_text(
                f"<b>GitHub upload failed</b>\n\nRepository: <code>{html.escape(owner)}/{html.escape(repo)}</code>\n"
                f"Branch: <code>{html.escape(branch)}</code>\nCommit message: <code>{html.escape(commit_message)}</code>\n"
                f"Reason: <code>{html.escape(detail)}</code>\n\n{hint}"
            )
        except Exception:
            log.warning("Failed to edit status message for user %s", message.from_user.id)
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
