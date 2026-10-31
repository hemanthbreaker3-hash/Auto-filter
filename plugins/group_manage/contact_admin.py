"""Private user-to-admin support forwarding and admin reply handlers.

SUPPORT_CHAT_ID is optional. When it is unset, the bot still loads normally;
only the !ans reply handler is disabled.
"""
import logging
from html import escape

from pyrogram import Client, filters
from pyrogram.types import Message

from info import ADMINS, LOG_CHANNEL, SUPPORT_CHAT_ID

LOGGER = logging.getLogger(__name__)


@Client.on_message(filters.private & filters.command("admin"))
async def forward_message_to_group(client: Client, message: Message):
    """Forward a user's /admin message to the configured log channel."""
    if not LOG_CHANNEL:
        return await message.reply_text(
            "Support forwarding is not configured. Please contact the bot owner."
        )

    parts = (message.text or "").split(None, 1)
    if len(parts) < 2 or not parts[1].strip():
        return await message.reply_text("Please include your message. Example: /admin I need help")
    if not message.from_user:
        return await message.reply_text("I could not identify your Telegram account.")

    user_id = message.from_user.id
    name = message.from_user.mention
    try:
        await message.forward(LOG_CHANNEL)
        await client.send_message(
            LOG_CHANNEL,
            f"A new support message from {name}\n\nUser ID: <code>{user_id}</code>\n"
            f"Reply with: <code>!ans {user_id} your_message</code>",
        )
        await message.reply_text("Your message has been forwarded to the admins. Please wait for a reply.")
    except Exception:
        LOGGER.exception("Could not forward support message from user %s", user_id)
        await message.reply_text("Sorry, I could not forward your message right now. Please try again later.")


async def reply_to_forwarded_message(client: Client, message: Message):
    """Send an admin's !ans reply to the specified user."""
    parts = (message.text or "").split(None, 2)
    if len(parts) < 3:
        return await message.reply_text("Usage: !ans USER_ID your reply")
    try:
        user_id = int(parts[1])
        reply_text = parts[2].strip()
        if user_id <= 0 or not reply_text:
            raise ValueError("A valid user ID and reply text are required.")
        await client.send_message(user_id, "Reply from the bot admins:")
        await client.send_message(user_id, escape(reply_text))
        await message.reply_text(
            f"Message sent successfully to <a href=\"tg://user?id={user_id}\">user</a>."
        )
    except ValueError as exc:
        await message.reply_text(f"Invalid command: {escape(str(exc))}")
    except Exception:
        LOGGER.exception("Could not send admin reply")
        await message.reply_text("Could not deliver the reply. Check that the user has started the bot.")


# Register this handler only when a valid support chat is configured. This
# avoids int(None) during import and keeps optional support features optional.
if SUPPORT_CHAT_ID is not None and ADMINS:
    Client.on_message(
        filters.command("ans", "!")
        & filters.user(ADMINS)
        & filters.chat(SUPPORT_CHAT_ID)
    )(reply_to_forwarded_message)
else:
    LOGGER.warning(
        "Admin reply handler is disabled: set SUPPORT_CHAT_ID and ADMINS to enable it."
    )
