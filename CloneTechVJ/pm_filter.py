# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

# Clone Code Credit : YT - @MoviesZoneFlix / TG - @MoviesZoneFlix / GitHub - @MoviesZoneFlix

import os, logging, string, asyncio, time, re, ast, random, math, pytz, pyrogram
from datetime import datetime, timedelta, date, time
from Script import script
from info import *
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, InputMediaPhoto, ChatPermissions, WebAppInfo
from pyrogram import Client, filters, enums
from TechVJ.util.telegram_rich import ButtonStyle
from pyrogram.errors import FloodWait, UserIsBlocked, MessageNotModified, PeerIdInvalid
from pyrogram.errors.exceptions.bad_request_400 import MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty
from utils import get_size, is_subscribed, pub_is_subscribed, get_poster, search_gagala, temp, get_settings, save_group_settings, get_shortlink, get_tutorial, send_all, get_cap
from database.users_chats_db import db
from database.ia_filterdb import get_file_details, get_search_results, get_bad_files

logger = logging.getLogger(__name__)
logger.setLevel(logging.ERROR)
lock = asyncio.Lock()

BUTTON = {}
BUTTONS = {}
FRESH = {}
BUTTONS0 = {}
BUTTONS1 = {}
BUTTONS2 = {}
SPELL_CHECK = {}

@Client.on_message(filters.group & filters.text & filters.incoming)
async def give_filter(client, message):
    ai_search = True
    reply_msg = await message.reply_text(f"<b>🔍 <i>MoviesZoneFlix searching for</i> <code>{message.text}</code>...</b>")
    await auto_filter(client, message.text, message, reply_msg, ai_search)
            
@Client.on_message(filters.private & filters.text & filters.incoming)
async def pm_text(bot, message):
    content = message.text
    user = message.from_user.first_name
    user_id = message.from_user.id
    if content.startswith("/") or content.startswith("#"): return  # ignore commands and hashtags
    ai_search = True
    reply_msg = await bot.send_message(message.from_user.id, f"<b>🔍 <i>MoviesZoneFlix searching for</i> <code>{content}</code>...</b>", reply_to_message_id=message.id)
    await auto_filter(bot, content, message, reply_msg, ai_search)
    
@Client.on_callback_query(filters.regex(r"^next"))
async def next_page(bot, query):
    ident, req, key, offset = query.data.split("_")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if int(req) not in [query.from_user.id, 0]:
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    try:
        offset = int(offset)
    except:
        offset = 0
    search = FRESH.get(key)
  #  if not search:
     #   await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
    #    return

    files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=offset, filter=True)
    try:
        n_offset = int(n_offset)
    except:
        n_offset = 0

    if not files:
        return
    temp.GETALL[key] = files
    temp.SHORT[query.from_user.id] = query.message.chat.id
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ]

    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    if 0 < offset <= int(MAX_B_TN):
        off_set = 0
    elif offset == 0:
        off_set = None
    else:
        off_set = offset - int(MAX_B_TN)
    if n_offset == 0:
        btn.append(
            [InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}", style=ButtonStyle.DANGER), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages", style=ButtonStyle.DANGER)]
        )
    elif off_set is None:
        btn.append([InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}", style=ButtonStyle.DANGER)])
    else:
        btn.append(
            [
                InlineKeyboardButton("⌫ 𝐁𝐀𝐂𝐊", callback_data=f"next_{req}_{key}_{off_set}", style=ButtonStyle.DANGER),
                InlineKeyboardButton(f"{math.ceil(int(offset)/int(MAX_B_TN))+1} / {math.ceil(total/int(MAX_B_TN))}", callback_data="pages", style=ButtonStyle.DANGER),
                InlineKeyboardButton("𝐍𝐄𝐗𝐓 ➪", callback_data=f"next_{req}_{key}_{n_offset}", style=ButtonStyle.DANGER)
            ],
        )
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    await query.answer()

@Client.on_callback_query(filters.regex(r"^spol"))
async def advantage_spoll_choker(bot, query):
    _, user, movie_ = query.data.split('#')
    movies = SPELL_CHECK.get(query.message.reply_to_message.id)
    if not movies:
        return await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if int(user) != 0 and query.from_user.id != int(user):
        return await query.answer(script.ALRT_TXT.format(query.from_user.first_name), show_alert=True)
    if movie_ == "close_spellcheck":
        return await query.message.delete()
    movie = movies[(int(movie_))]
    movie = re.sub(r"[:\-]", " ", movie)
    movie = re.sub(r"\s+", " ", movie).strip()
    await query.answer(script.TOP_ALRT_MSG)
    files, offset, total_results = await get_search_results(query.message.chat.id, movie, offset=0, filter=True)
    if files:
        k = (movie, files, offset, total_results)
        ai_search = True
        reply_msg = await query.message.edit_text(f"<b>🔍 <i>MoviesZoneFlix searching for</i> <code>{movie}</code>...</b>")
        await auto_filter(bot, movie, query, reply_msg, ai_search, k)
    else:
        reqstr1 = query.from_user.id if query.from_user else 0
        reqstr = await bot.get_users(reqstr1)
        k = await query.message.edit(script.MVE_NT_FND)
        await asyncio.sleep(10)
        await k.delete()

# Year 
@Client.on_callback_query(filters.regex(r"^years#"))
async def years_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    btn = []
    for i in range(0, len(YEARS)-1, 4):
        row = []
        for j in range(4):
            if i+j < len(YEARS):
                row.append(
                    InlineKeyboardButton(
                        text=YEARS[i+j].title(),
                        callback_data=f"fy#{YEARS[i+j].lower()}#{key}", style=ButtonStyle.DANGER)
                )
        btn.append(row)

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="sᴇʟᴇᴄᴛ ʏᴏᴜʀ ʏᴇᴀʀ", callback_data="ident", style=ButtonStyle.DANGER)
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭", callback_data=f"fy#homepage#{key}", style=ButtonStyle.DANGER)])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fy#"))
async def filter_yearss_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ]
    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    if offset != "":
        btn.append(
            [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages", style=ButtonStyle.DANGER)]
        )
    
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    await query.answer()  

# Episode

@Client.on_callback_query(filters.regex(r"^episodes#"))
async def episodes_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    btn = []
    for i in range(0, len(EPISODES)-1, 4):
        row = []
        for j in range(4):
            if i+j < len(EPISODES):
                row.append(
                    InlineKeyboardButton(
                        text=EPISODES[i+j].title(),
                        callback_data=f"fe#{EPISODES[i+j].lower()}#{key}", style=ButtonStyle.DANGER)
                )
        btn.append(row)

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="sᴇʟᴇᴄᴛ ʏᴏᴜʀ ᴇᴘɪsᴏᴅᴇ", callback_data="ident", style=ButtonStyle.DANGER)
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭", callback_data=f"fe#homepage#{key}", style=ButtonStyle.DANGER)])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fe#"))
async def filter_episodes_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ]
    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    if offset != "":
        btn.append(
            [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages", style=ButtonStyle.DANGER)]
        )
    
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    await query.answer()
    


#languages

@Client.on_callback_query(filters.regex(r"^languages#"))
async def languages_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    btn = []
    for i in range(0, len(LANGUAGES)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=LANGUAGES[i].title(),
                callback_data=f"fl#{LANGUAGES[i].lower()}#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(
                text=LANGUAGES[i+1].title(),
                callback_data=f"fl#{LANGUAGES[i+1].lower()}#{key}", style=ButtonStyle.DANGER),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="👇 𝖲𝖾𝗅𝖾𝖼𝗍 𝖸𝗈𝗎𝗋 𝖫𝖺𝗇𝗀𝗎𝖺𝗀𝖾𝗌 👇", callback_data="ident", style=ButtonStyle.DANGER)
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ​↭", callback_data=f"fl#homepage#{key}", style=ButtonStyle.DANGER)])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fl#"))
async def filter_languages_cb_handler(client: Client, query: CallbackQuery):
    _, lang, key = query.data.split("#")
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    baal = lang in search
    if baal:
        search = search.replace(lang, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    if lang != "homepage":
        search = f"{search} {lang}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ]
    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    if offset != "":
        btn.append(
            [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages", style=ButtonStyle.DANGER)]
        )
    
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    await query.answer()    
    
@Client.on_callback_query(filters.regex(r"^seasons#"))
async def seasons_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except:
        pass
    
    _, key = query.data.split("#")
    search = FRESH.get(key)
    BUTTONS[key] = None
    search = (search or '').replace('_', ' ')
    btn = []
    for i in range(0, len(SEASONS)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=SEASONS[i].title(),
                callback_data=f"fs#{SEASONS[i].lower()}#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(
                text=SEASONS[i+1].title(),
                callback_data=f"fs#{SEASONS[i+1].lower()}#{key}", style=ButtonStyle.DANGER),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="👇 𝖲𝖾𝗅𝖾𝖼𝗍 Season 👇", callback_data="ident", style=ButtonStyle.DANGER)
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ​↭", callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))


@Client.on_callback_query(filters.regex(r"^fs#"))
async def filter_seasons_cb_handler(client: Client, query: CallbackQuery):
    _, seas, key = query.data.split("#")
    search = (FRESH.get(key) or '').replace('_', ' ')
    search = re.sub(r"(?i)\b(?:season\s*\d{1,2}|s\d{1,3})\b", "", search).strip()
    search = re.sub(r"\s+", " ", search).strip()
    req = query.from_user.id
    chat_id = query.message.chat.id
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ {query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=True,
            )
    except Exception:
        pass
    if seas != "homepage":
        search = f"{search} {seas}".strip()
    BUTTONS0[key] = search
    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=True)
        return
    temp.GETALL[key] = files
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}",
                callback_data=f"file#{filevj['file_id']}",
                style=ButtonStyle.DANGER,
            ),
        ]
        for filevj in files
    ]
    btn.insert(0, [
        InlineKeyboardButton('ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("sᴇᴀsᴏɴs", callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
    ])
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭", callback_data=f"next_{req}_{key}_0", style=ButtonStyle.DANGER)])
    try:
        await query.edit_message_reply_markup(reply_markup=InlineKeyboardMarkup(btn))
    except MessageNotModified:
        pass
    await query.answer()

@Client.on_callback_query(filters.regex(r"^qualities#"))
async def qualities_cb_handler(client: Client, query: CallbackQuery):

    try:
        if int(query.from_user.id) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=False,
            )
    except:
        pass
    _, key = query.data.split("#")
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    btn = []
    for i in range(0, len(QUALITIES)-1, 2):
        btn.append([
            InlineKeyboardButton(
                text=QUALITIES[i].title(),
                callback_data=f"fq#{QUALITIES[i].lower()}#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton(
                text=QUALITIES[i+1].title(),
                callback_data=f"fq#{QUALITIES[i+1].lower()}#{key}", style=ButtonStyle.DANGER),
        ])

    btn.insert(
        0,
        [
            InlineKeyboardButton(
                text="⇊ ꜱᴇʟᴇᴄᴛ ʏᴏᴜʀ ǫᴜᴀʟɪᴛʏ ⇊", callback_data="ident", style=ButtonStyle.DANGER)
        ],
    )
    req = query.from_user.id
    offset = 0
    btn.append([InlineKeyboardButton(text="↭ ʙᴀᴄᴋ ᴛᴏ ꜰɪʟᴇs ↭", callback_data=f"fq#homepage#{key}", style=ButtonStyle.DANGER)])

    await query.edit_message_reply_markup(InlineKeyboardMarkup(btn))
    

@Client.on_callback_query(filters.regex(r"^fq#"))
async def filter_qualities_cb_handler(client: Client, query: CallbackQuery):
    _, qual, key = query.data.split("#")
    search = FRESH.get(key)
    search = (search or '').replace('_', ' ')
    baal = qual in search
    if baal:
        search = search.replace(qual, "")
    else:
        search = search
    req = query.from_user.id
    chat_id = query.message.chat.id
    message = query.message
    try:
        if int(req) not in [query.message.reply_to_message.from_user.id, 0]:
            return await query.answer(
                f"⚠️ ʜᴇʟʟᴏ{query.from_user.first_name},\nᴛʜɪꜱ ɪꜱ ɴᴏᴛ ʏᴏᴜʀ ᴍᴏᴠɪᴇ ʀᴇQᴜᴇꜱᴛ,\nʀᴇQᴜᴇꜱᴛ ʏᴏᴜʀ'ꜱ...",
                show_alert=False,
            )
    except:
        pass
    searchagain = search
    if qual != "homepage":
        search = f"{search} {qual}" 
    BUTTONS[key] = search

    files, offset, total_results = await get_search_results(chat_id, search, offset=0, filter=True)
    if not files:
        await query.answer("🚫 𝗡𝗼 𝗙𝗶𝗹𝗲 𝗪𝗲𝗿𝗲 𝗙𝗼𝘂𝗻𝗱 🚫", show_alert=1)
        return
    temp.GETALL[key] = files
    btn = [
        [
            InlineKeyboardButton(
                text=f"⚜️[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ] 
    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])

    if offset != "":
        btn.append(
            [InlineKeyboardButton("ᴘᴀɢᴇ", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text="ɴᴇxᴛ ⇛",callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="😶 ɴᴏ ᴍᴏʀᴇ ᴘᴀɢᴇꜱ ᴀᴠᴀɪʟᴀʙʟᴇ 😶",callback_data="pages", style=ButtonStyle.DANGER)]
        )
    try:
        await query.edit_message_reply_markup(
            reply_markup=InlineKeyboardMarkup(btn)
        )
    except MessageNotModified:
        pass
    await query.answer()

                
@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    me = await client.get_me()
    settings = await db.get_bot(me.id)
    if query.data == "close_data":
        await query.message.delete()

    elif query.data == "pages":
        await query.answer()

    elif query.data == "help":
        text = "<b>👨‍💻 How To Use Bot :-\n\n🔻 /start - check bot is working or not.\n\n🔻 /stats - check bot files and users.\n\n🔻 /settings - configure clone bot settings ( owner only ).\n\n🔻 /reset - reset all settings to default or none ( owner only ).\n\n🔻 /broadcast - broadcast a message to your bot users ( owner only ).</b>"
        btn = [[
            InlineKeyboardButton("🔍 ᴀʙᴏᴜᴛ", callback_data="about", style=ButtonStyle.DANGER),
            InlineKeyboardButton("🏡 ʜᴏᴍᴇ", callback_data="start", style=ButtonStyle.DANGER)
        ]]
        await query.message.edit_text(text = text, reply_markup = InlineKeyboardMarkup(btn))

    elif query.data == "start":
        buttons = [[
            InlineKeyboardButton('⤬ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ⤬', url=f'http://t.me/{me.username}?startgroup=true', style=ButtonStyle.PRIMARY)
        ],[
            InlineKeyboardButton('🕵️ ʜᴇʟᴘ', callback_data='help', style=ButtonStyle.DANGER),
            InlineKeyboardButton('🔍 ᴀʙᴏᴜᴛ', callback_data='about', style=ButtonStyle.DANGER)
        ]]
        update_link = settings.get("update_channel_link") or CHNL_LNK
        if update_link:
            buttons.append([[InlineKeyboardButton('🍿 ᴊᴏɪɴ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟ 🍿', url=update_link, style=ButtonStyle.SUCCESS)]])
        reply_markup = InlineKeyboardMarkup(buttons)
        await query.message.edit_text(text=script.CLONE_START_TXT.format(query.from_user.mention, me.username, me.first_name), reply_markup=reply_markup)

    elif query.data == "about":
        btn = [[
            InlineKeyboardButton('🕵️ ʜᴇʟᴘ', callback_data='help', style=ButtonStyle.DANGER),
            InlineKeyboardButton("🏡 ʜᴏᴍᴇ", callback_data="start", style=ButtonStyle.DANGER)
        ]]
        await query.message.edit_text(text = script.CLONE_ABOUT_TXT.format(me.mention, temp.U_NAME, temp.B_NAME), reply_markup = InlineKeyboardMarkup(btn))
        
    if query.data.startswith("file"):
        clicked = query.from_user.id
        try:
            typed = query.message.reply_to_message.from_user.id
        except:
            typed = query.from_user.id
        ident, file_id = query.data.split("#")
        files_ = await get_file_details(file_id)
        if not files_:
            return await query.answer('Nᴏ sᴜᴄʜ ғɪʟᴇ ᴇxɪsᴛ.')
        files = files_
        title = files['file_name']
        size = get_size(files['file_size'])
        f_caption = files['caption']
        if f_caption is None:
            f_caption = f"{files['file_name']}"

        try:
            if settings['url']:
                if clicked == typed:
                    temp.SHORT[clicked] = query.message.chat.id
                    await query.answer(url=f"https://telegram.me/{me.username}?start=short_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
            else:
                if clicked == typed:
                    await query.answer(url=f"https://telegram.me/{me.username}?start={ident}_{file_id}")
                    return
                else:
                    await query.answer(f"Hᴇʏ {query.from_user.first_name}, Tʜɪs Is Nᴏᴛ Yᴏᴜʀ Mᴏᴠɪᴇ Rᴇǫᴜᴇsᴛ. Rᴇǫᴜᴇsᴛ Yᴏᴜʀ's !", show_alert=True)
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{me.username}?start={ident}_{file_id}")
        except Exception as e:
            await query.answer(url=f"https://telegram.me/{me.username}?start={ident}_{file_id}")
            
    elif query.data.startswith("sendfiles"):
        clicked = query.from_user.id
        ident, key = query.data.split("#")
        try:
            if settings['url']:
                await query.answer(url=f"https://telegram.me/{me.username}?start=sendfiles1_{key}")
            else:
                await query.answer(url=f"https://telegram.me/{me.username}?start=allfiles_{key}")    
                
        except UserIsBlocked:
            await query.answer('Uɴʙʟᴏᴄᴋ ᴛʜᴇ ʙᴏᴛ ᴍᴀʜɴ !', show_alert=True)
        except PeerIdInvalid:
            await query.answer(url=f"https://telegram.me/{me.username}?start=sendfiles3_{key}")
        except Exception as e:
            logger.exception(e)
            await query.answer(url=f"https://telegram.me/{me.username}?start=sendfiles4_{key}")
    
    elif query.data.startswith("send_fsall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = BUTTONS0.get(key) or BUTTONS.get(key) or FRESH.get(key)
        if not search:
            await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
            return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS1.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        search = BUTTONS2.get(key)
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)
        
    elif query.data.startswith("send_fall"):
        temp_var, ident, key, offset = query.data.split("#")
        search = FRESH.get(key)
       # if not search:
        #    await query.answer(script.OLD_ALRT_TXT.format(query.from_user.first_name),show_alert=True)
           # return
        files, n_offset, total = await get_search_results(query.message.chat.id, search, offset=int(offset), filter=True)
        await send_all(client, query.from_user.id, files, ident, query.message.chat.id, query.from_user.first_name, query)
        await query.answer(f"Hey {query.from_user.first_name}, All files on this page has been sent successfully to your PM !", show_alert=True)


async def auto_filter(client, name, msg, reply_msg, ai_search, spoll=False):
    curr_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    if not spoll:
        message = msg
        if message.text.startswith("/"): return  # ignore commands
        if re.findall(r"((^\/|^,|^!|^\.|^[\U0001F600-\U000E007F]).*)", message.text):
            return
        if len(message.text) < 100:
            search = re.sub(r"[_\-\.\+:＿]+", " ", str(name or "")).lower()
            search = re.sub(r"\s+", " ", search).strip()
            find = search.split(" ")
            search = ""
            removes = ["in","upload", "series", "full", "horror", "thriller", "mystery", "print", "file"]
            for x in find:
                if x in removes:
                    continue
                else:
                    search = search + x + " "
            search = re.sub(r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|bro|bruh|broh|helo|that|find|dubbed|link|venum|iruka|pannunga|pannungga|anuppunga|anupunga|anuppungga|anupungga|film|undo|kitti|kitty|tharu|kittumo|kittum|movie|any(one)|with\ssubtitle(s)?)", "", search, flags=re.IGNORECASE)
            search = re.sub(r"\s+", " ", search).strip()
            search = search.replace("-", " ")
            search = search.replace(":", "")
            search = search.replace(".", "")
            files, offset, total_results = await get_search_results(message.chat.id ,search, offset=0, filter=True)
            settings = await get_settings(message.chat.id)
            if not files:
                return await advantage_spell_chok(client, name, msg, reply_msg, ai_search)
        else:
            return
    else:
        message = msg.message.reply_to_message  # msg will be callback query
        search, files, offset, total_results = spoll
        await msg.message.delete()
    key = f"{message.chat.id}-{message.id}"
    FRESH[key] = search
    temp.GETALL[key] = files
    temp.SHORT[message.from_user.id] = message.chat.id
    btn = [
        [
            InlineKeyboardButton(
                text=f"[{get_size(filevj['file_size'])}] {' '.join(filter(lambda x: not x.startswith('[') and not x.startswith('@') and not x.startswith('www.'), re.sub(r'_+', ' ', filevj['file_name']).split()))}", callback_data=f"file#{filevj['file_id']}", style=ButtonStyle.DANGER),
        ]
        for filevj in files
    ]
    btn.insert(0, 
        [
            InlineKeyboardButton(f'ǫᴜᴀʟɪᴛʏ', callback_data=f"qualities#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("ᴇᴘɪsᴏᴅᴇs", callback_data=f"episodes#{key}", style=ButtonStyle.DANGER),
            InlineKeyboardButton("sᴇᴀsᴏɴs",  callback_data=f"seasons#{key}", style=ButtonStyle.DANGER)
        ]
    )
    btn.insert(0, [
        InlineKeyboardButton("𝐒𝐞𝐧𝐝 𝐀𝐥𝐥", callback_data=f"sendfiles#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʟᴀɴɢᴜᴀɢᴇs", callback_data=f"languages#{key}", style=ButtonStyle.DANGER),
        InlineKeyboardButton("ʏᴇᴀʀs", callback_data=f"years#{key}", style=ButtonStyle.DANGER)
    ])
    if offset != "":
        req = message.from_user.id if message.from_user else 0
        btn.append(
            [InlineKeyboardButton("𝐏𝐀𝐆𝐄", callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text=f"1/{math.ceil(int(total_results)/int(MAX_B_TN))}",callback_data="pages", style=ButtonStyle.DANGER), InlineKeyboardButton(text="𝐍𝐄𝐗𝐓 ➪",callback_data=f"next_{req}_{key}_{offset}", style=ButtonStyle.DANGER)]
        )
    else:
        btn.append(
            [InlineKeyboardButton(text="𝐍𝐎 𝐌𝐎𝐑𝐄 𝐏𝐀𝐆𝐄𝐒 𝐀𝐕𝐀𝐈𝐋𝐀𝐁𝐋𝐄",callback_data="pages", style=ButtonStyle.DANGER)]
        )
    imdb = await get_poster(search, file=(files[0])['file_name']) if settings["imdb"] else None
    cur_time = datetime.now(pytz.timezone('Asia/Kolkata')).time()
    time_difference = timedelta(hours=cur_time.hour, minutes=cur_time.minute, seconds=(cur_time.second+(cur_time.microsecond/1000000))) - timedelta(hours=curr_time.hour, minutes=curr_time.minute, seconds=(curr_time.second+(curr_time.microsecond/1000000)))
    remaining_seconds = "{:.2f}".format(time_difference.total_seconds())
    TEMPLATE = script.IMDB_TEMPLATE_TXT
    if imdb:
        cap = TEMPLATE.format(
            qurey=search,
            title=imdb['title'],
            votes=imdb['votes'],
            aka=imdb["aka"],
            seasons=imdb["seasons"],
            box_office=imdb['box_office'],
            localized_title=imdb['localized_title'],
            kind=imdb['kind'],
            imdb_id=imdb["imdb_id"],
            cast=imdb["cast"],
            runtime=imdb["runtime"],
            countries=imdb["countries"],
            certificates=imdb["certificates"],
            languages=imdb["languages"],
            director=imdb["director"],
            writer=imdb["writer"],
            producer=imdb["producer"],
            composer=imdb["composer"],
            cinematographer=imdb["cinematographer"],
            music_team=imdb["music_team"],
            distributors=imdb["distributors"],
            release_date=imdb['release_date'],
            year=imdb['year'],
            genres=imdb['genres'],
            poster=imdb['poster'],
            plot=imdb['plot'],
            rating=imdb['rating'],
            url=imdb['url'],
            **locals()
        )
        temp.IMDB_CAP[message.from_user.id] = cap
    else:
        cap = f"<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 ✦</blockquote>\n\n🎬 <b>Query:</b> <code>{search}</code>\n👤 <b>Requested By:</b> {message.from_user.mention}\n⚡ <b>Speed:</b> <code>{remaining_seconds}s</code>\n🏠 <b>Chat:</b> {message.chat.title or 'MoviesZoneFlix'}\n\n<i>⏳ Auto-deletes in 5 minutes</i>\n\n</b>"
    if imdb and imdb.get('poster'):
        try:
            hehe = await message.reply_photo(photo=imdb.get('poster'), caption=cap, reply_markup=InlineKeyboardMarkup(btn))
            await reply_msg.delete()
            await asyncio.sleep(300)
            await hehe.delete()
            await message.delete()
        except (MediaEmpty, PhotoInvalidDimensions, WebpageMediaEmpty):
            pic = imdb.get('poster')
            poster = pic.replace('.jpg', "._V1_UX360.jpg") 
            hmm = await message.reply_photo(photo=poster, caption=cap, reply_markup=InlineKeyboardMarkup(btn))
            await reply_msg.delete()
            await asyncio.sleep(300)
            await hmm.delete()
            await message.delete()
        except Exception as e:
            logger.exception(e) 
            fek = await reply_msg.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn))
            await asyncio.sleep(300)
            await fek.delete()
            await message.delete()
    else:
        fuk = await reply_msg.edit_text(text=cap, reply_markup=InlineKeyboardMarkup(btn), disable_web_page_preview=True)
        await asyncio.sleep(300)
        await fuk.delete()
        await message.delete()

async def advantage_spell_chok(client, name, msg, reply_msg, vj_search):
    mv_id = msg.id
    mv_rqst = name
    reqstr1 = msg.from_user.id if msg.from_user else 0
    reqstr = await client.get_users(reqstr1)
    query = re.sub(
        r"\b(pl(i|e)*?(s|z+|ease|se|ese|(e+)s(e)?)|((send|snd|giv(e)?|gib)(\sme)?)|movie(s)?|new|latest|br((o|u)h?)*|^h(e|a)?(l)*(o)*|mal(ayalam)?|t(h)?amil|file|that|find|und(o)*|kit(t(i|y)?)?o(w)?|thar(u)?(o)*w?|kittum(o)*|aya(k)*(um(o)*)?|full\smovie|any(one)|with\ssubtitle(s)?)",
        "", msg.text, flags=re.IGNORECASE)  # plis contribute some common words
    query = query.strip() + " movie"
    try:
        movies = await get_poster(mv_rqst, bulk=True)
    except Exception as e:
        logger.exception(e)
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}", style=ButtonStyle.PRIMARY)
        ]]
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    movielist = []
    if not movies:
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}", style=ButtonStyle.PRIMARY)
        ]]
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    movielist += [movie.get('title') for movie in movies]
    movielist += [f"{movie.get('title')} {movie.get('year')}" for movie in movies]
    SPELL_CHECK[mv_id] = movielist
    if vj_search == True:
        vj_search_new = False
        vj_ai_msg = await reply_msg.edit_text("<b><i>Advance Ai Of MoviesZoneFlix Try To Find Your Movie With Your Wrong Spelling.</i></b>")
        movienamelist = []
        movienamelist += [movie.get('title') for movie in movies]
        for techvj in movienamelist:
            try:
                mv_rqst = mv_rqst.capitalize()
            except:
                pass
            if mv_rqst.startswith(techvj[0]):
                await auto_filter(client, techvj, msg, reply_msg, vj_search_new)
                break
        reqst_gle = mv_rqst.replace(" ", "+")
        button = [[
            InlineKeyboardButton("Gᴏᴏɢʟᴇ", url=f"https://www.google.com/search?q={reqst_gle}", style=ButtonStyle.PRIMARY)
        ]]
        k = await reply_msg.edit_text(text=script.I_CUDNT.format(mv_rqst), reply_markup=InlineKeyboardMarkup(button))
        await asyncio.sleep(30)
        await k.delete()
        return
    else:
        btn = [
            [
                InlineKeyboardButton(
                    text=movie_name.strip(),
                    callback_data=f"spol#{reqstr1}#{k}", style=ButtonStyle.DANGER)
            ]
            for k, movie_name in enumerate(movielist)
        ]
        btn.append([InlineKeyboardButton(text="Close", callback_data=f'spol#{reqstr1}#close_spellcheck', style=ButtonStyle.DANGER)])
        spell_check_del = await reply_msg.edit_text(
            text=script.CUDNT_FND.format(mv_rqst),
            reply_markup=InlineKeyboardMarkup(btn)
        )
        await asyncio.sleep(600)
        await spell_check_del.delete()

