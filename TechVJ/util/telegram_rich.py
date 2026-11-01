"""Telegram Bot API 10.x rich messages and native styled keyboards.

Provides `ButtonStyle` (`PRIMARY`, `SUCCESS`, `DANGER`) and automatic Bot API
styled inline keyboard rendering across every Pyrogram/Pyrofork message and
callback edit in the bot (including search results, filters, admin panels,
indexing, backup/restore, clone bots, and extra plugins).
"""
from enum import Enum
import logging
import re
from typing import Any, Dict, Iterable, List, Optional, Union

import aiohttp
from pyrogram import Client, enums, types
from pyrogram.errors import MessageNotModified
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup

logger = logging.getLogger(__name__)

_VALID_STYLES = {"primary", "success", "danger"}
_VALID_RICH_TYPES = {"url", "callback_data", "web_app", "copy_text", "disabled"}


class ButtonStyle(str, Enum):
    """Telegram native coloured button styles."""
    PRIMARY = "primary"
    SUCCESS = "success"
    DANGER = "danger"
    DEFAULT = "primary"
    BLUE = "primary"
    GREEN = "success"
    RED = "danger"

    def __str__(self) -> str:
        return str(self.value)


# Expose ButtonStyle on pyrogram.enums and pyrogram.types so any import path works
if not hasattr(enums, "ButtonStyle"):
    setattr(enums, "ButtonStyle", ButtonStyle)
if not hasattr(types, "ButtonStyle"):
    setattr(types, "ButtonStyle", ButtonStyle)


class TelegramAPIError(RuntimeError):
    """Raised when Telegram rejects a Bot API request."""


def normalize_style(style: Any, text: str = "", callback_data: str = "", url: str = "") -> str:
    """Normalize any ButtonStyle / string into 'primary', 'success', or 'danger'."""
    if style is not None:
        if isinstance(style, Enum):
            val = str(style.value).strip().lower()
        else:
            val = str(style).strip().lower()
        if val in _VALID_STYLES:
            return val
        if val in ("blue", "default", "info"):
            return "primary"
        if val in ("green", "confirm", "ok"):
            return "success"
        if val in ("red", "error", "cancel", "delete", "warn"):
            return "danger"
    return infer_button_style(text=text, callback_data=callback_data, url=url)


def infer_button_style(text: str = "", callback_data: str = "", url: str = "") -> str:
    """Infer an appropriate native colour style when one is not explicitly specified."""
    t = (text or "").lower()
    cb = (callback_data or "").lower()
    combined = f"{t} {cb}"

    danger_tokens = (
        "cancel", "close", "delete", "delall", "remove", "stop", "abort",
        "disable", "disconnect", "unavailable", "unalert", "no more pages",
        "ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇ", "ᴄʟᴏsᴇ", "ᴅᴇʟᴇᴛᴇ", "ᴄᴀɴᴄᴇʟ", "✘", "❎", "✖", "🛑", "🗑", "⚠️",
        "back", "ʙᴀᴄᴋ", "𝐁𝐀𝐂𝐊", "pause",
    )
    for tok in danger_tokens:
        if tok in combined:
            return "danger"

    success_tokens = (
        "sendfiles", "send_fall", "send_fsall", "send all", "𝐒𝐞𝐧𝐝 𝐀𝐥𝐥",
        "confirm", "resume", "continue", "enable", "verify", "checksub",
        "generate_stream_link", "download", "ᴅᴏᴡɴʟᴏᴀᴅ", "watch", "ᴡᴀᴛᴄʜ",
        "stream", "sᴛʀᴇᴀᴍ", "backup", "start new", "new /index", "➕",
        "get_trail", "buy_premium", "subscription", "earn money", "ᴇᴀʀɴ ᴍᴏɴᴇʏ",
        "join", "ᴊᴏɪɴ", "unmute", "yes", "uploaded", "upalert", "already_available",
        "alalert", "get file again", "ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ", "✔", "✅", "🟢", "▶️", "💾",
        "pages", "ᴘᴀɢᴇ", "𝐏𝐀𝐆𝐄",
    )
    for tok in success_tokens:
        if tok in combined:
            return "success"

    if url:
        return "success"
    return "primary"


def _normalize_button_url(url: str) -> str:
    u = str(url or "").strip().replace(" ", "")
    if not u:
        return u
    if u.startswith(("http://", "https://", "tg://")):
        return u
    if u.startswith(("t.me/", "telegram.me/", "telegram.dog/")):
        return f"https://{u}"
    return f"https://{u}"


# Patch InlineKeyboardButton.__init__ so `style=` is always accepted and stored
_ORIG_IKB_INIT = InlineKeyboardButton.__init__
if not getattr(InlineKeyboardButton, "_tgbox_style_patched", False):
    def _patched_ikb_init(self, text: str, *args, style: Any = None, **kwargs):
        if "url" in kwargs and kwargs["url"]:
            kwargs["url"] = _normalize_button_url(kwargs["url"])
        try:
            _ORIG_IKB_INIT(self, text, *args, **kwargs)
        except TypeError:
            kwargs.pop("style", None)
            _ORIG_IKB_INIT(self, text, *args, **kwargs)
        cb_val = getattr(self, "callback_data", None) or kwargs.get("callback_data") or ""
        url_val = getattr(self, "url", None) or kwargs.get("url") or ""
        self.style = normalize_style(style, text=str(text or ""), callback_data=str(cb_val), url=str(url_val))

    InlineKeyboardButton.__init__ = _patched_ikb_init
    InlineKeyboardButton._tgbox_style_patched = True


def _token(client) -> Optional[str]:
    token = getattr(client, "bot_token", None)
    if not token:
        try:
            import info
            token = getattr(info, "BOT_TOKEN", None)
        except Exception:
            token = None
    return token


async def api_request(client, method: str, payload: Dict[str, Any]) -> Any:
    """Call an official Bot API method and return its result."""
    token = _token(client)
    if not token:
        raise ValueError("This client has no bot token; rich Bot API methods require a bot client.")
    url = f"https://api.telegram.org/bot{token}/{method}"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            try:
                data = await response.json(content_type=None)
            except Exception as exc:
                body = await response.text()
                raise TelegramAPIError(f"Telegram returned HTTP {response.status}: {body[:500]}") from exc
    if not data.get("ok"):
        desc = data.get("description", "Telegram Bot API request failed")
        if "message is not modified" in desc.lower():
            raise MessageNotModified
        raise TelegramAPIError(desc)
    return data.get("result")


def _button_to_dict(source: Union[Dict[str, Any], InlineKeyboardButton]) -> Optional[Dict[str, Any]]:
    """Convert either a dict or Pyrogram InlineKeyboardButton into a Bot API styled button dict."""
    if isinstance(source, InlineKeyboardButton):
        text = str(getattr(source, "text", "") or "").strip() or "Button"
        btn: Dict[str, Any] = {"text": text}
        if getattr(source, "url", None):
            btn["url"] = _normalize_button_url(source.url)
        elif getattr(source, "callback_data", None) is not None:
            cb = str(source.callback_data)
            if len(cb.encode("utf-8")) > 64:
                cb = cb.encode("utf-8")[:64].decode("utf-8", errors="ignore")
            btn["callback_data"] = cb or "noop"
        elif getattr(source, "web_app", None) is not None:
            wa = source.web_app
            wa_url = getattr(wa, "url", None) if not isinstance(wa, dict) else wa.get("url")
            if wa_url:
                btn["web_app"] = {"url": _normalize_button_url(wa_url)}
        elif getattr(source, "switch_inline_query", None) is not None:
            btn["switch_inline_query"] = str(source.switch_inline_query)
        elif getattr(source, "switch_inline_query_current_chat", None) is not None:
            btn["switch_inline_query_current_chat"] = str(source.switch_inline_query_current_chat)
        elif getattr(source, "copy_text", None) is not None:
            ct = source.copy_text
            ct_text = getattr(ct, "text", str(ct)) if not isinstance(ct, dict) else ct.get("text", "")
            btn["copy_text"] = {"text": str(ct_text)}
        else:
            btn["callback_data"] = "pages"

        btn["style"] = normalize_style(
            getattr(source, "style", None),
            text=text,
            callback_data=btn.get("callback_data", ""),
            url=btn.get("url", ""),
        )
        return btn

    if isinstance(source, dict):
        button = dict(source)
        text = str(button.get("text") or "").strip()
        if not text:
            return None
        button["text"] = text
        if "url" in button and button["url"]:
            button["url"] = _normalize_button_url(button["url"])
        if "web_app" in button and not isinstance(button["web_app"], dict):
            wa_url = getattr(button["web_app"], "url", None)
            if wa_url:
                button["web_app"] = {"url": _normalize_button_url(wa_url)}
        if "callback_data" in button and isinstance(button["callback_data"], str):
            cb_bytes = button["callback_data"].encode("utf-8")
            if len(cb_bytes) > 64:
                button["callback_data"] = cb_bytes[:64].decode("utf-8", errors="ignore")
        button["style"] = normalize_style(
            button.get("style"),
            text=text,
            callback_data=str(button.get("callback_data", "")),
            url=str(button.get("url", "")),
        )
        return button
    return None


def make_inline_keyboard(rows: Union[InlineKeyboardMarkup, Dict[str, Any], Iterable[Iterable[Any]]]) -> Dict[str, Any]:
    """Build Bot API inline_keyboard JSON with official native button styles."""
    if isinstance(rows, dict) and "inline_keyboard" in rows:
        raw_rows = rows["inline_keyboard"]
    elif isinstance(rows, InlineKeyboardMarkup):
        raw_rows = rows.inline_keyboard
    else:
        raw_rows = rows

    keyboard: List[List[Dict[str, Any]]] = []
    for row in raw_rows or []:
        if isinstance(row, (InlineKeyboardButton, dict)):
            row = [row]
        out_row = []
        for source in row:
            button = _button_to_dict(source)
            if not button:
                continue
            actions = [key for key in (
                "url", "callback_data", "web_app", "login_url",
                "switch_inline_query", "switch_inline_query_current_chat",
                "switch_inline_query_chosen_chat", "callback_game", "pay",
                "copy_text"
            ) if key in button]
            if len(actions) != 1:
                continue
            out_row.append(button)
        if out_row:
            keyboard.append(out_row)
    return {"inline_keyboard": keyboard}


async def apply_styled_markup(client, chat_id: Any, message_id: int, reply_markup: Any) -> bool:
    """Apply native Bot API button styles to an existing message's inline keyboard."""
    if reply_markup is None:
        try:
            await api_request(client, "editMessageReplyMarkup", {
                "chat_id": chat_id,
                "message_id": message_id,
                "reply_markup": {"inline_keyboard": []},
            })
            return True
        except MessageNotModified:
            return True
        except Exception:
            return False

    if not isinstance(reply_markup, (InlineKeyboardMarkup, dict, list, tuple)):
        return False
    kb = make_inline_keyboard(reply_markup)
    if not kb.get("inline_keyboard"):
        return False
    try:
        await api_request(client, "editMessageReplyMarkup", {
            "chat_id": chat_id,
            "message_id": message_id,
            "reply_markup": kb,
        })
        return True
    except MessageNotModified:
        return True
    except Exception as exc:
        logger.debug("Could not apply styled markup via Bot API: %s", exc)
        return False


def install_global_styled_buttons():
    """Patch Pyrogram Client methods so every InlineKeyboardMarkup in the bot renders with ButtonStyle colours."""
    if getattr(Client, "_tgbox_global_styled_patched", False):
        return

    orig_send_message = Client.send_message
    orig_send_photo = Client.send_photo
    orig_send_cached_media = Client.send_cached_media
    orig_copy_message = Client.copy_message
    orig_send_document = Client.send_document
    orig_send_video = Client.send_video
    orig_send_audio = Client.send_audio
    orig_edit_message_text = Client.edit_message_text
    orig_edit_message_caption = Client.edit_message_caption
    orig_edit_message_reply_markup = Client.edit_message_reply_markup

    async def _SendMessage(self, chat_id, text, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_message(self, chat_id, text, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _SendPhoto(self, chat_id, photo, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_photo(self, chat_id, photo, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _SendCachedMedia(self, chat_id, file_id, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_cached_media(self, chat_id, file_id, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _CopyMessage(self, chat_id, from_chat_id, message_id, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_copy_message(self, chat_id, from_chat_id, message_id, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _SendDocument(self, chat_id, document, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_document(self, chat_id, document, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _SendVideo(self, chat_id, video, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_video(self, chat_id, video, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _SendAudio(self, chat_id, audio, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_send_audio(self, chat_id, audio, *args, **kwargs)
        if msg and isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            await apply_styled_markup(self, msg.chat.id, msg.id, reply_markup)
        return msg

    async def _EditMessageText(self, chat_id, message_id, text, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_edit_message_text(self, chat_id, message_id, text, *args, **kwargs)
        if isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            target_chat = msg.chat.id if getattr(msg, "chat", None) else chat_id
            target_id = getattr(msg, "id", None) or message_id
            await apply_styled_markup(self, target_chat, target_id, reply_markup)
        return msg

    async def _EditMessageCaption(self, chat_id, message_id, *args, **kwargs):
        reply_markup = kwargs.get("reply_markup")
        msg = await orig_edit_message_caption(self, chat_id, message_id, *args, **kwargs)
        if isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            target_chat = msg.chat.id if getattr(msg, "chat", None) else chat_id
            target_id = getattr(msg, "id", None) or message_id
            await apply_styled_markup(self, target_chat, target_id, reply_markup)
        return msg

    async def _EditMessageReplyMarkup(self, chat_id, message_id, reply_markup=None, *args, **kwargs):
        if isinstance(reply_markup, (InlineKeyboardMarkup, dict)):
            kb = make_inline_keyboard(reply_markup)
            if kb.get("inline_keyboard"):
                try:
                    await api_request(self, "editMessageReplyMarkup", {
                        "chat_id": chat_id,
                        "message_id": message_id,
                        "reply_markup": kb,
                    })
                    return True
                except MessageNotModified:
                    raise
                except Exception:
                    pass
        return await orig_edit_message_reply_markup(self, chat_id, message_id, reply_markup=reply_markup, *args, **kwargs)

    Client.send_message = _SendMessage
    Client.send_photo = _SendPhoto
    Client.send_cached_media = _SendCachedMedia
    Client.copy_message = _CopyMessage
    Client.send_document = _SendDocument
    Client.send_video = _SendVideo
    Client.send_audio = _SendAudio
    Client.edit_message_text = _EditMessageText
    Client.edit_message_caption = _EditMessageCaption
    Client.edit_message_reply_markup = _EditMessageReplyMarkup
    Client._tgbox_global_styled_patched = True


install_global_styled_buttons()


async def send_styled_message(client, chat_id: Any, text: str,
                              buttons: Optional[Iterable[Iterable[Any]]] = None,
                              parse_mode: str = "HTML", **kwargs):
    """Send a regular message with Telegram-native coloured inline buttons."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    payload.update(kwargs)
    if buttons is not None:
        payload["reply_markup"] = make_inline_keyboard(buttons)
    return await api_request(client, "sendMessage", payload)


async def send_rich_message(client, chat_id: Any, html: str,
                            reply_markup: Optional[Dict[str, Any]] = None, **kwargs):
    """Send a Bot API 10.1+ Rich Message using Telegram's official HTML mode."""
    if not isinstance(html, str) or not html.strip():
        raise ValueError("Rich message HTML cannot be empty")
    payload = {"chat_id": chat_id, "rich_message": {"html": html}}
    payload.update(kwargs)
    if reply_markup is not None:
        payload["reply_markup"] = make_inline_keyboard(reply_markup) if not isinstance(reply_markup, dict) or "inline_keyboard" not in reply_markup else make_inline_keyboard(reply_markup["inline_keyboard"])
    return await api_request(client, "sendRichMessage", payload)


async def send_rich_markdown(client, chat_id: Any, markdown: str,
                             reply_markup: Optional[Dict[str, Any]] = None, **kwargs):
    """Send a Bot API 10.1+ Rich Message using Telegram Rich Markdown."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("Rich message Markdown cannot be empty")
    payload = {"chat_id": chat_id, "rich_message": {"markdown": markdown}}
    payload.update(kwargs)
    if reply_markup is not None:
        payload["reply_markup"] = make_inline_keyboard(reply_markup)
    return await api_request(client, "sendRichMessage", payload)


async def edit_rich_message(client, chat_id: Any, message_id: int, html: str,
                            reply_markup: Optional[Dict[str, Any]] = None):
    """Edit an existing message with Bot API rich HTML content."""
    payload = {"chat_id": chat_id, "message_id": message_id,
               "rich_message": {"html": html}}
    if reply_markup is not None:
        payload["reply_markup"] = make_inline_keyboard(reply_markup)
    return await api_request(client, "editMessageText", payload)
