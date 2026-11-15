# MoviesZoneFlix — Telegram Rich Messages & Native Button Styles

This project now includes a compatibility layer for Telegram Bot API 10.1–10.3.
The existing Pyrofork handlers and callback system remain unchanged. The new
helpers call Telegram's official HTTPS Bot API directly because the pinned
Pyrofork 2.3.45 model layer may not serialize all Bot API 10.x fields.

## Rich HTML message

```python
await TechVJBot.send_rich_message(
    chat_id,
    "<h2>Welcome to MoviesZoneFlix</h2>"
    "<p><b>Bold</b>, <i>italic</i>, <u>underline</u>, "
    "<s>strike</s>, <tg-spoiler>spoiler</tg-spoiler></p>"
    "<blockquote>Native Telegram quote</blockquote>"
    "<pre language="python">print('MoviesZoneFlix')</pre>"
    "<tg-button-row align="center">"
    "<tg-button type="url" style="success" url="https://t.me/">Open Telegram</tg-button>"
    "</tg-button-row>"
)
```

## Coloured inline keyboard on a regular message

```python
await TechVJBot.send_styled_message(
    chat_id,
    "<b>Choose an action</b>",
    buttons=[
        [{"text": "Continue", "callback_data": "continue", "style": "primary"}],
        [{"text": "Confirm", "callback_data": "confirm", "style": "success"},
         {"text": "Cancel", "callback_data": "cancel", "style": "danger"}],
    ],
)
```

Available native button styles are `primary` (blue), `success` (green), and
`danger` (red). Telegram does not expose arbitrary HEX/RGB colours. Use colours
sparingly to preserve action hierarchy. Existing callback handlers still
receive the same callback data.

## Other helpers

- `send_rich_markdown(client, chat_id, markdown, ...)`
- `send_rich_message(client, chat_id, html, ...)`
- `edit_rich_message(client, chat_id, message_id, html, ...)`
- `make_inline_keyboard(rows)` for validated Bot API keyboard JSON

For clone clients, import the helper from `TechVJ.util.telegram_rich` and pass
the relevant Pyrogram client instance. Every client must be a bot client with
its own bot token. The helper raises `TelegramAPIError` with Telegram's error
message if a request is rejected; it does not silently fall back or report a
false success.

Rich Messages require a Telegram client version that supports the relevant
feature. Older Telegram clients may display a simplified rendering or omit
newer controls. Rich messages are a separate Bot API method; this integration
keeps legacy send_message/edit_message_text flows intact unless the new helper
is explicitly used.
