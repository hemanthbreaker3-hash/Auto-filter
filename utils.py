# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import logging, asyncio, os, re, random, pytz, aiohttp, requests, string, json, http.client, html as html_lib
from info import *
from imdb import Cinemagoer
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from TechVJ.util.telegram_rich import ButtonStyle, get_http_session
from pyrogram import enums
from pyrogram.errors import *
from typing import Union, List
from Script import script
from datetime import datetime, date
from database.users_chats_db import db, parse_duration_to_seconds, format_seconds_human
from database.join_reqs import JoinReqs
from bs4 import BeautifulSoup
from shortzy import Shortzy

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
join_db = JoinReqs
BTN_URL_REGEX = re.compile(r"(\[([^\[]+?)\]\((buttonurl|buttonalert):(?:/{0,2})(.+?)(:same)?\))")

try:
    imdb = Cinemagoer()
except Exception as e:
    logger.error(f"Cinemagoer failed to initialize, IMDb lookups will be disabled: {e}")
    imdb = None

TOKENS = {}
VERIFIED = {}
BANNED = {}
SECOND_SHORTENER = {}
SMART_OPEN = '“'
SMART_CLOSE = '”'
START_CHAR = ('\'', '"', SMART_OPEN)


class temp(object):
    BANNED_USERS = []
    BANNED_CHATS = []
    ME = None
    BOT = None
    CURRENT = int(os.environ.get("SKIP", 2))
    CANCEL = False
    MELCOW = {}
    U_NAME = None
    B_NAME = None
    GETALL = {}
    SHORT = {}
    SETTINGS = {}
    IMDB_CAP = {}


def format_file_caption(raw_caption, fallback_name="", update_link=None):
    """Wrap the entire file caption in an HTML hyperlink to the update channel without editing the caption text."""
    link = (update_link or CHNL_LNK or OWNER_LNK or "").strip()
    text = ""
    if raw_caption is not None and str(raw_caption).strip():
        raw_str = str(raw_caption)
        if "<" in raw_str and ">" in raw_str:
            cleaned = html_lib.unescape(re.sub(r"<[^>]+>", "", raw_str))
            text = cleaned if cleaned.strip() else raw_str
        else:
            text = raw_str
    if not text.strip():
        fb = str(fallback_name or "").strip()
        for _pfx in ("@MoviesZoneFlix ", "@TGBoxOffice "):
            if fb.startswith(_pfx):
                fb = fb[len(_pfx):].strip() or fb
        if "<" in fb and ">" in fb:
            fb = html_lib.unescape(re.sub(r"<[^>]+>", "", fb)).strip() or fb
        text = fb or "File"
    if len(text) > 950:
        text = text[:947] + "..."
    escaped_text = html_lib.escape(text)
    if link:
        escaped_link = html_lib.escape(link, quote=True)
        return f'<a href="{escaped_link}">{escaped_text}</a>'
    return escaped_text


async def get_file_stream_markup(file_id: str):
    """Return the stream/download InlineKeyboardMarkup for a file, or None when stream and download are disabled."""
    if not STREAM_MODE:
        return None
    stream_enabled = await db.get_link_feature("stream_enabled")
    download_enabled = await db.get_link_feature("download_enabled")
    if not stream_enabled and not download_enabled:
        return None
    if stream_enabled and download_enabled:
        label = "sᴛʀᴇᴀᴍ ᴀɴᴅ ᴅᴏᴡɴʟᴏᴀᴅ"
    elif stream_enabled:
        label = "• sᴛʀᴇᴀᴍ •"
    else:
        label = "• ᴅᴏᴡɴʟᴏᴀᴅ •"
    return InlineKeyboardMarkup([[InlineKeyboardButton(label, callback_data=f"generate_stream_link:{file_id}", style=ButtonStyle.DANGER)]])


async def get_force_subscribe_chats():
    """Get environment and panel-managed force-subscribe destinations."""
    from info import AUTH_CHANNEL
    configured = []
    if AUTH_CHANNEL:
        configured.append(int(AUTH_CHANNEL))
    try:
        if await db.force_subscribe_enabled():
            configured.extend(await db.get_force_subscribe_chats())
    except Exception as exc:
        logger.warning("Could not load panel force-subscribe settings: %s", exc)
    return list(dict.fromkeys(configured))


async def has_force_subscribe():
    return bool(await get_force_subscribe_chats())


async def _chat_join_url(bot, chat):
    if getattr(chat, "username", None):
        return f"https://t.me/{chat.username}"
    if getattr(chat, "invite_link", None):
        return chat.invite_link
    try:
        invite = await bot.create_chat_invite_link(chat.id)
        return invite.invite_link
    except Exception:
        return None


async def pub_is_subscribed(bot, query, channel):
    """Return join buttons for destinations where the user is not a member."""
    btn = []
    user_id = getattr(getattr(query, "from_user", None), "id", None)
    if not user_id:
        return btn
    for chat_id in channel or []:
        try:
            chat = await bot.get_chat(int(chat_id))
            member = await bot.get_chat_member(chat.id, user_id)
            status = getattr(member, "status", None)
            is_member = status in (
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
                enums.ChatMemberStatus.MEMBER,
            )
            if status == enums.ChatMemberStatus.RESTRICTED:
                is_member = bool(getattr(member, "is_member", False))
            if is_member:
                continue
        except UserNotParticipant:
            try:
                chat = await bot.get_chat(int(chat_id))
            except Exception:
                continue
        except Exception as exc:
            logger.warning("FSub membership check failed for %s: %s", chat_id, exc)
            continue
        link = await _chat_join_url(bot, chat)
        if link:
            title = (getattr(chat, "title", None) or str(chat_id)).strip()
            btn.append([InlineKeyboardButton(f"Join {title[:45]}", url=link, style=ButtonStyle.SUCCESS)])
    return btn


async def is_subscribed(bot, query):
    """Require membership in every configured global FSub channel/group."""
    channels = await get_force_subscribe_chats()
    if not channels:
        return True

    user_id = getattr(getattr(query, "from_user", None), "id", None)
    if not user_id:
        return False

    request_approved = False
    if REQUEST_TO_JOIN_MODE and join_db().isActive():
        try:
            request_user = await join_db().get_user(user_id)
            request_approved = bool(request_user and request_user.get("user_id") == user_id)
        except Exception:
            logger.exception("Could not check force-subscribe join request")

    from info import AUTH_CHANNEL
    for chat_id in channels:
        if request_approved and AUTH_CHANNEL and int(chat_id) == int(AUTH_CHANNEL):
            continue
        try:
            member = await bot.get_chat_member(int(chat_id), user_id)
            status = getattr(member, "status", None)
            allowed = status in (
                enums.ChatMemberStatus.OWNER,
                enums.ChatMemberStatus.ADMINISTRATOR,
                enums.ChatMemberStatus.MEMBER,
            )
            if status == enums.ChatMemberStatus.RESTRICTED:
                allowed = bool(getattr(member, "is_member", False))
            if not allowed:
                return False
        except UserNotParticipant:
            return False
        except Exception as exc:
            logger.warning("Global FSub check failed for %s: %s", chat_id, exc)
            return False
    return True


async def get_poster(query, bulk=False, id=False, file=None):
    if imdb is None:
        return None
    if not id:
        query = (query.strip()).lower()
        title = query
        year = re.findall(r'[1-2]\d{3}$', query, re.IGNORECASE)
        if year:
            year = list_to_str(year[:1])
            title = (query.replace(year, "")).strip()
        elif file is not None:
            year = re.findall(r'[1-2]\d{3}', file, re.IGNORECASE)
            if year:
                year = list_to_str(year[:1])
        else:
            year = None
        try:
            movieid = await asyncio.to_thread(imdb.search_movie, title.lower(), results=10)
        except Exception as e:
            logger.error(f"IMDb search failed for '{title}': {e}")
            return None
        if not movieid:
            return None
        if year:
            filtered = list(filter(lambda k: str(k.get('year')) == str(year), movieid))
            if not filtered:
                filtered = movieid
        else:
            filtered = movieid
        movieid = list(filter(lambda k: k.get('kind') in ['movie', 'tv series'], filtered))
        if not movieid:
            movieid = filtered
        if bulk:
            return movieid
        movieid = movieid[0].movieID
    else:
        movieid = query
    try:
        movie = await asyncio.to_thread(imdb.get_movie, movieid)
    except Exception as e:
        logger.error(f"IMDb get_movie failed for id '{movieid}': {e}")
        return None
    if not movie:
        return None
    if movie.get("original air date"):
        rel_date = movie["original air date"]
    elif movie.get("year"):
        rel_date = movie.get("year")
    else:
        rel_date = "N/A"
    plot = ""
    if not LONG_IMDB_DESCRIPTION:
        plot = movie.get('plot')
        if plot and len(plot) > 0:
            plot = plot[0]
    else:
        plot = movie.get('plot outline')
    if plot and len(plot) > 800:
        plot = plot[0:800] + "..."

    return {
        'title': movie.get('title'),
        'votes': movie.get('votes'),
        "aka": list_to_str(movie.get("akas")),
        "seasons": movie.get("number of seasons"),
        "box_office": movie.get('box office'),
        'localized_title': movie.get('localized title'),
        'kind': movie.get("kind"),
        "imdb_id": f"tt{movie.get('imdbID')}",
        "cast": list_to_str(movie.get("cast")),
        "runtime": list_to_str(movie.get("runtimes")),
        "countries": list_to_str(movie.get("countries")),
        "certificates": list_to_str(movie.get("certificates")),
        "languages": list_to_str(movie.get("languages")),
        "director": list_to_str(movie.get("director")),
        "writer": list_to_str(movie.get("writer")),
        "producer": list_to_str(movie.get("producer")),
        "composer": list_to_str(movie.get("composer")),
        "cinematographer": list_to_str(movie.get("cinematographer")),
        "music_team": list_to_str(movie.get("music department")),
        "distributors": list_to_str(movie.get("distributors")),
        'release_date': rel_date,
        'year': movie.get('year'),
        'genres': list_to_str(movie.get("genres")),
        'poster': movie.get('full-size cover url'),
        'plot': plot,
        'rating': str(movie.get("rating")),
        'url': f'https://www.imdb.com/title/tt{movieid}'
    }


async def broadcast_messages(user_id, message):
    try:
        await message.copy(chat_id=user_id)
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
        return await broadcast_messages(user_id, message)
    except InputUserDeactivated:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id}-Removed from Database, since deleted account.")
        return False, "Deleted"
    except UserIsBlocked:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} -Blocked the bot.")
        return False, "Blocked"
    except PeerIdInvalid:
        await db.delete_user(int(user_id))
        logging.info(f"{user_id} - PeerIdInvalid")
        return False, "Error"
    except Exception:
        return False, "Error"


async def broadcast_messages_group(chat_id, message):
    try:
        kd = await message.copy(chat_id=chat_id)
        try:
            await kd.pin()
        except Exception:
            pass
        return True, "Success"
    except FloodWait as e:
        await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
        return await broadcast_messages_group(chat_id, message)
    except Exception:
        return False, "Error"


async def search_gagala(text):
    usr_agent = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/120.0.0.0 Safari/537.36'
    }
    text = text.replace(" ", '+')
    url = f'https://www.google.com/search?q={text}'
    try:
        session = get_http_session()
        async with session.get(url, headers=usr_agent) as resp:
            if resp.status != 200:
                return []
            body = await resp.text()
        soup = BeautifulSoup(body, 'html.parser')
        titles = soup.find_all('h3')
        return [title.getText() for title in titles]
    except Exception:
        return []


async def get_settings(group_id):
    return await db.get_settings(group_id)


async def save_group_settings(group_id, key, value):
    current = await get_settings(group_id)
    current.update({key: value})
    await db.update_settings(group_id, current)


def get_size(size):
    units = ["Bytes", "KB", "MB", "GB", "TB", "PB", "EB"]
    size = float(size or 0)
    i = 0
    while size >= 1024.0 and i < len(units) - 1:
        i += 1
        size /= 1024.0
    return "%.2f %s" % (size, units[i])


def split_list(l, n):
    for i in range(0, len(l), n):
        yield l[i:i + n]


def get_file_id(msg: Message):
    if msg.media:
        for message_type in (
            "photo",
            "animation",
            "audio",
            "document",
            "video",
            "video_note",
            "voice",
            "sticker"
        ):
            obj = getattr(msg, message_type, None)
            if obj:
                setattr(obj, "message_type", message_type)
                return obj


def extract_user(message: Message) -> Union[int, str]:
    user_id = None
    user_first_name = None
    if message.reply_to_message:
        user_id = message.reply_to_message.from_user.id
        user_first_name = message.reply_to_message.from_user.first_name
    elif len(message.command) > 1:
        if (
            len(message.entities) > 1 and
            message.entities[1].type == enums.MessageEntityType.TEXT_MENTION
        ):
            required_entity = message.entities[1]
            user_id = required_entity.user.id
            user_first_name = required_entity.user.first_name
        else:
            user_id = message.command[1]
            user_first_name = user_id
        try:
            user_id = int(user_id)
        except ValueError:
            pass
    else:
        user_id = message.from_user.id
        user_first_name = message.from_user.first_name
    return (user_id, user_first_name)


def list_to_str(k):
    if not k:
        return "N/A"
    elif len(k) == 1:
        return str(k[0])
    elif MAX_LIST_ELM:
        k = k[:int(MAX_LIST_ELM)]
        return ' '.join(f'{elem}, ' for elem in k)
    else:
        return ' '.join(f'{elem}, ' for elem in k)


def last_online(from_user):
    t = ""
    if from_user.is_bot:
        t += "🤖 Bot :("
    elif from_user.status == enums.UserStatus.RECENTLY:
        t += "Recently"
    elif from_user.status == enums.UserStatus.LAST_WEEK:
        t += "Within the last week"
    elif from_user.status == enums.UserStatus.LAST_MONTH:
        t += "Within the last month"
    elif from_user.status == enums.UserStatus.LONG_AGO:
        t += "A long time ago :("
    elif from_user.status == enums.UserStatus.ONLINE:
        t += "Currently Online"
    elif from_user.status == enums.UserStatus.OFFLINE:
        t += from_user.last_online_date.strftime("%a, %d %b %Y, %H:%M:%S")
    return t


def split_quotes(text: str) -> List:
    if not any(text.startswith(char) for char in START_CHAR):
        return text.split(None, 1)
    counter = 1
    while counter < len(text):
        if text[counter] == "\\":
            counter += 1
        elif text[counter] == text[0] or (text[0] == SMART_OPEN and text[counter] == SMART_CLOSE):
            break
        counter += 1
    else:
        return text.split(None, 1)

    key = remove_escapes(text[1:counter].strip())
    rest = text[counter + 1:].strip()
    if not key:
        key = text[0] + text[0]
    return list(filter(None, [key, rest]))


def gfilterparser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}", style=ButtonStyle.DANGER))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"gfilteralert:{i}:{keyword}", style=ButtonStyle.DANGER)])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", ""), style=ButtonStyle.PRIMARY))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", ""), style=ButtonStyle.PRIMARY)])
        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except Exception:
        return note_data, buttons, None


def parser(text, keyword):
    if "buttonalert" in text:
        text = (text.replace("\n", "\\n").replace("\t", "\\t"))
    buttons = []
    note_data = ""
    prev = 0
    i = 0
    alerts = []
    for match in BTN_URL_REGEX.finditer(text):
        n_escapes = 0
        to_check = match.start(1) - 1
        while to_check > 0 and text[to_check] == "\\":
            n_escapes += 1
            to_check -= 1

        if n_escapes % 2 == 0:
            note_data += text[prev:match.start(1)]
            prev = match.end(1)
            if match.group(3) == "buttonalert":
                if bool(match.group(5)) and buttons:
                    buttons[-1].append(InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}", style=ButtonStyle.DANGER))
                else:
                    buttons.append([InlineKeyboardButton(
                        text=match.group(2),
                        callback_data=f"alertmessage:{i}:{keyword}", style=ButtonStyle.DANGER)])
                i += 1
                alerts.append(match.group(4))
            elif bool(match.group(5)) and buttons:
                buttons[-1].append(InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", ""), style=ButtonStyle.PRIMARY))
            else:
                buttons.append([InlineKeyboardButton(
                    text=match.group(2),
                    url=match.group(4).replace(" ", ""), style=ButtonStyle.PRIMARY)])
        else:
            note_data += text[prev:to_check]
            prev = match.start(1) - 1
    else:
        note_data += text[prev:]

    try:
        return note_data, buttons, alerts
    except Exception:
        return note_data, buttons, None


def remove_escapes(text: str) -> str:
    res = ""
    is_escaped = False
    for counter in range(len(text)):
        if is_escaped:
            res += text[counter]
            is_escaped = False
        elif text[counter] == "\\":
            is_escaped = True
        else:
            res += text[counter]
    return res


def humanbytes(size):
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'


async def _convert_with_shortener(link: str, url: str, api: str) -> str:
    """Convert a URL using a shortener domain + API key with automatic REST fallback."""
    domain = str(url or "").strip().removeprefix("https://").removeprefix("http://").strip("/")
    api_key = str(api or "").strip()
    if not domain or not api_key:
        return link

    session = get_http_session()
    if domain == "api.shareus.io":
        endpoint = f"https://{domain}/easy_api"
        params = {"key": api_key, "link": link}
        try:
            async with session.get(endpoint, params=params, ssl=False) as response:
                data = (await response.text()).strip()
                if data.startswith("http"):
                    return data
        except Exception as e:
            logger.error("shareus shortener error: %s", e)
        return link

    # Standard AdLinkFly / GPLinks / ShrinkMe / KPSLink JSON API call via pooled session
    try:
        api_endpoint = f"https://{domain}/api"
        params = {"api": api_key, "url": link}
        async with session.get(api_endpoint, params=params, ssl=False) as response:
            data = await response.json(content_type=None)
            if isinstance(data, dict):
                shortened = data.get("shortenedUrl") or data.get("short_url") or data.get("url")
                if shortened and str(shortened).startswith("http"):
                    return str(shortened)
    except Exception:
        pass

    try:
        shortzy = Shortzy(api_key=api_key, base_site=domain)
        converted = await shortzy.convert(link)
        if converted:
            return str(converted)
    except Exception as e:
        logger.warning("Shortzy fallback failed for %s: %s", domain, e)
    return link


async def _resolve_active_shortener(chat_id=None, for_verify=False):
    """Resolve (domain, api_key) from group settings, panel shortener pool, or env defaults."""
    if chat_id is not None:
        settings = await get_settings(chat_id)
        grp_url = str(settings.get("shortlink") or "").strip()
        grp_api = str(settings.get("shortlink_api") or "").strip()
        if grp_url and grp_api and not grp_url.startswith(("shorturllink", "terabox.in", "urlshorten.in")):
            return grp_url, grp_api

    try:
        pool = await db.get_shortener_pool()
        if pool:
            selected = random.choice(pool)
            return selected["url"], selected["api"]
    except Exception as pool_error:
        logger.warning("Shortener pool lookup failed: %s", pool_error)

    if for_verify and VERIFY_SHORTLINK_URL and VERIFY_SHORTLINK_API:
        return VERIFY_SHORTLINK_URL, VERIFY_SHORTLINK_API
    if SHORTLINK_URL and SHORTLINK_API:
        return SHORTLINK_URL, SHORTLINK_API
    if VERIFY_SHORTLINK_URL and VERIFY_SHORTLINK_API:
        return VERIFY_SHORTLINK_URL, VERIFY_SHORTLINK_API
    return "", ""


async def is_verification_needed(chat_id=None) -> bool:
    """Return True when verification (Time or Credits mode) is active and a shortener is configured."""
    cfg = await db.get_shortener_config()
    mode = cfg.get("mode", "off")
    if chat_id is not None:
        settings = await get_settings(chat_id)
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        if grp_mode in ("time", "credits", "link", "off"):
            mode = grp_mode
    if mode not in ("time", "credits"):
        return False
    url, api = await _resolve_active_shortener(chat_id=chat_id, for_verify=True)
    return bool(url and api)


async def get_clone_shortlink(link, url, api):
    return await _convert_with_shortener(link, url, api)


async def get_shortlink(chat_id, link):
    url, api = await _resolve_active_shortener(chat_id=chat_id, for_verify=False)
    return await _convert_with_shortener(link, url, api)


async def get_tutorial(chat_id=None):
    if chat_id is not None:
        settings = await get_settings(chat_id)
        if settings.get('tutorial'):
            return settings['tutorial']
    cfg = await db.get_shortener_config()
    return cfg.get("tutorial_url") or TUTORIAL or VERIFY_TUTORIAL or ""


async def get_verify_shorted_link(link, url="", api="", chat_id=None):
    if not url or not api:
        url, api = await _resolve_active_shortener(chat_id=chat_id, for_verify=True)
    return await _convert_with_shortener(link, url, api)


async def check_token(bot, userid, token):
    uid = int(userid)
    if not await db.is_user_exist(uid):
        try:
            user = await bot.get_users(uid)
            await db.add_user(user.id, user.first_name)
            if LOG_CHANNEL:
                await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
        except Exception:
            pass
    if uid in TOKENS and token in TOKENS[uid]:
        entry = TOKENS[uid][token]
        if isinstance(entry, dict):
            return not bool(entry.get("used", False))
        return not bool(entry)
    # Check MongoDB fallback token store so bot restarts never invalidate active links
    doc = await db.config.find_one({"_id": f"verify_token:{uid}:{token}"})
    if doc and not doc.get("used", False):
        TOKENS.setdefault(uid, {})[token] = {"used": False, "pending": doc.get("pending")}
        return True
    return False


async def get_token(bot, userid, link, pending_data=None, chat_id=None):
    uid = int(userid)
    if not await db.is_user_exist(uid):
        try:
            user = await bot.get_users(uid)
            await db.add_user(user.id, user.first_name)
            if LOG_CHANNEL:
                await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
        except Exception:
            pass
    token = ''.join(random.choices(string.ascii_letters + string.digits, k=7))
    TOKENS[uid] = {token: {"used": False, "pending": pending_data, "chat_id": chat_id}}
    try:
        await db.config.update_one(
            {"_id": f"verify_token:{uid}:{token}"},
            {"$set": {"used": False, "pending": pending_data, "chat_id": chat_id, "created_at": datetime.utcnow()}},
            upsert=True,
        )
    except Exception:
        pass
    verify_url = f"{link}verify-{uid}-{token}"
    url, api = await _resolve_active_shortener(chat_id=chat_id, for_verify=True)
    shortened_verify_url = await get_verify_shorted_link(verify_url, url, api, chat_id=chat_id)
    cfg = await db.get_shortener_config()
    if (cfg.get("second_shortener") or VERIFY_SECOND_SHORTNER) and VERIFY_SND_SHORTLINK_URL and VERIFY_SND_SHORTLINK_API:
        snd_link = await get_verify_shorted_link(shortened_verify_url, VERIFY_SND_SHORTLINK_URL, VERIFY_SND_SHORTLINK_API)
        return str(snd_link)
    return str(shortened_verify_url)


async def verify_user(bot, userid, token):
    """Complete token verification and grant the user either Expire Duration or Credits based on active mode."""
    uid = int(userid)
    if not await db.is_user_exist(uid):
        try:
            user = await bot.get_users(uid)
            await db.add_user(user.id, user.first_name)
            if LOG_CHANNEL:
                await bot.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(user.id, user.mention))
        except Exception:
            pass
    pending_data = None
    chat_id = None
    if uid in TOKENS and token in TOKENS[uid]:
        entry = TOKENS[uid][token]
        if isinstance(entry, dict):
            pending_data = entry.get("pending")
            chat_id = entry.get("chat_id")
            entry["used"] = True
        else:
            TOKENS[uid][token] = True
    try:
        doc = await db.config.find_one_and_update(
            {"_id": f"verify_token:{uid}:{token}"},
            {"$set": {"used": True}},
        )
        if doc and not pending_data:
            pending_data = doc.get("pending")
            chat_id = doc.get("chat_id")
    except Exception:
        pass

    VERIFIED[uid] = str(date.today())
    mode = None
    exp_secs = None
    creds = None
    if chat_id is not None:
        settings = await get_settings(chat_id)
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        if grp_mode in ("time", "credits"):
            mode = grp_mode
        if settings.get("verify_expire_seconds"):
            exp_secs = settings.get("verify_expire_seconds")
        if settings.get("verify_credits"):
            creds = settings.get("verify_credits")

    granted = await db.grant_user_verification(uid, mode=mode, expire_seconds=exp_secs, credits_to_add=creds)
    granted["pending"] = pending_data
    return granted


async def check_verification(bot, userid, chat_id=None, cost=1, consume=True):
    """Verify whether the user has active access under the configured Shortener Mode (Time or Credits)."""
    uid = int(userid)
    if not await is_verification_needed(chat_id=chat_id):
        return True
    allowed, _details = await db.check_and_consume_access(uid, chat_id=chat_id, cost=cost, consume=consume)
    return allowed


async def build_verification_prompt(bot, userid, user_mention, base_start_url, pending_data=None, chat_id=None):
    """Build the verification message text and inline keyboard adapted to the active Shortener Mode (Time vs Credits)."""
    cfg = await db.get_shortener_config()
    mode = cfg["mode"]
    exp_human = cfg["expire_human"]
    creds_count = cfg["credits_per_verify"]
    tutorial = await get_tutorial(chat_id)

    if chat_id is not None:
        settings = await get_settings(chat_id)
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        if grp_mode in ("time", "credits"):
            mode = grp_mode
        if settings.get("verify_expire_seconds"):
            exp_human = format_seconds_human(settings.get("verify_expire_seconds"))
        if settings.get("verify_credits"):
            creds_count = int(settings.get("verify_credits"))

    verify_url = await get_token(bot, userid, base_start_url, pending_data=pending_data, chat_id=chat_id)
    btn = [[InlineKeyboardButton("🔐 ᴠᴇʀɪғʏ ɴᴏᴡ & ᴜɴʟᴏᴄᴋ", url=verify_url, style=ButtonStyle.SUCCESS)]]
    if tutorial and str(tutorial).startswith("http"):
        btn.append([InlineKeyboardButton("🎬 ʜᴏᴡ ᴛᴏ ᴠᴇʀɪғʏ (ᴛᴜᴛᴏʀɪᴀʟ)", url=str(tutorial), style=ButtonStyle.PRIMARY)])

    if mode == "credits":
        text = (
            f"<b><blockquote>🔐 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗩𝗘𝗥𝗜𝗙𝗜𝗖𝗔𝗧𝗜𝗢𝗡 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗</blockquote>\n\n"
            f"👋 Hey {user_mention},\n"
            f"💳 Your download credits have reached <code>0</code>.\n\n"
            f"✨ Complete 1 quick verification below to instantly unlock <b>+{creds_count} File Credits</b>!</b>"
        )
    else:
        text = (
            f"<b><blockquote>🔐 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗩𝗘𝗥𝗜𝗙𝗜𝗖𝗔𝗧𝗜𝗢𝗡 𝗥𝗘𝗤𝗨𝗜𝗥𝗘𝗗</blockquote>\n\n"
            f"👋 Hey {user_mention},\n"
            f"⏳ Your verification pass is not active or has expired.\n\n"
            f"✨ Complete 1 quick verification below to unlock <b>Unlimited Direct Files for {exp_human}</b>!</b>"
        )

    if PREMIUM_AND_REFERAL_MODE:
        text += "\n\n💎 <i>Want instant direct files with zero ads? Send /plan to upgrade to Premium!</i>"
    return text, InlineKeyboardMarkup(btn)


async def send_all(bot, userid, files, ident, chat_id, user_name, query):
    settings = await get_settings(chat_id)
    cfg = await db.get_shortener_config()
    grp_mode = str(settings.get("shortener_mode") or "global").lower()
    effective_mode = grp_mode if grp_mode in ("time", "credits", "link", "off") else cfg["mode"]
    is_premium = await db.has_premium_access(userid)

    try:
        if not is_premium and effective_mode == "link" and (settings.get("is_shortlink") or SHORTLINK_MODE or cfg["pool_count"] > 0):
            for file in files:
                title = file["file_name"]
                size = get_size(file["file_size"])
                short_url = await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}")
                await bot.send_message(
                    chat_id=userid,
                    text=(
                        f"<b>👋 Hey {html_lib.escape(str(user_name or 'there'))}\n\n"
                        f"✅ Your download link is ready:\n\n"
                        f"🗃️ <b>File:</b> <code>{html_lib.escape(str(title))}</code>\n"
                        f"🔖 <b>Size:</b> <code>{size}</code></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("📤 Dᴏᴡɴʟᴏᴀᴅ 📥", url=short_url, style=ButtonStyle.SUCCESS)]]),
                )
            return

        if not is_premium and effective_mode in ("time", "credits") and await is_verification_needed(chat_id=chat_id):
            allowed = await check_verification(bot, userid, chat_id=chat_id, cost=1, consume=True)
            if not allowed:
                v_text, v_markup = await build_verification_prompt(
                    bot,
                    userid,
                    f'<a href="tg://user?id={userid}">{html_lib.escape(str(user_name or "User"))}</a>',
                    f"https://telegram.me/{temp.U_NAME}?start=",
                    chat_id=chat_id,
                )
                await bot.send_message(chat_id=userid, text=v_text, reply_markup=v_markup, protect_content=True)
                return

        for file in files:
            f_caption = format_file_caption(file.get("caption"), file.get("file_name"), CHNL_LNK)
            reply_markup = await get_file_stream_markup(file["file_id"])
            await bot.send_cached_media(
                chat_id=userid,
                file_id=file["file_id"],
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML,
                protect_content=True if ident == "filep" else False,
                reply_markup=reply_markup
            )
    except UserIsBlocked:
        await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
    except PeerIdInvalid:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)
    except Exception:
        await query.answer('Hᴇʏ, Sᴛᴀʀᴛ Bᴏᴛ Fɪʀsᴛ Aɴᴅ Cʟɪᴄᴋ Sᴇɴᴅ Aʟʟ', show_alert=True)


async def get_cap(settings, remaining_seconds, files, query, total_results, search):
    if settings["imdb"]:
        IMDB_CAP = temp.IMDB_CAP.get(query.from_user.id)
        if IMDB_CAP:
            cap = IMDB_CAP
            cap += "<b>\n\n<u>🍿 Your Movie & Series Files 👇</u></b>\n\n"
            for file in files:
                cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', file['file_name']).split()))}\n\n</a></b>"
        else:
            imdb_data = await get_poster(search, file=(files[0])["file_name"]) if settings["imdb"] else None
            if imdb_data:
                TEMPLATE = script.IMDB_TEMPLATE_TXT
                cap = TEMPLATE.format(
                    qurey=search,
                    support=f"🔗 <b>Support:</b> <a href='https://t.me/{SUPPORT_CHAT}'>Join Support Group</a>" if SUPPORT_CHAT else "",
                    title=imdb_data['title'],
                    votes=imdb_data['votes'],
                    aka=imdb_data["aka"],
                    seasons=imdb_data["seasons"],
                    box_office=imdb_data['box_office'],
                    localized_title=imdb_data['localized_title'],
                    kind=imdb_data['kind'],
                    imdb_id=imdb_data["imdb_id"],
                    cast=imdb_data["cast"],
                    runtime=imdb_data["runtime"],
                    countries=imdb_data["countries"],
                    certificates=imdb_data["certificates"],
                    languages=imdb_data["languages"],
                    director=imdb_data["director"],
                    writer=imdb_data["writer"],
                    producer=imdb_data["producer"],
                    composer=imdb_data["composer"],
                    cinematographer=imdb_data["cinematographer"],
                    music_team=imdb_data["music_team"],
                    distributors=imdb_data["distributors"],
                    release_date=imdb_data['release_date'],
                    year=imdb_data['year'],
                    genres=imdb_data['genres'],
                    poster=imdb_data['poster'],
                    plot=imdb_data['plot'],
                    rating=imdb_data['rating'],
                    url=imdb_data['url'],
                    **locals()
                )
                cap += "<b>\n\n<u>🍿 Your Movie & Series Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', file['file_name']).split()))}\n\n</a></b>"
            else:
                cap = f"<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 ✦</blockquote>\n\n🎬 <b>Query:</b> <code>{html_lib.escape(str(search))}</code>\n📊 <b>Total Files:</b> <code>{total_results}</code>\n👤 <b>Requested By:</b> {query.from_user.mention}\n⚡ <b>Speed:</b> <code>{remaining_seconds}s</code>\n🏠 <b>Chat:</b> {html_lib.escape(str(query.message.chat.title or 'MoviesZoneFlix'))}\n\n<i>⏳ Auto-deletes in 5 minutes</i>\n\n</b>"
                cap += "<b><u>🍿 Your Movie & Series Files 👇</u></b>\n\n"
                for file in files:
                    cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', file['file_name']).split()))}\n\n</a></b>"
    else:
        cap = f"<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 ✦</blockquote>\n\n🎬 <b>Query:</b> <code>{html_lib.escape(str(search))}</code>\n📊 <b>Total Files:</b> <code>{total_results}</code>\n👤 <b>Requested By:</b> {query.from_user.mention}\n⚡ <b>Speed:</b> <code>{remaining_seconds}s</code>\n🏠 <b>Chat:</b> {html_lib.escape(str(query.message.chat.title or 'MoviesZoneFlix'))}\n\n<i>⏳ Auto-deletes in 5 minutes</i>\n\n</b>"
        cap += "<b><u>🍿 Your Movie & Series Files 👇</u></b>\n\n"
        for file in files:
            cap += f"<b>📁 <a href='https://telegram.me/{temp.U_NAME}?start=files_{file['file_id']}'>[{get_size(file['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', file['file_name']).split()))}\n\n</a></b>"
    return cap


async def get_seconds(time_string):
    return parse_duration_to_seconds(time_string, default=0)
