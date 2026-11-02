# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix


import os
from plugins.Extra.fotnt_string import Fonts
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from TechVJ.util.telegram_rich import ButtonStyle


@Client.on_message(filters.private & filters.command(["font"]))
async def style_buttons(c, m, cb=False):
    buttons = [[
        InlineKeyboardButton('𝚃𝚢𝚙𝚎𝚠𝚛𝚒𝚝𝚎𝚛', callback_data='style+typewriter', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝕆𝕦𝕥𝕝𝕚𝕟𝕖', callback_data='style+outline', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝐒𝐞𝐫𝐢𝐟', callback_data='style+serif', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('𝑺𝒆𝒓𝒊𝒇', callback_data='style+bold_cool', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝑆𝑒𝑟𝑖𝑓', callback_data='style+cool', style=ButtonStyle.DANGER),
        InlineKeyboardButton('Sᴍᴀʟʟ Cᴀᴘs', callback_data='style+small_cap', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('𝓈𝒸𝓇𝒾𝓅𝓉', callback_data='style+script', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝓼𝓬𝓻𝓲𝓹𝓽', callback_data='style+script_bolt', style=ButtonStyle.DANGER),
        InlineKeyboardButton('ᵗⁱⁿʸ', callback_data='style+tiny', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('ᑕOᗰIᑕ', callback_data='style+comic', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝗦𝗮𝗻𝘀', callback_data='style+sans', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝙎𝙖𝙣𝙨', callback_data='style+slant_sans', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('𝘚𝘢𝘯𝘴', callback_data='style+slant', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝖲𝖺𝗇𝗌', callback_data='style+sim', style=ButtonStyle.DANGER),
        InlineKeyboardButton('Ⓒ︎Ⓘ︎Ⓡ︎Ⓒ︎Ⓛ︎Ⓔ︎Ⓢ︎', callback_data='style+circles', style=ButtonStyle.DANGER)
        ],[
        InlineKeyboardButton('🅒︎🅘︎🅡︎🅒︎🅛︎🅔︎🅢︎', callback_data='style+circle_dark', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝔊𝔬𝔱𝔥𝔦𝔠', callback_data='style+gothic', style=ButtonStyle.DANGER),
        InlineKeyboardButton('𝕲𝖔𝖙𝖍𝖎𝖈', callback_data='style+gothic_bolt', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('C͜͡l͜͡o͜͡u͜͡d͜͡s͜͡', callback_data='style+cloud', style=ButtonStyle.DANGER),
        InlineKeyboardButton('H̆̈ă̈p̆̈p̆̈y̆̈', callback_data='style+happy', style=ButtonStyle.DANGER),
        InlineKeyboardButton('S̑̈ȃ̈d̑̈', callback_data='style+sad', style=ButtonStyle.DANGER),
        ],[
        InlineKeyboardButton('Next ➡️', callback_data="nxt", style=ButtonStyle.DANGER)
    ]]
    if not cb:
        if ' ' in m.text:
            title = m.text.split(" ", 1)[1]
            await m.reply_text(title, reply_markup=InlineKeyboardMarkup(buttons), reply_to_message_id=m.id)                     
        else:
            await m.reply_text(text="Ente Any Text Eg:- `/font [text]`")    
    else:
        await m.answer()
        await m.message.edit_reply_markup(InlineKeyboardMarkup(buttons))


@Client.on_callback_query(filters.regex('^nxt'))
async def nxt(c, m):
    if m.data == "nxt":
        buttons = [[
            InlineKeyboardButton('🇸 🇵 🇪 🇨 🇮 🇦 🇱 ', callback_data='style+special', style=ButtonStyle.DANGER),
            InlineKeyboardButton('🅂🅀🅄🄰🅁🄴🅂', callback_data='style+squares', style=ButtonStyle.DANGER),
            InlineKeyboardButton('🆂︎🆀︎🆄︎🅰︎🆁︎🅴︎🆂︎', callback_data='style+squares_bold', style=ButtonStyle.DANGER),
            ],[
            InlineKeyboardButton('ꪖꪀᦔꪖꪶꪊᥴ𝓲ꪖ', callback_data='style+andalucia', style=ButtonStyle.DANGER),
            InlineKeyboardButton('爪卂几ᘜ卂', callback_data='style+manga', style=ButtonStyle.DANGER),
            InlineKeyboardButton('S̾t̾i̾n̾k̾y̾', callback_data='style+stinky', style=ButtonStyle.DANGER),
            ],[
            InlineKeyboardButton('B̥ͦu̥ͦb̥ͦb̥ͦl̥ͦe̥ͦs̥ͦ', callback_data='style+bubbles', style=ButtonStyle.DANGER),
            InlineKeyboardButton('U͟n͟d͟e͟r͟l͟i͟n͟e͟', callback_data='style+underline', style=ButtonStyle.DANGER),
            InlineKeyboardButton('꒒ꍏꀷꌩꌃꀎꁅ', callback_data='style+ladybug', style=ButtonStyle.DANGER),
            ],[
            InlineKeyboardButton('R҉a҉y҉s҉', callback_data='style+rays', style=ButtonStyle.DANGER),
            InlineKeyboardButton('B҈i҈r҈d҈s҈', callback_data='style+birds', style=ButtonStyle.DANGER),
            InlineKeyboardButton('S̸l̸a̸s̸h̸', callback_data='style+slash', style=ButtonStyle.DANGER),
            ],[
            InlineKeyboardButton('s⃠t⃠o⃠p⃠', callback_data='style+stop', style=ButtonStyle.DANGER),
            InlineKeyboardButton('S̺͆k̺͆y̺͆l̺͆i̺͆n̺͆e̺͆', callback_data='style+skyline', style=ButtonStyle.DANGER),
            InlineKeyboardButton('A͎r͎r͎o͎w͎s͎', callback_data='style+arrows', style=ButtonStyle.DANGER),
            ],[
            InlineKeyboardButton('ዪሀክቿነ', callback_data='style+qvnes', style=ButtonStyle.DANGER),
            InlineKeyboardButton('S̶t̶r̶i̶k̶e̶', callback_data='style+strike', style=ButtonStyle.DANGER),
            InlineKeyboardButton('F༙r༙o༙z༙e༙n༙', callback_data='style+frozen', style=ButtonStyle.DANGER)
            ],[
            InlineKeyboardButton('⬅️ Back', callback_data='nxt+0', style=ButtonStyle.DANGER)
        ]]
        await m.answer()
        await m.message.edit_reply_markup(InlineKeyboardMarkup(buttons))
    else:
        await style_buttons(c, m, cb=True)


@Client.on_callback_query(filters.regex('^style'))
async def style(c, m):
    await m.answer()
    cmd, style = m.data.split('+')

    if style == 'typewriter':
        cls = Fonts.typewriter
    if style == 'outline':
        cls = Fonts.outline
    if style == 'serif':
        cls = Fonts.serief
    if style == 'bold_cool':
        cls = Fonts.bold_cool
    if style == 'cool':
        cls = Fonts.cool
    if style == 'small_cap':
        cls = Fonts.smallcap
    if style == 'script':
        cls = Fonts.script
    if style == 'script_bolt':
        cls = Fonts.bold_script
    if style == 'tiny':
        cls = Fonts.tiny
    if style == 'comic':
        cls = Fonts.comic
    if style == 'sans':
        cls = Fonts.san
    if style == 'slant_sans':
        cls = Fonts.slant_san
    if style == 'slant':
        cls = Fonts.slant
    if style == 'sim':
        cls = Fonts.sim
    if style == 'circles':
        cls = Fonts.circles
    if style == 'circle_dark':
        cls = Fonts.dark_circle
    if style == 'gothic':
        cls = Fonts.gothic
    if style == 'gothic_bolt':
        cls = Fonts.bold_gothic
    if style == 'cloud':
        cls = Fonts.cloud
    if style == 'happy':
        cls = Fonts.happy
    if style == 'sad':
        cls = Fonts.sad
    if style == 'special':
        cls = Fonts.special
    if style == 'squares':
        cls = Fonts.square
    if style == 'squares_bold':
        cls = Fonts.dark_square
    if style == 'andalucia':
        cls = Fonts.andalucia
    if style == 'manga':
        cls = Fonts.manga
    if style == 'stinky':
        cls = Fonts.stinky
    if style == 'bubbles':
        cls = Fonts.bubbles
    if style == 'underline':
        cls = Fonts.underline
    if style == 'ladybug':
        cls = Fonts.ladybug
    if style == 'rays':
        cls = Fonts.rays
    if style == 'birds':
        cls = Fonts.birds
    if style == 'slash':
        cls = Fonts.slash
    if style == 'stop':
        cls = Fonts.stop
    if style == 'skyline':
        cls = Fonts.skyline
    if style == 'arrows':
        cls = Fonts.arrows
    if style == 'qvnes':
        cls = Fonts.rvnes
    if style == 'strike':
        cls = Fonts.strike
    if style == 'frozen':
        cls = Fonts.frozen

    r, oldtxt = m.message.reply_to_message.text.split(None, 1) 
    new_text = cls(oldtxt)            
    try:
        await m.message.edit_text(f"`{new_text}`\n\n👆 Click To Copy", reply_markup=m.message.reply_markup)
    except Exception as e:
        print(e)



