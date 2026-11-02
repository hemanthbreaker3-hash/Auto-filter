# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import logging
from pyrogram import Client, emoji, filters, enums
from pyrogram.errors.exceptions.bad_request_400 import QueryIdInvalid
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultCachedDocument, InlineQuery
from TechVJ.util.telegram_rich import ButtonStyle
from database.ia_filterdb import get_search_results
from utils import has_force_subscribe, is_subscribed, get_size, temp, format_file_caption
from info import CACHE_TIME, AUTH_USERS, AUTH_CHANNEL, CUSTOM_FILE_CAPTION, CHNL_LNK
from database.connections_mdb import active_connection

logger = logging.getLogger(__name__)
# Re-check FSub on every inline query; panel-managed channels can change at runtime.
cache_time = 0

async def inline_users(query: InlineQuery):
    if AUTH_USERS:
        if query.from_user and query.from_user.id in AUTH_USERS:
            return True
        else:
            return False
    if query.from_user and query.from_user.id not in temp.BANNED_USERS:
        return True
    return False

@Client.on_inline_query()
async def answer(bot, query):
    """Show search results for given inline query"""
    chat_id = await active_connection(str(query.from_user.id))
    
    if not await inline_users(query):
        await query.answer(
            results=[],
            cache_time=0,
            switch_pm_text='okDa',
            switch_pm_parameter="hehe"
        )
        return

    if await has_force_subscribe() and not await is_subscribed(bot, query):
        await query.answer(
            results=[],
            cache_time=0,
            switch_pm_text='You have to subscribe my channel to use the bot',
            switch_pm_parameter="subscribe"
        )
        return

    results = []
    if '|' in query.query:
        string, file_type = query.query.split('|', maxsplit=1)
        string = string.strip()
        file_type = file_type.strip().lower()
    else:
        string = query.query.strip()
        file_type = None

    offset = int(query.offset or 0)
    reply_markup = get_reply_markup(query=string)
    files, next_offset, total = await get_search_results(chat_id, string, file_type=file_type, max_results=10, offset=offset)

    for file in files:
        f_caption = format_file_caption(file.get('caption'), file.get('file_name'), CHNL_LNK)
        results.append(
            InlineQueryResultCachedDocument(
                title=file['file_name'],
                document_file_id=file['file_id'],
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML,
                description=f'Size: {get_size(file["file_size"])}',
                reply_markup=reply_markup
            )
        )

    if results:
        switch_pm_text = f"{emoji.FILE_FOLDER} Results - {total}"
        if string:
            switch_pm_text += f" for {string}"
        try:
            await query.answer(
                results=results,
                is_personal = True,
                cache_time=cache_time,
                switch_pm_text=switch_pm_text,
                switch_pm_parameter="start",
                next_offset=str(next_offset)
            )
        except QueryIdInvalid:
            pass
        except Exception as e:
            logging.exception(str(e))
    else:
        switch_pm_text = f'{emoji.CROSS_MARK} No results'
        if string:
            switch_pm_text += f' for "{string}"'

        await query.answer(
            results=[],
            is_personal = True,
            cache_time=cache_time,
            switch_pm_text=switch_pm_text,
            switch_pm_parameter="okay"
        )


def get_reply_markup(query):
    buttons = [[
        InlineKeyboardButton('Search again', switch_inline_query_current_chat=query, style=ButtonStyle.PRIMARY)
    ]]
    return InlineKeyboardMarkup(buttons)
