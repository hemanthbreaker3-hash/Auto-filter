"""Telegram Bot API 10.x rich messages and native styled keyboards.

Pyrogram/Pyrofork 2.3.x does not serialize all Bot API 10.x fields yet, so
these helpers call the official HTTPS Bot API directly while keeping the
existing Pyrogram client and handlers intact.
"""
import json
from typing import Any, Dict, Iterable, List, Optional

import aiohttp

_VALID_STYLES = {"primary", "success", "danger"}
_VALID_RICH_TYPES = {"url", "callback_data", "web_app", "copy_text", "disabled"}


class TelegramAPIError(RuntimeError):
    """Raised when Telegram rejects a Bot API request."""


def _token(client) -> str:
    token = getattr(client, "bot_token", None)
    if not token:
        raise ValueError("This client has no bot token; rich Bot API methods require a bot client.")
    return token


async def api_request(client, method: str, payload: Dict[str, Any]) -> Any:
    """Call an official Bot API method and return its result."""
    url = f"https://api.telegram.org/bot{_token(client)}/{method}"
    timeout = aiohttp.ClientTimeout(total=30)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.post(url, json=payload) as response:
            try:
                data = await response.json(content_type=None)
            except Exception as exc:
                body = await response.text()
                raise TelegramAPIError(f"Telegram returned HTTP {response.status}: {body[:500]}") from exc
    if not data.get("ok"):
        raise TelegramAPIError(data.get("description", "Telegram Bot API request failed"))
    return data.get("result")


def make_inline_keyboard(rows: Iterable[Iterable[Dict[str, Any]]]) -> Dict[str, Any]:
    """Build Bot API inline_keyboard JSON with official native button styles.

    Each button must contain text and exactly one action field, e.g. url or
    callback_data. Optional style is primary (blue), success (green), or
    danger (red). Arbitrary HEX colours are not supported by Telegram.
    """
    keyboard: List[List[Dict[str, Any]]] = []
    for row in rows:
        out_row = []
        for source in row:
            button = dict(source)
            if not isinstance(button.get("text"), str) or not button["text"]:
                raise ValueError("Every inline button needs non-empty text")
            style = button.get("style")
            if style is not None and style not in _VALID_STYLES:
                raise ValueError("Button style must be primary, success, or danger")
            actions = [key for key in ("url", "callback_data", "web_app", "login_url",
                       "switch_inline_query", "switch_inline_query_current_chat",
                       "switch_inline_query_chosen_chat", "callback_game", "pay",
                       "copy_text") if key in button]
            if len(actions) != 1:
                raise ValueError("Each inline button must define exactly one action")
            if "callback_data" in button:
                value = button["callback_data"]
                if not isinstance(value, str) or not 1 <= len(value.encode("utf-8")) <= 64:
                    raise ValueError("callback_data must contain 1-64 UTF-8 bytes")
            out_row.append(button)
        if out_row:
            keyboard.append(out_row)
    if not keyboard:
        raise ValueError("Inline keyboard cannot be empty")
    return {"inline_keyboard": keyboard}


async def send_styled_message(client, chat_id: Any, text: str,
                              buttons: Optional[Iterable[Iterable[Dict[str, Any]]]] = None,
                              parse_mode: str = "HTML", **kwargs):
    """Send a regular message with Telegram-native coloured inline buttons."""
    payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
    payload.update(kwargs)
    if buttons is not None:
        payload["reply_markup"] = make_inline_keyboard(buttons)
    return await api_request(client, "sendMessage", payload)


async def send_rich_message(client, chat_id: Any, html: str,
                            reply_markup: Optional[Dict[str, Any]] = None, **kwargs):
    """Send a Bot API 10.1+ Rich Message using Telegram's official HTML mode.

    Rich HTML supports native formatting, structured blocks, and embedded
    <tg-button> / <tg-button-row> controls (Bot API 10.3). Embedded buttons
    should be used when the layout needs buttons inside the rich message.
    """
    if not isinstance(html, str) or not html.strip():
        raise ValueError("Rich message HTML cannot be empty")
    payload = {"chat_id": chat_id, "rich_message": {"html": html}}
    payload.update(kwargs)
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await api_request(client, "sendRichMessage", payload)


async def send_rich_markdown(client, chat_id: Any, markdown: str,
                             reply_markup: Optional[Dict[str, Any]] = None, **kwargs):
    """Send a Bot API 10.1+ Rich Message using Telegram Rich Markdown."""
    if not isinstance(markdown, str) or not markdown.strip():
        raise ValueError("Rich message Markdown cannot be empty")
    payload = {"chat_id": chat_id, "rich_message": {"markdown": markdown}}
    payload.update(kwargs)
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await api_request(client, "sendRichMessage", payload)


async def edit_rich_message(client, chat_id: Any, message_id: int, html: str,
                            reply_markup: Optional[Dict[str, Any]] = None):
    """Edit an existing message with Bot API rich HTML content."""
    payload = {"chat_id": chat_id, "message_id": message_id,
               "rich_message": {"html": html}}
    if reply_markup is not None:
        payload["reply_markup"] = reply_markup
    return await api_request(client, "editMessageText", payload)
