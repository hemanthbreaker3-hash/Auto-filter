# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import re
import time
import datetime
from pymongo.errors import DuplicateKeyError
import motor.motor_asyncio
from pymongo import MongoClient
from info import (
    DATABASE_NAME, USER_DB_URI, OTHER_DB_URI, CUSTOM_FILE_CAPTION, IMDB,
    IMDB_TEMPLATE, MELCOW_NEW_USERS, BUTTON_MODE, SPELL_CHECK_REPLY,
    PROTECT_CONTENT, AUTO_DELETE, MAX_BTN, AUTO_FFILTER, SHORTLINK_API,
    SHORTLINK_URL, SHORTLINK_MODE, TUTORIAL, IS_TUTORIAL, VERIFY, VERIFY_TUTORIAL,
    VERIFY_SECOND_SHORTNER
)

my_client = MongoClient(OTHER_DB_URI)
mydb = my_client["referal_user"]


def normalize_channel_id(value):
    """Normalize a Telegram channel/supergroup ID to standard negative -100 format when numeric."""
    if value is None:
        return None
    s = str(value).strip()
    if not s or not s.lstrip("-").isdigit():
        return None
    num = int(s)
    if num == 0:
        return None
    if num > 0:
        return int(f"-100{num}")
    if not str(num).startswith("-100") and len(str(abs(num))) >= 8:
        return int(f"-100{abs(num)}")
    return num


def parse_duration_to_seconds(raw_value, default=86400):
    """Parse flexible human duration strings (e.g. '30m', '6h', '1d', '2days', '3600') into seconds."""
    if raw_value is None:
        return default
    if isinstance(raw_value, (int, float)):
        val = int(raw_value)
        return val if val > 0 else default
    s = str(raw_value).strip().lower()
    if not s:
        return default
    if s.isdigit():
        val = int(s)
        return val if val > 0 else default
    total = 0
    matched = False
    for qty_str, unit in re.findall(r"(\d+)\s*([a-z]+)", s):
        qty = int(qty_str)
        matched = True
        if unit.startswith(("s", "sec")):
            total += qty
        elif unit.startswith(("m", "min")) and not unit.startswith("mo"):
            total += qty * 60
        elif unit.startswith(("h", "hr", "hour")):
            total += qty * 3600
        elif unit.startswith(("d", "day")):
            total += qty * 86400
        elif unit.startswith(("w", "wk", "week")):
            total += qty * 86400 * 7
        elif unit.startswith(("mo", "month")):
            total += qty * 86400 * 30
        elif unit.startswith(("y", "yr", "year")):
            total += qty * 86400 * 365
    return total if (matched and total > 0) else default


def format_seconds_human(seconds):
    """Return a clean human-readable duration string (e.g. '12h', '1d 6h', '45m')."""
    seconds = max(0, int(seconds or 0))
    if seconds == 0:
        return "0s"
    days, rem = divmod(seconds, 86400)
    hours, rem = divmod(rem, 3600)
    mins, secs = divmod(rem, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if mins:
        parts.append(f"{mins}m")
    if secs and not days and not hours:
        parts.append(f"{secs}s")
    return " ".join(parts) if parts else f"{seconds}s"


async def referal_add_user(user_id, ref_user_id):
    user_db = mydb[str(user_id)]
    user = {'_id': ref_user_id}
    try:
        user_db.insert_one(user)
        return True
    except DuplicateKeyError:
        return False


async def get_referal_all_users(user_id):
    user_db = mydb[str(user_id)]
    return user_db.find()


async def get_referal_users_count(user_id):
    user_db = mydb[str(user_id)]
    count = user_db.count_documents({})
    return count


async def delete_all_referal_users(user_id):
    user_db = mydb[str(user_id)]
    user_db.delete_many({})


default_setgs = {
    'button': BUTTON_MODE,
    'file_secure': PROTECT_CONTENT,
    'imdb': IMDB,
    'spell_check': SPELL_CHECK_REPLY,
    'welcome': MELCOW_NEW_USERS,
    'auto_delete': AUTO_DELETE,
    'auto_ffilter': AUTO_FFILTER,
    'max_btn': MAX_BTN,
    'template': IMDB_TEMPLATE,
    'caption': CUSTOM_FILE_CAPTION,
    'shortlink': SHORTLINK_URL,
    'shortlink_api': SHORTLINK_API,
    'is_shortlink': SHORTLINK_MODE,
    'shortener_mode': 'global',
    'verify_expire_seconds': 86400,
    'verify_credits': 5,
    'fsub': None,
    'tutorial': TUTORIAL,
    'is_tutorial': IS_TUTORIAL
}


class Database:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.col = self.db.users
        self.grp = self.db.groups
        self.users = self.db.uersz
        self.bot = self.db.clone_bots
        self.config = self.db.bot_config
        # Fast in-memory TTL cache to avoid repetitive MongoDB queries on every message
        self._cache = {}
        self._cache_ttl = 45.0
        self._known_users = set()

    def _cache_get(self, key):
        entry = self._cache.get(key)
        if not entry:
            return None
        val, expires_at = entry
        if time.monotonic() > expires_at:
            self._cache.pop(key, None)
            return None
        return val

    def _cache_set(self, key, value, ttl=None):
        self._cache[key] = (value, time.monotonic() + (ttl if ttl is not None else self._cache_ttl))
        return value

    def _cache_invalidate(self, *keys):
        for k in keys:
            self._cache.pop(k, None)

    def new_user(self, id, name):
        return dict(
            id=id,
            name=name,
            file_id=None,
            caption=None,
            message_command=None,
            save=False,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
        )

    def new_group(self, id, title):
        return dict(
            id=id,
            title=title,
            chat_status=dict(
                is_disabled=False,
                reason="",
            ),
            settings=dict(default_setgs)
        )

    async def add_user(self, id, name):
        uid = int(id)
        user = self.new_user(uid, name)
        try:
            await self.col.update_one({'id': uid}, {'$setOnInsert': user}, upsert=True)
        except Exception:
            pass
        self._known_users.add(uid)

    async def is_user_exist(self, id):
        uid = int(id)
        if uid in self._known_users:
            return True
        user = await self.col.find_one({'id': uid}, {'_id': 1})
        if user:
            self._known_users.add(uid)
            return True
        return False

    async def total_users_count(self):
        cached = self._cache_get("total_users_count")
        if cached is not None:
            return cached
        count = await self.col.count_documents({})
        return self._cache_set("total_users_count", count, ttl=15.0)

    async def add_clone_bot(self, bot_id, user_id, bot_token):
        settings = {
            'bot_id': bot_id,
            'bot_token': bot_token,
            'user_id': user_id,
            'url': None,
            'api': None,
            'tutorial': None,
            'update_channel_link': None
        }
        await self.bot.insert_one(settings)

    async def is_clone_exist(self, user_id):
        clone = await self.bot.find_one({'user_id': int(user_id)})
        return bool(clone)

    async def delete_clone(self, user_id):
        await self.bot.delete_many({'user_id': int(user_id)})

    async def get_clone(self, user_id):
        clone_data = await self.bot.find_one({"user_id": user_id})
        return clone_data

    async def update_clone(self, user_id, user_data):
        await self.bot.update_one({"user_id": user_id}, {"$set": user_data}, upsert=True)

    async def get_bot(self, bot_id):
        bot_data = await self.bot.find_one({"bot_id": bot_id})
        return bot_data

    async def update_bot(self, bot_id, bot_data):
        await self.bot.update_one({"bot_id": bot_id}, {"$set": bot_data}, upsert=True)

    async def get_all_bots(self):
        return self.bot.find({})

    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id': int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        uid = int(user_id)
        self._known_users.discard(uid)
        await self.col.delete_many({'id': uid})

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        chats = self.grp.find({'chat_status.is_disabled': True})
        b_chats = [chat['id'] async for chat in chats]
        b_users = [user['id'] async for user in users]
        return b_users, b_chats

    async def add_chat(self, chat, title):
        cid = int(chat)
        chat_doc = self.new_group(cid, title)
        await self.grp.update_one({'id': cid}, {'$setOnInsert': chat_doc}, upsert=True)
        self._cache_invalidate(f"settings:{cid}", "total_chat_count")

    async def get_chat(self, chat):
        chat_doc = await self.grp.find_one({'id': int(chat)})
        return False if not chat_doc else chat_doc.get('chat_status')

    async def re_enable_chat(self, id):
        chat_status = dict(
            is_disabled=False,
            reason="",
        )
        await self.grp.update_one({'id': int(id)}, {'$set': {'chat_status': chat_status}})

    async def update_settings(self, id, settings):
        cid = int(id)
        await self.grp.update_one({'id': cid}, {'$set': {'settings': settings}}, upsert=True)
        merged = dict(default_setgs)
        merged.update(settings or {})
        self._cache_set(f"settings:{cid}", merged)

    async def get_settings(self, id):
        if id is None:
            return dict(default_setgs)
        cid = int(id)
        cached = self._cache_get(f"settings:{cid}")
        if cached is not None:
            return dict(cached)
        chat = await self.grp.find_one({'id': cid})
        merged = dict(default_setgs)
        if chat and isinstance(chat.get('settings'), dict):
            merged.update(chat['settings'])
        self._cache_set(f"settings:{cid}", merged)
        return dict(merged)

    async def disable_chat(self, chat, reason="No Reason"):
        chat_status = dict(
            is_disabled=True,
            reason=reason,
        )
        await self.grp.update_one({'id': int(chat)}, {'$set': {'chat_status': chat_status}})

    async def total_chat_count(self):
        cached = self._cache_get("total_chat_count")
        if cached is not None:
            return cached
        count = await self.grp.count_documents({})
        return self._cache_set("total_chat_count", count, ttl=15.0)

    async def get_all_chats(self):
        return self.grp.find({})

    async def get_db_size(self):
        return (await self.db.command("dbstats"))['dataSize']

    async def get_admins(self):
        """Return persistent admins; deployment admins remain authoritative."""
        doc = await self.config.find_one({"_id": "admins"})
        return sorted(set(int(x) for x in (doc.get("admins", []) if doc else []) if str(x).lstrip("-").isdigit()))

    async def add_admin(self, user_id):
        await self.config.update_one(
            {"_id": "admins"}, {"$addToSet": {"admins": int(user_id)}}, upsert=True
        )

    async def remove_admin(self, user_id):
        await self.config.update_one(
            {"_id": "admins"}, {"$pull": {"admins": int(user_id)}}, upsert=True
        )

    async def get_file_channels_doc(self):
        cached = self._cache_get("config:file_channels")
        if cached is not None:
            return dict(cached)
        doc = await self.config.find_one({"_id": "file_channels"}) or {}
        self._cache_set("config:file_channels", doc, ttl=30.0)
        return dict(doc)

    async def get_managed_channels(self):
        """Return configured file-index channels, including environment defaults."""
        from info import CHANNELS
        doc = await self.get_file_channels_doc()
        saved = doc.get("channels", []) if doc else []
        removed_env = set()
        for item in (doc.get("removed_channels", []) if doc else []):
            norm = normalize_channel_id(item)
            if norm is not None:
                removed_env.add(norm)
        result = set()
        for raw in list(CHANNELS) + list(saved):
            norm = normalize_channel_id(raw)
            if norm is not None and norm not in removed_env:
                result.add(norm)
        return sorted(result)

    async def add_managed_channel(self, channel_id):
        norm = normalize_channel_id(channel_id)
        if norm is None:
            raise ValueError("Invalid channel ID")
        await self.config.update_one(
            {"_id": "file_channels"},
            {
                "$addToSet": {"channels": int(norm)},
                "$pull": {"removed_channels": int(norm)},
            },
            upsert=True
        )
        self._cache_invalidate("config:file_channels")
        return int(norm)

    async def remove_managed_channel(self, channel_id):
        norm = normalize_channel_id(channel_id)
        if norm is None:
            return False
        raw_int = int(channel_id) if str(channel_id).lstrip("-").isdigit() else norm
        await self.config.update_one(
            {"_id": "file_channels"},
            {
                "$pull": {"channels": {"$in": [int(norm), int(raw_int)]}},
                "$addToSet": {"removed_channels": int(norm)},
            },
            upsert=True
        )
        self._cache_invalidate("config:file_channels")
        return True

    async def auto_index_enabled(self):
        doc = await self.get_file_channels_doc()
        return bool(doc.get("auto_index", True)) if doc else True

    async def set_auto_index_enabled(self, enabled):
        await self.config.update_one(
            {"_id": "file_channels"},
            {"$set": {"auto_index": bool(enabled)}},
            upsert=True
        )
        self._cache_invalidate("config:file_channels")
        return bool(enabled)

    async def get_auto_post_channel(self):
        """Return the persistent destination post channel ID configured via /auto."""
        doc = await self.get_file_channels_doc()
        if not doc:
            return None
        val = doc.get("post_channel_id")
        if val is None:
            return None
        norm = normalize_channel_id(val)
        return int(norm) if norm is not None else val

    async def set_auto_post_channel(self, channel_id):
        """Persist the destination post channel ID and enable auto-indexing."""
        norm = normalize_channel_id(channel_id)
        stored = int(norm) if norm is not None else str(channel_id).strip()
        await self.config.update_one(
            {"_id": "file_channels"},
            {"$set": {"post_channel_id": stored, "auto_index": True}},
            upsert=True,
        )
        self._cache_invalidate("config:file_channels")
        return stored

    async def get_auto_post_settings(self):
        """Return full /auto configuration including threshold, series/movie toggles, and destination channel."""
        doc = await self.get_file_channels_doc()
        return {
            "auto_index": bool(doc.get("auto_index", False)),
            "post_channel_id": doc.get("post_channel_id"),
            "min_qualities": max(1, int(doc.get("min_qualities", 3) or 3)),
            "series_enabled": bool(doc.get("series_enabled", True)),
            "movies_enabled": bool(doc.get("movies_enabled", True)),
        }

    async def update_auto_post_settings(self, **kwargs):
        await self.config.update_one(
            {"_id": "file_channels"},
            {"$set": kwargs},
            upsert=True,
        )
        self._cache_invalidate("config:file_channels")
        return await self.get_auto_post_settings()

    async def get_force_subscribe_chats(self):
        """Return dynamically configured force-subscribe channels and groups."""
        cached = self._cache_get("config:fsub_chats")
        if cached is not None:
            return list(cached)
        doc = await self.config.find_one({"_id": "force_subscribe"})
        chats = sorted(set(int(x) for x in (doc.get("chats", []) if doc else []) if str(x).lstrip("-").isdigit()))
        self._cache_set("config:fsub_chats", chats, ttl=30.0)
        return list(chats)

    async def add_force_subscribe_chat(self, chat_id):
        await self.config.update_one(
            {"_id": "force_subscribe"},
            {"$addToSet": {"chats": int(chat_id)}},
            upsert=True
        )
        self._cache_invalidate("config:fsub_chats", "config:fsub_enabled")

    async def remove_force_subscribe_chat(self, chat_id):
        await self.config.update_one(
            {"_id": "force_subscribe"},
            {"$pull": {"chats": int(chat_id)}},
            upsert=True
        )
        self._cache_invalidate("config:fsub_chats", "config:fsub_enabled")

    async def force_subscribe_enabled(self):
        cached = self._cache_get("config:fsub_enabled")
        if cached is not None:
            return bool(cached)
        doc = await self.config.find_one({"_id": "force_subscribe"})
        enabled = bool(doc.get("enabled", True)) if doc else True
        return self._cache_set("config:fsub_enabled", enabled, ttl=30.0)

    async def set_force_subscribe_enabled(self, enabled):
        await self.config.update_one(
            {"_id": "force_subscribe"},
            {"$set": {"enabled": bool(enabled)}},
            upsert=True
        )
        self._cache_invalidate("config:fsub_chats", "config:fsub_enabled")

    # ------------------------------------------------------------------
    # Shortener Pool + Mode Selection (Time Duration / Credits / Per-Link)
    # ------------------------------------------------------------------
    async def get_shortener_pool(self):
        cached = self._cache_get("config:shortener_pool")
        if cached is not None:
            return list(cached)
        cfg = await self.config.find_one({"_id": "panel_shortener_pool"}) or {}
        items = [item for item in cfg.get("items", []) if item.get("url") and item.get("api")]
        self._cache_set("config:shortener_pool", items, ttl=30.0)
        return list(items)

    async def set_shortener_pool(self, items):
        await self.config.update_one(
            {"_id": "panel_shortener_pool"},
            {"$set": {"items": list(items)}},
            upsert=True,
        )
        self._cache_invalidate("config:shortener_pool", "config:shortener_settings")

    async def get_shortener_config(self):
        """Return global shortener mode and verification settings."""
        cached = self._cache_get("config:shortener_settings")
        if cached is not None:
            return dict(cached)
        doc = await self.config.find_one({"_id": "shortener_settings"}) or {}
        pool = await self.get_shortener_pool()
        has_any_shortener = bool(pool or SHORTLINK_URL)
        default_mode = "time" if (VERIFY or has_any_shortener) else ("link" if SHORTLINK_MODE else "off")
        mode = str(doc.get("mode") or default_mode).strip().lower()
        if mode not in ("time", "credits", "link", "off"):
            mode = default_mode
        expire_seconds = parse_duration_to_seconds(doc.get("expire_seconds", 86400), default=86400)
        credits_per_verify = max(1, int(doc.get("credits_per_verify", 5) or 5))
        tutorial_url = str(doc.get("tutorial_url") or VERIFY_TUTORIAL or TUTORIAL or "").strip()
        second_shortener = bool(doc.get("second_shortener", VERIFY_SECOND_SHORTNER))
        result = {
            "mode": mode,
            "expire_seconds": expire_seconds,
            "expire_human": format_seconds_human(expire_seconds),
            "credits_per_verify": credits_per_verify,
            "tutorial_url": tutorial_url,
            "second_shortener": second_shortener,
            "pool_count": len(pool),
        }
        self._cache_set("config:shortener_settings", result, ttl=30.0)
        return dict(result)

    async def update_shortener_config(self, **kwargs):
        updates = {}
        if "mode" in kwargs and kwargs["mode"] is not None:
            m = str(kwargs["mode"]).strip().lower()
            if m in ("time", "duration", "expire", "timer"):
                updates["mode"] = "time"
            elif m in ("credits", "credit", "token", "tokens", "count"):
                updates["mode"] = "credits"
            elif m in ("link", "per_link", "every", "every_file", "shortlink"):
                updates["mode"] = "link"
            elif m in ("off", "disable", "disabled", "none", "direct"):
                updates["mode"] = "off"
        if "expire_seconds" in kwargs and kwargs["expire_seconds"] is not None:
            updates["expire_seconds"] = parse_duration_to_seconds(kwargs["expire_seconds"], default=86400)
        if "credits_per_verify" in kwargs and kwargs["credits_per_verify"] is not None:
            updates["credits_per_verify"] = max(1, int(kwargs["credits_per_verify"]))
        if "tutorial_url" in kwargs and kwargs["tutorial_url"] is not None:
            updates["tutorial_url"] = str(kwargs["tutorial_url"]).strip()
        if "second_shortener" in kwargs and kwargs["second_shortener"] is not None:
            updates["second_shortener"] = bool(kwargs["second_shortener"])
        if updates:
            await self.config.update_one(
                {"_id": "shortener_settings"},
                {"$set": updates},
                upsert=True,
            )
            self._cache_invalidate("config:shortener_settings")
        return await self.get_shortener_config()

    async def get_user_verify_state(self, user_id):
        uid = int(user_id)
        cached = self._cache_get(f"verify_state:{uid}")
        if cached is not None:
            return dict(cached)
        user_data = await self.get_user(uid) or {}
        state = {
            "verified_until": user_data.get("verified_until"),
            "verify_credits": max(0, int(user_data.get("verify_credits", 0) or 0)),
            "total_verifications": max(0, int(user_data.get("total_verifications", 0) or 0)),
        }
        self._cache_set(f"verify_state:{uid}", state, ttl=20.0)
        return dict(state)

    async def grant_user_verification(self, user_id, mode=None, expire_seconds=None, credits_to_add=None):
        """Grant verification access to a user based on active shortener mode (Time Expiry or Credits)."""
        uid = int(user_id)
        cfg = await self.get_shortener_config()
        active_mode = (mode or cfg["mode"]).lower()
        exp_secs = parse_duration_to_seconds(expire_seconds or cfg["expire_seconds"], default=86400)
        add_creds = max(1, int(credits_to_add if credits_to_add is not None else cfg["credits_per_verify"]))

        now = datetime.datetime.now()
        current = await self.get_user_verify_state(uid)
        new_until = current.get("verified_until")
        new_credits = current.get("verify_credits", 0)

        if active_mode == "credits":
            new_credits = new_credits + add_creds
            # Also set a generous 30-day window or keep existing verified_until if valid
            new_until = now + datetime.timedelta(seconds=exp_secs)
        else:
            # Time/Duration mode (also grant credits in case admin switches modes)
            base_time = new_until if (isinstance(new_until, datetime.datetime) and new_until > now) else now
            new_until = base_time + datetime.timedelta(seconds=exp_secs)
            if new_credits <= 0:
                new_credits = add_creds

        total_v = current.get("total_verifications", 0) + 1
        await self.users.update_one(
            {"id": uid},
            {
                "$set": {
                    "id": uid,
                    "verified_until": new_until,
                    "verify_credits": new_credits,
                    "total_verifications": total_v,
                    "last_verified_at": now,
                }
            },
            upsert=True,
        )
        new_state = {
            "verified_until": new_until,
            "verify_credits": new_credits,
            "total_verifications": total_v,
            "granted_mode": active_mode,
            "granted_seconds": exp_secs,
            "granted_credits": add_creds,
        }
        self._cache_set(f"verify_state:{uid}", new_state, ttl=20.0)
        return new_state

    async def set_user_credits(self, user_id, credits):
        uid = int(user_id)
        credits = max(0, int(credits))
        await self.users.update_one(
            {"id": uid},
            {"$set": {"id": uid, "verify_credits": credits}},
            upsert=True,
        )
        self._cache_invalidate(f"verify_state:{uid}")
        return credits

    async def check_and_consume_access(self, user_id, chat_id=None, cost=1, consume=True):
        """Check whether user can access files under the active shortener mode.
        Returns (allowed: bool, details: dict).
        """
        uid = int(user_id)
        cfg = await self.get_shortener_config()
        mode = cfg["mode"]
        expire_seconds = cfg["expire_seconds"]
        credits_per_verify = cfg["credits_per_verify"]

        if chat_id is not None:
            grp_settings = await self.get_settings(chat_id)
            grp_mode = str(grp_settings.get("shortener_mode") or "global").lower()
            if grp_mode in ("time", "credits", "link", "off"):
                mode = grp_mode
            elif grp_settings.get("is_shortlink") and mode == "off":
                mode = "link"
            if grp_settings.get("verify_expire_seconds"):
                expire_seconds = parse_duration_seconds = parse_duration_to_seconds(
                    grp_settings.get("verify_expire_seconds"), default=expire_seconds
                )
            if grp_settings.get("verify_credits"):
                credits_per_verify = max(1, int(grp_settings.get("verify_credits") or credits_per_verify))

        if mode == "off":
            return True, {"mode": "off"}

        if mode == "link":
            return False, {
                "mode": "link",
                "expire_seconds": expire_seconds,
                "credits_per_verify": credits_per_verify,
            }

        state = await self.get_user_verify_state(uid)
        now = datetime.datetime.now()

        if mode == "time":
            verified_until = state.get("verified_until")
            if isinstance(verified_until, datetime.datetime) and verified_until > now:
                rem = int((verified_until - now).total_seconds())
                return True, {
                    "mode": "time",
                    "remaining_seconds": rem,
                    "remaining_human": format_seconds_human(rem),
                    "verified_until": verified_until,
                }
            return False, {
                "mode": "time",
                "expire_seconds": expire_seconds,
                "expire_human": format_seconds_human(expire_seconds),
            }

        if mode == "credits":
            credits = max(0, int(state.get("verify_credits", 0) or 0))
            needed = max(1, int(cost or 1))
            if credits > 0:
                if consume:
                    new_credits = max(0, credits - needed)
                    await self.users.update_one(
                        {"id": uid},
                        {"$set": {"verify_credits": new_credits}},
                        upsert=True,
                    )
                    state["verify_credits"] = new_credits
                    self._cache_set(f"verify_state:{uid}", state, ttl=20.0)
                    credits = new_credits
                return True, {
                    "mode": "credits",
                    "remaining_credits": credits,
                    "credits_per_verify": credits_per_verify,
                }
            return False, {
                "mode": "credits",
                "remaining_credits": 0,
                "credits_per_verify": credits_per_verify,
            }

        return True, {"mode": mode}

    async def get_user(self, user_id):
        user_data = await self.users.find_one({"id": int(user_id)})
        return user_data

    async def update_user(self, user_data):
        uid = int(user_data["id"])
        await self.users.update_one({"id": uid}, {"$set": user_data}, upsert=True)
        self._cache_invalidate(f"verify_state:{uid}", f"premium:{uid}")

    async def has_premium_access(self, user_id):
        uid = int(user_id)
        cached = self._cache_get(f"premium:{uid}")
        if cached is not None:
            return bool(cached)
        user_data = await self.get_user(uid)
        if user_data:
            expiry_time = user_data.get("expiry_time")
            if expiry_time is None:
                return self._cache_set(f"premium:{uid}", False, ttl=20.0)
            elif isinstance(expiry_time, datetime.datetime) and datetime.datetime.now() <= expiry_time:
                return self._cache_set(f"premium:{uid}", True, ttl=20.0)
            else:
                await self.users.update_one({"id": uid}, {"$set": {"expiry_time": None}})
        return self._cache_set(f"premium:{uid}", False, ttl=20.0)

    async def check_remaining_uasge(self, userid):
        user_data = await self.get_user(int(userid))
        if not user_data or not user_data.get("expiry_time"):
            return datetime.timedelta(0)
        return max(datetime.timedelta(0), user_data.get("expiry_time") - datetime.datetime.now())

    async def get_free_trial_status(self, user_id):
        user_data = await self.get_user(int(user_id))
        if user_data:
            return user_data.get("has_free_trial", False)
        return False

    async def give_free_trail(self, userid):
        user_id = int(userid)
        seconds = 5 * 60
        expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
        user_data = {"id": user_id, "expiry_time": expiry_time, "has_free_trial": True}
        await self.users.update_one({"id": user_id}, {"$set": user_data}, upsert=True)
        self._cache_invalidate(f"premium:{user_id}")

    async def all_premium_users(self):
        count = await self.users.count_documents({
            "expiry_time": {"$gt": datetime.datetime.now()}
        })
        return count

    async def set_thumbnail(self, id, file_id):
        await self.col.update_one({'id': int(id)}, {'$set': {'file_id': file_id}})

    async def get_thumbnail(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('file_id', None) if user else None

    async def set_caption(self, id, caption):
        await self.col.update_one({'id': int(id)}, {'$set': {'caption': caption}})

    async def get_caption(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('caption', None) if user else None

    async def set_msg_command(self, id, com):
        await self.col.update_one({'id': int(id)}, {'$set': {'message_command': com}})

    async def get_msg_command(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('message_command', None) if user else None

    async def set_save(self, id, save):
        await self.col.update_one({'id': int(id)}, {'$set': {'save': save}})

    async def get_save(self, id):
        user = await self.col.find_one({'id': int(id)})
        return user.get('save', False) if user else False

    async def get_link_feature(self, feature):
        """Return persistent global stream/download switch (enabled by default)."""
        cached = self._cache_get(f"link_feature:{feature}")
        if cached is not None:
            return bool(cached)
        doc = await self.config.find_one({"_id": "link_features"}) or {}
        val = bool(doc.get(feature, True))
        return self._cache_set(f"link_feature:{feature}", val, ttl=30.0)

    async def set_link_feature(self, feature, enabled):
        await self.config.update_one(
            {"_id": "link_features"},
            {"$set": {feature: bool(enabled)}},
            upsert=True,
        )
        self._cache_invalidate(f"link_feature:{feature}")
        return bool(enabled)


db = Database(USER_DB_URI, DATABASE_NAME)
