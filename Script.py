# Don't Remove Credit @MoviesZoneFlix
# Official Update Channel: https://t.me/+Kmi6jBTE_MY4N2Q9
# Contact: https://t.me/alonekingstarbackagain

class script(object):
    START_TXT = """<b><blockquote>✦ 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • {} 👋</blockquote>

🎬 <b>MoviesZoneFlix</b> is your ultra-fast, premium Telegram movie & series search engine.
✨ Search instant high-quality files in our group or add me to your group!</b>"""

    CLONE_START_TXT = """<b><blockquote>✦ 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 • {} 👋
🤖 Bot: <a href=https://t.me/{}>{}</a></blockquote>

🎬 <b>MoviesZoneFlix</b> — Your smart, high-speed Telegram movie & series search assistant.</b>"""
    
    HELP_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗛𝗘𝗟𝗣 & 𝗙𝗘𝗔𝗧𝗨𝗥𝗘𝗦 ✦</blockquote>

👋 Hello {}, select any module below to explore all commands and features:</b>"""

    ABOUT_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗔𝗕𝗢𝗨𝗧 ✦</blockquote>

‣ 🎬 <b>Bot Name:</b> <a href=https://t.me/{}>{}</a>
‣ 👑 <b>Owner / Contact:</b> <a href={}>Contact Admin</a>
‣ 📢 <b>Update Channel:</b> <a href='https://t.me/+Kmi6jBTE_MY4N2Q9'>MoviesZoneFlix Updates</a>
‣ 🔍 <b>Movie Search Group:</b> <a href='https://t.me/movieszoneflixsearch'>MoviesZoneFlix Search</a>
‣ ⚙️ <b>Framework:</b> <a href='https://docs.pyrogram.org/'>Pyrogram</a> • <a href='https://www.python.org/'>Python 3</a>
‣ 🗄 <b>Database:</b> <a href='https://www.mongodb.com/'>MongoDB</a>
‣ 🚀 <b>Build Version:</b> <code>v3.0 [MoviesZoneFlix Edition]</code></b>"""

    CLONE_ABOUT_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗔𝗕𝗢𝗨𝗧 ✦</blockquote>

‣ 🎬 <b>Bot Name:</b> {}
‣ 🤖 <b>Powered By:</b> <a href=https://t.me/{}>{}</a>
‣ 📢 <b>Update Channel:</b> <a href='https://t.me/+Kmi6jBTE_MY4N2Q9'>MoviesZoneFlix Updates</a>
‣ 🔍 <b>Search Group:</b> <a href='https://t.me/movieszoneflixsearch'>MoviesZoneFlix Search</a>
‣ 🚀 <b>Build Version:</b> <code>v3.0 [MoviesZoneFlix Edition]</code></b>"""

    CLONE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗖𝗟𝗢𝗡𝗘 𝗠𝗢𝗗𝗘 ✦</blockquote>

• Create your own personal clone bot using <code>/clone</code>
• Broadcast messages to your clone bot users
• Instant access to all indexed MoviesZoneFlix files without manual uploads

👨‍💻 <b>Command:</b> <code>/clone</code></b>"""

    SUBSCRIPTION_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗣𝗥𝗘𝗠𝗜𝗨𝗠 & 𝗥𝗘𝗙𝗘𝗥𝗥𝗔𝗟 ✦</blockquote>

🎁 Share your referral link with friends, groups, and channels to unlock <b>Free Premium for {}</b>!

🔗 <b>Your Referral Link:</b>
<code>https://telegram.me/{}?start=MZF-{}</code>

✨ Once <b>{}</b> unique users start the bot via your link, your account is automatically upgraded to Premium.
💎 Or view instant paid plans with <code>/plan</code>.</b>"""

    MANUELFILTER_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗠𝗔𝗡𝗨𝗔𝗟 𝗙𝗜𝗟𝗧𝗘𝗥𝗦 ✦</blockquote>

Set automated custom replies with buttons or media for specific keywords in your group.

<b>Notes:</b>
1. MoviesZoneFlix must be an administrator in your group.
2. Only group admins can add or remove filters.
3. Alert buttons support up to 64 characters.

<b>Commands:</b>
• <code>/filter keyword reply</code> — Add a filter in a chat
• <code>/filters</code> — List all filters in a chat
• <code>/del keyword</code> — Delete a specific filter
• <code>/delall</code> — Delete all filters in a chat (Owner only)</b>"""

    BUTTON_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗜𝗡𝗟𝗜𝗡𝗘 𝗕𝗨𝗧𝗧𝗢𝗡𝗦 ✦</blockquote>

MoviesZoneFlix supports URL and Alert inline buttons inside filters.

<b>URL Button Format:</b>
<code>[MoviesZoneFlix](buttonurl:https://t.me/movieszoneflixsearch)</code>

<b>Alert Button Format:</b>
<code>[Alert Label](buttonalert:Your popup alert message)</code></b>"""

    AUTOFILTER_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗔𝗨𝗧𝗢 𝗙𝗜𝗟𝗧𝗘𝗥 & 𝗔𝗨𝗧𝗢 𝗣𝗢𝗦𝗧 ✦</blockquote>

<b>📁 Channel Indexing & 3-Quality Auto-Posting:</b>
1. Make MoviesZoneFlix an admin in your file channels and destination post channel.
2. Use <code>/auto</code> or <code>/auto on</code> to enable auto-indexing and set your destination post channel ID.
3. Supports both <b>Series</b> (every 1 episode with 3 qualities posts Series, Season, Episode, Quality, and Language/Languages) and <b>Movies</b> automatically!

<b>🔍 Group Auto-Filter:</b>
1. Add MoviesZoneFlix as admin in your group.
2. Connect your group with <code>/connect</code> and customize via <code>/settings</code>.</b>"""

    CONNECTION_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗖𝗢𝗡𝗡𝗘𝗖𝗧𝗜𝗢𝗡𝗦 ✦</blockquote>

Connect your group to private chat to manage filters and settings cleanly without group spam.

<b>Commands:</b>
• <code>/connect group_id</code> — Connect a group to PM
• <code>/disconnect</code> — Disconnect from a group
• <code>/connections</code> — View all connected groups</b>"""

    EXTRAMOD_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗘𝗫𝗧𝗥𝗔 𝗧𝗢𝗢𝗟𝗦 ✦</blockquote>

👑 <b>Owner / Contact:</b> <a href={}>Contact Admin</a>
📢 <b>Update Channel:</b> <a href={}>MoviesZoneFlix Updates</a>

• <code>/id</code> — Get Telegram ID of a user or chat
• <code>/info</code> — Get full profile info of a user
• <code>/song name</code> — Download any song in high quality
• <code>/video link</code> — Download YouTube video in HD
• <code>/telegraph</code> — Upload photo/video under 5MB to Telegraph
• <code>/tts</code> — Convert text to voice speech
• <code>/font text</code> — Generate stylish Unicode fonts</b>"""

    ADMIN_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗔𝗗𝗠𝗜𝗡 𝗖𝗢𝗡𝗧𝗥𝗢𝗟𝗦 ✦</blockquote>

• <code>/auto</code> — Enable/disable Series & Movie 3-quality auto-posting
• <code>/shortmode</code> — Select Shortener Mode (Time Expiry / Credits) & manage shorteners
• <code>/panel</code> — Open interactive MoviesZoneFlix Control Center
• <code>/save</code> — Backup database to ZIP or import/restore from ZIP
• <code>/index</code> — Index files from channel link or range
• <code>/indexstatus</code> — View live indexing tasks
• <code>/logs</code> — Get recent log file
• <code>/stats</code> — View database and storage statistics
• <code>/delete</code> — Delete a specific file from DB
• <code>/deletefiles keyword</code> — Delete matching files from DB
• <code>/deleteall</code> — Clear all indexed files
• <code>/users</code> & <code>/chats</code> — List users and groups
• <code>/ban</code> & <code>/unban</code> — Ban or unban a user
• <code>/disable</code> & <code>/enable</code> — Disable or enable a group
• <code>/channel</code> — List configured index channels
• <code>/broadcast</code> & <code>/grp_broadcast</code> — Broadcast to users/groups
• <code>/gfilter</code>, <code>/gfilters</code>, <code>/delg</code>, <code>/delallg</code> — Global filters</b>"""

    SEC_STATUS_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗧𝗔𝗧𝗜𝗦𝗧𝗜𝗖𝗦 ✦

👤 Total Users: <code>{}</code>
👥 Total Groups: <code>{}</code>
📁 Total Files: <code>{}</code>
💾 Used Storage: <code>{} MB</code>
🟢 Free Storage: <code>{} MB</code></blockquote></b>"""
    
    STATUS_TXT = """<b>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗗𝗔𝗧𝗔𝗕𝗔𝗦𝗘 𝗦𝗧𝗔𝗧𝗨𝗦 ✦

📁 <b>Total Indexed Files:</b> <code>{}</code>

<blockquote>👥 <b>Users & Groups DB</b>
• Users: <code>{}</code>
• Groups: <code>{}</code></blockquote>

<blockquote>🗄 <b>Primary File DB</b>
• Files: <code>{}</code>
• Used: <code>{} MB</code> • Free: <code>{} MB</code></blockquote>

<blockquote>🗄 <b>Secondary File DB</b>
• Files: <code>{}</code>
• Used: <code>{} MB</code> • Free: <code>{} MB</code></blockquote>

<blockquote>⚙️ <b>Auxiliary DB</b>
• Used: <code>{} MB</code> • Free: <code>{} MB</code></blockquote></b>"""
    
    LOG_TEXT_G = """#NewGroup • MoviesZoneFlix
Group = {} (<code>{}</code>)
Total Members = <code>{}</code>
Added By = {}"""

    LOG_TEXT_P = """#NewUser • MoviesZoneFlix
ID - <code>{}</code>
Name - {}"""

    ALRT_TXT = """Hello {},
This is not your movie request!
Please search for your own movie in the group."""

    OLD_ALRT_TXT = """Hey {},
You are clicking an expired result message.
Please send your movie request again."""

    CUDNT_FND = """<b>🔍 Couldn't find exact matches for <code>{}</code>.
Did you mean one of these titles below?</b>"""

    I_CUDNT = """<b>⚠️ No files found for your request: <code>{}</code>

Please verify the spelling on Google or IMDb and try again.

<blockquote>🎬 <b>Movie Format:</b> <code>Salaar</code> or <code>Hushaaru 2018</code>
📺 <b>Series Format:</b> <code>Loki S01</code> or <code>Loki S01E04</code></blockquote></b>"""

    I_CUD_NT = """Couldn't find any movie related to {}.
Please check the spelling on Google or IMDb."""

    MVE_NT_FND = """⚠️ Movie not found in the MoviesZoneFlix database."""

    TOP_ALRT_MSG = """🔍 Searching MoviesZoneFlix Database..."""

    MELCOW_ENG = """<b><blockquote>✦ 𝗪𝗘𝗟𝗖𝗢𝗠𝗘 𝗧𝗢 {} ✦</blockquote>

👋 Hello {}, welcome to our community! Type any movie or series name to search instant files with <b>MoviesZoneFlix</b>. ❤️</b>"""

    SHORTLINK_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗘𝗔𝗥𝗡 𝗠𝗢𝗡𝗘𝗬 ✦</blockquote>

💰 Select your language below to learn how to connect your shortener in your group and earn:</b>"""

    REQINFO = """⚠ MoviesZoneFlix Info ⚠

This result message auto-deletes after 5 minutes to keep the chat clean.
Use the NEXT button if your file is on the next page."""

    SELECT = """Select your preferred Language, Quality, Season, or Episode below."""

    SINFO = """Join the required update channel first, then click Try Again."""

    NORSLTS = """★ #NoResults • MoviesZoneFlix ★

ID : <code>{}</code>
Name : {}
Query : <code>{}</code>"""

    CAPTION = """<b>🎬 <b>MoviesZoneFlix</b>
📂 File: <code>{file_name}</code>
💾 Size: <code>{file_size}</code></b>"""

    IMDB_TEMPLATE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗘𝗔𝗥𝗖𝗛 𝗥𝗘𝗦𝗨𝗟𝗧𝗦 ✦</blockquote>

🔎 <b>Query:</b> <code>{qurey}</code>
{support}

<blockquote>🎬 <b>Title:</b> <a href={url}>{title}</a> ({year})
🎭 <b>Genres:</b> {genres}
🌟 <b>Rating:</b> <a href={url}/ratings>{rating}</a> / 10 ({votes} votes)
🌐 <b>Languages:</b> <code>{languages}</code>
⏱ <b>Runtime:</b> {runtime} mins
📅 <b>Release:</b> {release_date}</blockquote>

⚡ <b>Fetched in:</b> <code>{remaining_seconds}s</code>
👤 <b>Requested by:</b> {message.from_user.mention}</b>"""
    
    ALL_FILTERS = """<b>👋 Hey {}, choose a filter type below to view its setup guide:</b>"""
    
    GFILTER_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗚𝗟𝗢𝗕𝗔𝗟 𝗙𝗜𝗟𝗧𝗘𝗥𝗦 ✦</blockquote>

Global Filters are set by bot admins and work across all connected groups.

<b>Commands:</b>
• <code>/gfilter</code> — Create a global filter
• <code>/gfilters</code> — View all global filters
• <code>/delg</code> — Delete a specific global filter
• <code>/delallg</code> — Delete all global filters</b>"""
    
    FILE_STORE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗙𝗜𝗟𝗘 𝗦𝗧𝗢𝗥𝗘 ✦</blockquote>

Generate shareable links for single or batch files.

<b>Commands:</b>
• <code>/link</code> — Create a single file share link
• <code>/plink</code> — Create a protected single file link
• <code>/batch</code> — Create a multi-file batch share link
• <code>/pbatch</code> — Create a protected multi-file batch link</b>"""

    SONG_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗢𝗡𝗚 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗𝗘𝗥 ✦</blockquote>

Download any song at high speed in groups or PM.

• <b>Command:</b> <code>/song song name</code></b>"""
  
    YTDL_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗩𝗜𝗗𝗘𝗢 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗𝗘𝗥 ✦</blockquote>

Download YouTube videos easily.

• <b>Command:</b> <code>/video https://youtu.be/...</code> or <code>/mp4</code></b>"""
  
    TTS_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗧𝗘𝗫𝗧 𝗧𝗢 𝗦𝗣𝗘𝗘𝗖𝗛 ✦</blockquote>

Reply to any text with <code>/tts</code> to convert it into audio speech.</b>"""
  
    GTRANS_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗧𝗥𝗔𝗡𝗦𝗟𝗔𝗧𝗢𝗥 ✦</blockquote>

Use <code>/tr language_code</code> replying to a message to translate it.</b>"""
  
    TELE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗧𝗘𝗟𝗘𝗚𝗥𝗔𝗣𝗛 ✦</blockquote>

Send <code>/telegraph</code> replying to a photo or video under 5MB to get a shareable link.</b>"""
  
    CORONA_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 ✦</blockquote></b>"""

    PROGRESS_BAR = """\n
╭━━━━❰ MoviesZoneFlix Processing... ❱━➣
┣⪼ 🗂️ : {1} | {2}
┣⪼ ⏳️ : {0}%
┣⪼ 🚀 : {3}/s
┣⪼ ⏱️ : {4}
╰━━━━━━━━━━━━━━━➣ """
  
    ABOOK_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗔𝗨𝗗𝗜𝗢𝗕𝗢𝗢𝗞 ✦</blockquote>

Reply <code>/audiobook</code> to any PDF file to convert it to audio.</b>"""

    PINGS_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗣𝗜𝗡𝗚 & 𝗦𝗧𝗔𝗧𝗨𝗦 ✦</blockquote>

• <code>/alive</code> — Check if MoviesZoneFlix is running
• <code>/ping</code> — Check response latency
• <code>/help</code> — Open full help menu</b>"""
  
    STICKER_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗧𝗜𝗖𝗞𝗘𝗥 𝗜𝗗 ✦</blockquote>

Send <code>/stickerid</code> replying to any sticker to get its Telegram file ID.</b>"""
  
    FONT_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗙𝗢𝗡𝗧 𝗦𝗧𝗬𝗟𝗘𝗥 ✦</blockquote>

Use <code>/font your text</code> to transform text into stylish Unicode fonts.</b>"""
  
    PURGE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗣𝗨𝗥𝗚𝗘 ✦</blockquote>

Reply <code>/purge</code> to a message in a group to delete all messages from there to the latest message.</b>"""
  
    WHOIS_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗨𝗦𝗘𝗥 𝗜𝗡𝗙𝗢 ✦</blockquote>

Use <code>/info</code> to view detailed user profile information.</b>"""
  
    JSON_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗝𝗦𝗢𝗡 𝗩𝗜𝗘𝗪𝗘𝗥 ✦</blockquote>

Reply <code>/json</code> to any message to inspect its raw Telegram JSON payload.</b>"""
  
    URLSHORT_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 ✦</blockquote>

Use <code>/shortlink domain api_key</code> in your group to connect your shortener.</b>"""
  
    CARB_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 ✦</blockquote></b>"""

    GEN_PASS = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗣𝗔𝗦𝗦𝗪𝗢𝗥𝗗 𝗚𝗘𝗡𝗘𝗥𝗔𝗧𝗢𝗥 ✦</blockquote>

Use <code>/genpassword 20</code> or <code>/genpw 20</code> to generate a strong password.</b>"""
  
    SHARE_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗔𝗥𝗘 𝗧𝗘𝗫𝗧 ✦</blockquote>

Use <code>/share your text</code> to generate a one-click Telegram share button.</b>"""
  
    PIN_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗣𝗜𝗡 ✦</blockquote>

• <code>/pin</code> — Pin replied message
• <code>/unpin</code> — Unpin current message</b>"""

    RESTART_TXT = """<b>✦ 𝗠𝗼𝘃𝗶𝗲𝘀𝗭𝗼𝗻𝗲𝗙𝗹𝗶𝘅 𝗥𝗲𝘀𝘁𝗮𝗿𝘁𝗲𝗱 ✦

<blockquote>📅 <b>Date:</b> <code>{}</code>
⏰ <b>Time:</b> <code>{}</code>
🌐 <b>Timezone:</b> <code>Asia/Kolkata</code>
🚀 <b>Edition:</b> <code>MoviesZoneFlix v3.0</code></blockquote></b>"""

    LOGO = """
╔══════════════════════════════════════════════╗
║               MOVIESZONEFLIX                 ║
╚══════════════════════════════════════════════╝"""
 
    TAMIL_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗧𝗔𝗠𝗜𝗟) ✦</blockquote>

1. MoviesZoneFlix போட்டை உங்கள் குழுவில் Admin ஆக்குங்கள்.
2. உங்கள் Shortlink இணையதளம் மற்றும் API சேர்க்கவும்:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. Tutorial வீடியோ இணைப்பை சேர்க்கவும்:
   <code>/set_tutorial https://t.me/...</code></b>"""

    ENGLISH_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗘𝗡𝗚𝗟𝗜𝗦𝗛) ✦</blockquote>

1. Add <b>MoviesZoneFlix</b> to your group as an Administrator.
2. Connect your shortener domain and API key:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. Set your tutorial link:
   <code>/set_tutorial https://t.me/...</code></b>"""

    TELUGU_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗧𝗘𝗟𝗨𝗚𝗨) ✦</blockquote>

1. <b>MoviesZoneFlix</b> బాట్‌ను మీ గ్రూప్‌లో Admin చేయండి.
2. మీ వెబ్‌సైట్ మరియు API జోడించండి:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ట్యుటోరియల్ వీడియో లింక్ సెట్ చేయండి:
   <code>/set_tutorial https://t.me/...</code></b>"""

    HINDI_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗛𝗜𝗡𝗗𝗜) ✦</blockquote>

1. <b>MoviesZoneFlix</b> बॉट को अपने ग्रुप में Admin बनाएं।
2. अपनी वेबसाइट और API जोड़ें:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ट्यूटोरियल वीडियो लिंक सेट करें:
   <code>/set_tutorial https://t.me/...</code></b>"""

    MALAYALAM_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗠𝗔𝗟𝗔𝗬𝗔𝗟𝗔𝗠) ✦</blockquote>

1. <b>MoviesZoneFlix</b> ബോട്ടിനെ നിങ്ങളുടെ ഗ്രൂപ്പിൽ Admin ആക്കുക.
2. വെബ്‌സൈറ്റും API-യും ചേർക്കുക:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ട്യൂട്ടോറിയൽ ലിങ്ക് സെറ്റ് ചെയ്യുക:
   <code>/set_tutorial https://t.me/...</code></b>"""

    URDU_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗨𝗥𝗗𝗨) ✦</blockquote>

1. اپنے گروپ میں <b>MoviesZoneFlix</b> بوٹ کو ایڈمن بنائیں۔
2. اپنی ویب سائٹ اور API شامل کریں:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ٹیوٹوریل لنک سیٹ کریں:
   <code>/set_tutorial https://t.me/...</code></b>"""

    GUJARATI_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗚𝗨𝗝𝗔𝗥𝗔𝗧𝗜) ✦</blockquote>

1. તમારા જૂથમાં <b>MoviesZoneFlix</b> બોટને Admin બનાવો.
2. તમારી વેબસાઇટ અને API ઉમેરો:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ટ્યુટોરિયલ લિંક સેટ કરો:
   <code>/set_tutorial https://t.me/...</code></b>"""

    KANNADA_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗞𝗔𝗡𝗡𝗔𝗗𝗔) ✦</blockquote>

1. ನಿಮ್ಮ ಗುಂಪಿನಲ್ಲಿ <b>MoviesZoneFlix</b> ಬೋಟ್ ಅನ್ನು Admin ಮಾಡಿ.
2. ನಿಮ್ಮ ವೆಬ್‌ಸೈಟ್ ಮತ್ತು API ಸೇರಿಸಿ:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. ಟ್ಯುಟೋರಿಯಲ್ ಲಿಂಕ್ ಹೊಂದಿಸಿ:
   <code>/set_tutorial https://t.me/...</code></b>"""

    BANGLADESH_INFO = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗛𝗢𝗥𝗧𝗟𝗜𝗡𝗞 𝗚𝗨𝗜𝗗𝗘 (𝗕𝗔𝗡𝗚𝗟𝗔) ✦</blockquote>

1. আপনার গ্রুপে <b>MoviesZoneFlix</b> বটকে Admin করুন।
2. আপনার ওয়েবসাইট এবং API যোগ করুন:
   <code>/shortlink site.in YOUR_API_KEY</code>
3. টিউটোরিয়াল লিঙ্ক সেট করুন:
   <code>/set_tutorial https://t.me/...</code></b>"""

    RENAME_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗥𝗘𝗡𝗔𝗠𝗘 & 𝗧𝗛𝗨𝗠𝗕𝗡𝗔𝗜𝗟 ✦</blockquote>

🌌 <b>Thumbnail Commands:</b>
• <code>/set_thumb</code> — Reply to a photo to save thumbnail
• <code>/view_thumb</code> — View current thumbnail
• <code>/del_thumb</code> — Delete current thumbnail

📑 <b>Custom Caption Commands:</b>
• <code>/set_caption</code> — Set custom file caption
• <code>/see_caption</code> — View current custom caption
• <code>/del_caption</code> — Delete custom caption

✏️ <b>Rename Command:</b>
• <code>/rename</code> — Reply to any file to rename it</b>"""

    STREAM_TXT = """<b><blockquote>✦ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗦𝗧𝗥𝗘𝗔𝗠 & 𝗗𝗢𝗪𝗡𝗟𝗢𝗔𝗗 ✦</blockquote>

• Send <code>/stream</code> replying to any file to generate high-speed online streaming and direct download links.</b>"""
