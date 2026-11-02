# Don't Remove Credit @MoviesZoneFlix
# Official Update Channel: https://t.me/+Kmi6jBTE_MY4N2Q9
# Contact: https://t.me/alonekingstarbackagain

"""
Auto-registers every bot command with Telegram as soon as MoviesZoneFlix
finishes starting up.
"""

import logging

from pyrogram import Client
from pyrogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault

from info import ADMINS

logger = logging.getLogger(__name__)

# Commands every user can see and use.
PUBLIC_COMMANDS = {
    "start": "Start MoviesZoneFlix / show the welcome screen",
    "help": "Show all available features",
    "about": "About MoviesZoneFlix",
    "alive": "Check if MoviesZoneFlix is online",
    "ping": "Check the bot's response time",
    "imdb": "Search IMDb for a movie or series",
    "search": "Search for a movie or series file",
    "myplan": "Check your premium plan & verification status",
    "mycredits": "Check your remaining verification credits & time",
    "plan": "View available premium plans",
    "settings": "Configure bot settings for this chat",
    "request": "Request a movie or series",
    "song": "Download a song",
    "video": "Download a video",
    "mp3": "Download audio as MP3",
    "mp4": "Download video as MP4",
    "lyrics": "Get song lyrics",
    "tts": "Convert text to speech",
    "font": "Convert text into stylish fonts",
    "id": "Get the Telegram ID of a user or chat",
    "info": "Get info about a user",
}

# Extra commands shown only to the chats listed in ADMINS, on top of
# everything in PUBLIC_COMMANDS.
ADMIN_COMMANDS = {
    "auto": "Configure Series & Movie 3-quality auto-posting channel",
    "shortmode": "Select Shortener Mode (Time Expiry / Credits) & manage shorteners",
    "mode": "Quick alias for Shortener Mode Selection",
    "panel": "Open the interactive MoviesZoneFlix admin dashboard",
    "save": "Open MoviesZoneFlix backup and ZIP import center",
    "index": "Index files from a channel link or range",
    "indexstatus": "View and manage running index tasks",
    "cancelindex": "Cancel running index tasks",
    "broadcast": "Broadcast a message to all users",
    "grp_broadcast": "Broadcast a message to all groups",
    "ban": "Ban a user from using the bot",
    "unban": "Unban a user",
    "users": "Show total users",
    "chats": "Show total chats",
    "channel": "View configured auto-index channels",
    "logs": "Get the bot's log file",
    "delete": "Delete a file from the database",
    "deleteall": "Delete all files from the database",
    "deletefiles": "Delete files matching a query",
    "delg": "Delete a global filter",
    "delallg": "Delete all global filters",
    "addg": "Add a global filter",
    "restart": "Restart the bot",
    "stats": "Show database and storage stats",
    "add": "Manage filters or run /add save and /add load backups",
    "clone": "Create a clone of this bot",
    "deleteclone": "Delete your clone bot",
    "set_template": "Set a custom IMDb template",
    "set_caption": "Set a custom file caption",
    "set_thumb": "Set a custom thumbnail",
    "del_caption": "Remove the custom caption",
    "del_thumb": "Remove the custom thumbnail",
    "see_caption": "View the current custom caption",
    "view_thumb": "View the current custom thumbnail",
    "send": "Send a message to a specific user",
    "gfilter": "Add a global filter",
    "gfilters": "List global filters",
    "viewgfilters": "View all global filters",
    "purgerequests": "Purge pending movie requests",
    "totalrequests": "Show total pending requests",
    "invite": "Get the bot's group invite link",
    "leave": "Make the bot leave a chat",
    "setskip": "Set the file-indexing skip number",
    "disable": "Disable a chat or command",
    "enable": "Re-enable a chat or command",
    "del": "Remove a filter in this chat",
    "delall": "Remove all filters in this chat",
    "batch": "Generate a batch file link",
    "pbatch": "Generate a private batch link",
    "filter": "Add a filter in this chat",
    "filters": "List filters in this chat",
    "viewfilters": "View all filters",
    "connect": "Connect this chat for remote filter management",
    "connections": "View connected chats",
    "disconnect": "Disconnect a connected chat",
    "fsub": "Enable force-subscribe",
    "nofsub": "Disable force-subscribe",
    "shortlink": "Set a link shortener or mode for this chat",
    "shortlink_info": "View the current shortener settings",
    "setshortlinkon": "Enable the shortener",
    "setshortlinkoff": "Disable the shortener",
    "set_tutorial": "Set the shortener tutorial link",
    "remove_tutorial": "Remove the shortener tutorial link",
    "genpw": "Generate a random password",
    "genpassword": "Generate a random password",
    "add_premium": "Grant a user premium access",
    "remove_premium": "Revoke a user's premium access",
    "json": "Get the raw JSON of a replied message",
    "paste": "Paste text to a paste service",
    "pasty": "Paste text to a paste service",
    "tgpaste": "Paste text to Telegraph",
    "telegraph": "Upload content to Telegraph",
    "share": "Get a shareable text link",
    "share_text": "Get a shareable text link",
    "sharetext": "Get a shareable text link",
    "link": "Generate a file share link",
    "plink": "Generate a private file share link",
    "stream": "Get a streaming link for a file",
    "rename": "Rename a file",
    "stickerid": "Get the file ID of a sticker",
    "runs": "Check the bot's uptime",
    "openai": "Ask the built-in AI a question",
    "repo": "Get the bot's official channel link",
}


def _as_bot_commands(mapping: dict) -> list:
    return [BotCommand(cmd, desc) for cmd, desc in mapping.items()]


async def register_all_commands(bot: Client) -> None:
    public_commands = _as_bot_commands(PUBLIC_COMMANDS)
    admin_commands = _as_bot_commands({**PUBLIC_COMMANDS, **ADMIN_COMMANDS})

    try:
        await bot.set_bot_commands(public_commands, scope=BotCommandScopeDefault())
        logger.info(f"Registered {len(public_commands)} public commands.")
    except Exception as e:
        logger.error(f"Failed to register public commands: {e}")

    for admin_id in ADMINS:
        if not isinstance(admin_id, int):
            continue
        try:
            await bot.set_bot_commands(admin_commands, scope=BotCommandScopeChat(chat_id=admin_id))
        except Exception as e:
            logger.error(f"Failed to register admin commands for {admin_id}: {e}")

    logger.info("MoviesZoneFlix command registration complete.")
