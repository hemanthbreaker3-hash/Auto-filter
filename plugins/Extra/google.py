import asyncio
import logging

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

LOGGER = logging.getLogger(__name__)


def _google_results(query: str):
    """Run the optional googlesearch-python dependency outside the event loop."""
    from googlesearch import search
    try:
        return list(search(query, num_results=5, sleep_interval=1, unique=True))
    except TypeError:
        # Compatibility with older googlesearch-python releases.
        return list(search(query, num=5, stop=5, pause=1))


async def _search_reply(message: Message, query: str, site: str = ""):
    status = await message.reply_text("Searching...")
    try:
        search_query = f"site:stackoverflow.com {query}" if site else query
        links = await asyncio.to_thread(_google_results, search_query)
        links = [url for url in links if isinstance(url, str) and url.startswith(("https://", "http://"))]
        if not links:
            await status.edit_text("No results found for your query.")
            return
        rows = []
        for index, url in enumerate(links[:5], 1):
            label = f"Result {index}"
            rows.append([InlineKeyboardButton(label, url=url)])
        await status.edit_text(
            f"Search results for: {query[:300]}",
            reply_markup=InlineKeyboardMarkup(rows),
            disable_web_page_preview=True,
        )
    except Exception as exc:
        LOGGER.exception("Search failed")
        await status.edit_text(f"Search is temporarily unavailable: {str(exc)[:250]}")


@Client.on_message(filters.command("google"))
async def google_search(client: Client, message: Message):
    parts = (message.text or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Please provide a search query. Example: /google Python")
    await _search_reply(message, parts[1])


@Client.on_message(filters.command("stack"))
async def stack_search(client: Client, message: Message):
    parts = (message.text or "").split(None, 1)
    if len(parts) < 2:
        return await message.reply_text("Please provide a query. Example: /stack Pyrogram handlers")
    await _search_reply(message, parts[1], site="stackoverflow.com")
