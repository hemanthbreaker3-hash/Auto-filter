# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import os, string, logging, random, asyncio, time, datetime, re, sys, json, base64, html as html_lib
from Script import script
from pyrogram import Client, filters, enums
from pyrogram.errors import ChatAdminRequired, FloodWait, UserIsBlocked, PeerIdInvalid
from pyrogram.types import *
from TechVJ.util.telegram_rich import ButtonStyle, api_request, make_inline_keyboard
from database.ia_filterdb import col, sec_col, delete_file_everywhere, drop_all_file_collections, get_file_details, unpack_new_file_id, get_bad_files
from database.users_chats_db import (
    db, delete_all_referal_users, get_referal_users_count, get_referal_all_users,
    referal_add_user, normalize_channel_id, parse_duration_to_seconds, format_seconds_human
)
from database.join_reqs import JoinReqs
from info import (
    CLONE_MODE, OWNER_LNK, REACTIONS, CHANNELS, REQUEST_TO_JOIN_MODE, TRY_AGAIN_BTN,
    ADMINS, SHORTLINK_MODE, PREMIUM_AND_REFERAL_MODE, STREAM_MODE, AUTH_CHANNEL,
    REFERAL_PREMEIUM_TIME, REFERAL_COUNT, PAYMENT_TEXT, PAYMENT_QR, LOG_CHANNEL, PICS,
    BATCH_FILE_CAPTION, CUSTOM_FILE_CAPTION, PROTECT_CONTENT, CHNL_LNK, GRP_LNK,
    REQST_CHANNEL, SUPPORT_CHAT, MAX_B_TN, VERIFY, SHORTLINK_API, SHORTLINK_URL,
    TUTORIAL, VERIFY_TUTORIAL, IS_TUTORIAL, URL
)
from plugins.admin_filter import ADMIN_FILTER
from utils import (
    get_settings, pub_is_subscribed, get_size, is_subscribed, save_group_settings,
    temp, verify_user, check_token, check_verification, get_token, get_shortlink,
    get_tutorial, get_seconds, get_force_subscribe_chats, has_force_subscribe,
    format_file_caption, get_file_stream_markup, is_verification_needed, build_verification_prompt
)
from database.connections_mdb import active_connection
from urllib.parse import quote_plus
from TechVJ.util.file_properties import get_name, get_hash, get_media_file_size
from TechVJ.util.auto_post import parse_movie_caption, format_auto_post_message

logger = logging.getLogger(__name__)

BATCH_FILES = {}
join_db = JoinReqs


def _safe_mention(user):
    if not user:
        return "there"
    name = user.first_name or user.username or "there"
    return f'<a href="tg://user?id={user.id}">{html_lib.escape(name)}</a>'


def _safe_text(value):
    return html_lib.escape(str(value)) if value is not None else ""


def _start_buttons(client_username):
    rows = [
        [{"text": "➕  ADD ME TO YOUR GROUP", "url": f"https://t.me/{client_username}?startgroup=true", "style": "primary"}],
        [
            {"text": "🎬  MOVIE SEARCH GROUP", "url": GRP_LNK, "style": "success"},
            {"text": "📢  UPDATE CHANNEL", "url": CHNL_LNK, "style": "primary"},
        ],
        [
            {"text": "✨  EARN MONEY", "callback_data": "shortlink_info", "style": "success"},
            {"text": "❔  HELP", "callback_data": "help", "style": "primary"},
            {"text": "ℹ️  ABOUT", "callback_data": "about", "style": "primary"},
        ],
        [{"text": "👑  CONTACT ADMIN", "url": OWNER_LNK, "style": "danger"}],
    ]
    if PREMIUM_AND_REFERAL_MODE:
        rows.insert(3, [{"text": "💎  PREMIUM & REFERRAL", "callback_data": "subscription", "style": "success"}])
    if CLONE_MODE:
        rows.append([{"text": "🤖  CREATE YOUR OWN CLONE BOT", "callback_data": "clone", "style": "primary"}])
    return rows


async def _send_start_screen(client, message, *, group=False):
    who = _safe_mention(message.from_user) if message.from_user else _safe_text(message.chat.title)
    caption = script.START_TXT.format(who, temp.U_NAME, temp.B_NAME)
    markup = make_inline_keyboard(_start_buttons(temp.U_NAME))
    try:
        if group:
            await api_request(client, "sendMessage", {
                "chat_id": message.chat.id,
                "text": caption,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
                "reply_markup": markup,
            })
        else:
            await api_request(client, "sendPhoto", {
                "chat_id": message.chat.id,
                "photo": "https://files.catbox.moe/mau8mb.jpg",
                "caption": caption,
                "parse_mode": "HTML",
                "reply_markup": markup,
            })
    except Exception as e:
        logger.exception("Start screen send failed, falling back to plain text: %s", e)
        plain = re.sub(r"<[^>]+>", "", caption)
        if group:
            await api_request(client, "sendMessage", {
                "chat_id": message.chat.id,
                "text": plain,
                "reply_markup": markup,
            })
        else:
            await api_request(client, "sendPhoto", {
                "chat_id": message.chat.id,
                "photo": "https://files.catbox.moe/mau8mb.jpg",
                "caption": plain,
                "reply_markup": markup,
            })


async def _auto_delete_later(messages_to_delete, notice_msg, delay=600, final_text="<b>✅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ</b>", final_markup=None):
    """Delete sent media messages after `delay` seconds in the background without blocking handlers."""
    try:
        await asyncio.sleep(delay)
        for m in messages_to_delete:
            if m:
                try:
                    await m.delete()
                except Exception:
                    pass
        if notice_msg:
            try:
                await notice_msg.edit_text(final_text, reply_markup=final_markup)
            except Exception:
                pass
    except Exception:
        pass


async def _deliver_single_file(client, user_id, file_id, pre="file"):
    """Deliver a single indexed file to `user_id` with stream buttons and scheduled auto-delete."""
    files_ = await get_file_details(file_id)
    reply_markup = await get_file_stream_markup(file_id)
    if not files_:
        msg = await client.send_cached_media(
            chat_id=user_id,
            file_id=file_id,
            protect_content=(pre == 'filep'),
            reply_markup=reply_markup,
        )
        filetype = msg.media
        file_obj = getattr(msg, filetype.value)
        title = getattr(file_obj, "file_name", "File")
        f_caption = format_file_caption(getattr(msg, 'caption', None), title, CHNL_LNK)
        await msg.edit_caption(caption=f_caption, parse_mode=enums.ParseMode.HTML)
    else:
        title = files_["file_name"]
        f_caption = format_file_caption(files_.get("caption"), title, CHNL_LNK)
        msg = await client.send_cached_media(
            chat_id=user_id,
            file_id=file_id,
            caption=f_caption,
            parse_mode=enums.ParseMode.HTML,
            protect_content=(pre == 'filep'),
            reply_markup=reply_markup,
        )
    btn = [[InlineKeyboardButton("✅ ɢᴇᴛ ғɪʟᴇ ᴀɢᴀɪɴ ✅", callback_data=f'del#{file_id}', style=ButtonStyle.DANGER)]]
    k = await msg.reply(
        text=(
            "<blockquote><b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\n"
            "ᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b><u>10 mins</u> 🫥</b> <i>(ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs)</i>.\n\n"
            "<b><i>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ᴏʀ ᴀɴʏ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ.</i></b></blockquote>"
        )
    )
    asyncio.create_task(
        _auto_delete_later(
            [msg],
            k,
            delay=600,
            final_text="<b>✅ ʏᴏᴜʀ ᴍᴇssᴀɢᴇ ɪs sᴜᴄᴄᴇssғᴜʟʟʏ ᴅᴇʟᴇᴛᴇᴅ ɪғ ʏᴏᴜ ᴡᴀɴᴛ ᴀɢᴀɪɴ ᴛʜᴇɴ ᴄʟɪᴄᴋ ᴏɴ ʙᴇʟᴏᴡ ʙᴜᴛᴛᴏɴ</b>",
            final_markup=InlineKeyboardMarkup(btn),
        )
    )
    return msg


@Client.on_message(filters.command("start") & filters.incoming)
async def start(client, message):
    try:
        asyncio.create_task(message.react(emoji=random.choice(REACTIONS), big=True))
    except Exception:
        pass

    if message.chat.type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        await _send_start_screen(client, message, group=True)
        if not await db.get_chat(message.chat.id):
            try:
                total = await client.get_chat_members_count(message.chat.id)
                if LOG_CHANNEL:
                    await client.send_message(LOG_CHANNEL, script.LOG_TEXT_G.format(message.chat.title, message.chat.id, total, "Unknown"))
                await db.add_chat(message.chat.id, message.chat.title)
            except Exception:
                pass
        return

    if not message.from_user:
        return
    if not await db.is_user_exist(message.from_user.id):
        await db.add_user(message.from_user.id, message.from_user.first_name)
        if LOG_CHANNEL:
            try:
                await client.send_message(LOG_CHANNEL, script.LOG_TEXT_P.format(message.from_user.id, _safe_mention(message.from_user)))
            except Exception:
                pass

    if await has_force_subscribe() and not await is_subscribed(client, message):
        try:
            destinations = await get_force_subscribe_chats()
            btn = await pub_is_subscribed(client, message, destinations)
            if not btn:
                return await message.reply_text("Unable to create FSub join buttons. Please contact the bot administrator.")
            if len(message.command) > 1 and message.command[1] != "subscribe":
                if TRY_AGAIN_BTN:
                    try:
                        kk, file_id = message.command[1].split("_", 1)
                        btn.append([InlineKeyboardButton("↻ CHECK SUBSCRIPTION", callback_data=f"checksub#{kk}#{file_id}", style=ButtonStyle.DANGER)])
                    except (IndexError, ValueError):
                        btn.append([InlineKeyboardButton("↻ CHECK SUBSCRIPTION", url=f"https://t.me/{temp.U_NAME}?start={message.command[1]}", style=ButtonStyle.SUCCESS)])
                else:
                    await db.set_msg_command(message.from_user.id, com=message.command[1])
            styled_rows = []
            for row in btn:
                styled = []
                for button in row:
                    item = {"text": button.text}
                    if getattr(button, "url", None):
                        item["url"] = button.url
                    elif getattr(button, "callback_data", None):
                        item["callback_data"] = button.callback_data
                    else:
                        continue
                    item["style"] = "success" if item.get("url") else "primary"
                    styled.append(item)
                if styled:
                    styled_rows.append(styled)
            await api_request(client, "sendMessage", {
                "chat_id": message.from_user.id,
                "text": "<b>🔒 Join all required channels/groups below, then return and try again.</b>",
                "parse_mode": "HTML",
                "reply_markup": make_inline_keyboard(styled_rows),
            })
            return
        except Exception as e:
            logger.exception("Force-subscribe prompt failed: %s", e)
            return await message.reply_text("Something went wrong while checking force subscribe. Please contact the administrator.")

    if len(message.command) != 2 or (len(message.command) == 2 and message.command[1] in ["subscribe", "error", "okay", "help"]):
        await _send_start_screen(client, message)
        return

    data = message.command[1]
    if data.split("-", 1)[0] in ("MZF", "TGB"):
        user_id = int(data.split("-", 1)[1])
        vj = await referal_add_user(user_id, message.from_user.id)
        if vj and PREMIUM_AND_REFERAL_MODE:
            await message.reply(f"<b>You have joined using the referral link of user with ID {user_id}\n\nSend /start again to use the bot</b>")
            num_referrals = await get_referal_users_count(user_id)
            await client.send_message(chat_id=user_id, text="<b>{} start the bot with your referral link\n\nTotal Referals - {}</b>".format(_safe_mention(message.from_user), num_referrals))
            if num_referrals == REFERAL_COUNT:
                t_str = REFERAL_PREMEIUM_TIME
                seconds = await get_seconds(t_str)
                if seconds > 0:
                    expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
                    user_data = {"id": user_id, "expiry_time": expiry_time}
                    await db.update_user(user_data)
                    await delete_all_referal_users(user_id)
                    await client.send_message(chat_id=user_id, text="<b>You Have Successfully Completed Total Referal.\n\nYou Added In Premium For {}</b>".format(REFERAL_PREMEIUM_TIME))
                    return
        else:
            await _send_start_screen(client, message)
            return
    try:
        pre, file_id = data.split('_', 1)
    except Exception:
        file_id = data
        pre = ""

    if data.split("-", 1)[0] == "BATCH":
        sts = await message.reply("<b>⚡ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>")
        file_id = data.split("-", 1)[1]
        msgs = BATCH_FILES.get(file_id)
        if not msgs:
            file = await client.download_media(file_id)
            try:
                with open(file) as file_data:
                    msgs = json.loads(file_data.read())
            except Exception:
                await sts.edit("FAILED")
                return await client.send_message(LOG_CHANNEL, "UNABLE TO OPEN FILE.")
            os.remove(file)
            BATCH_FILES[file_id] = msgs

        filesarr = []
        stream_enabled = await db.get_link_feature("stream_enabled")
        download_enabled = await db.get_link_feature("download_enabled")
        can_link = bool(STREAM_MODE and (stream_enabled or download_enabled))
        for msg in msgs:
            title = msg.get("title")
            f_caption = format_file_caption(msg.get("caption"), title, CHNL_LNK)
            reply_markup = None
            try:
                if can_link:
                    log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=msg.get("file_id"))
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button = []
                    row1 = []
                    if download_enabled:
                        row1.append(InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download, style=ButtonStyle.SUCCESS))
                    if stream_enabled:
                        row1.append(InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream, style=ButtonStyle.SUCCESS))
                    if row1:
                        button.append(row1)
                    if stream_enabled:
                        button.append([InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream), style=ButtonStyle.SUCCESS)])
                    reply_markup = InlineKeyboardMarkup(button) if button else None

                sent_msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    parse_mode=enums.ParseMode.HTML,
                    protect_content=msg.get('protect', False),
                    reply_markup=reply_markup
                )
                filesarr.append(sent_msg)
            except FloodWait as e:
                await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
                sent_msg = await client.send_cached_media(
                    chat_id=message.from_user.id,
                    file_id=msg.get("file_id"),
                    caption=f_caption,
                    parse_mode=enums.ParseMode.HTML,
                    protect_content=msg.get('protect', False),
                    reply_markup=reply_markup
                )
                filesarr.append(sent_msg)
            except Exception:
                continue
            await asyncio.sleep(0.35)
        await sts.delete()
        k = await client.send_message(
            chat_id=message.from_user.id,
            text="<blockquote><b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b><u>10 mins</u> 🫥</b> <i>(ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs)</i>.\n\n<b><i>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ᴏʀ ᴀɴʏ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ.</i></b></blockquote>"
        )
        asyncio.create_task(_auto_delete_later(filesarr, k, delay=600))
        return

    elif data.split("-", 1)[0] == "DSTORE":
        sts = await message.reply("<b>⚡ ᴘʟᴇᴀsᴇ ᴡᴀɪᴛ...</b>")
        b_string = data.split("-", 1)[1]
        decoded = (base64.urlsafe_b64decode(b_string + "=" * (-len(b_string) % 4))).decode("ascii")
        try:
            f_msg_id, l_msg_id, f_chat_id, protect = decoded.split("_", 3)
        except Exception:
            f_msg_id, l_msg_id, f_chat_id = decoded.split("_", 2)
            protect = "/pbatch" if PROTECT_CONTENT else "batch"
        filesarr = []
        stream_enabled = await db.get_link_feature("stream_enabled")
        download_enabled = await db.get_link_feature("download_enabled")
        can_link = bool(STREAM_MODE and (stream_enabled or download_enabled))
        async for msg in client.iter_messages(int(f_chat_id), int(l_msg_id), int(f_msg_id)):
            if msg.media:
                media = getattr(msg, msg.media.value)
                file_type = msg.media
                file = getattr(msg, file_type.value)
                file_name = getattr(media, 'file_name', '')
                f_caption = format_file_caption(getattr(msg, 'caption', None), file_name, CHNL_LNK)
                file_id = file.file_id
                reply_markup = None
                if can_link:
                    log_msg = await client.send_cached_media(chat_id=LOG_CHANNEL, file_id=file_id)
                    stream = f"{URL}watch/{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    download = f"{URL}{str(log_msg.id)}/{quote_plus(get_name(log_msg))}?hash={get_hash(log_msg)}"
                    button = []
                    row1 = []
                    if download_enabled:
                        row1.append(InlineKeyboardButton("• ᴅᴏᴡɴʟᴏᴀᴅ •", url=download, style=ButtonStyle.SUCCESS))
                    if stream_enabled:
                        row1.append(InlineKeyboardButton('• ᴡᴀᴛᴄʜ •', url=stream, style=ButtonStyle.SUCCESS))
                    if row1:
                        button.append(row1)
                    if stream_enabled:
                        button.append([InlineKeyboardButton("• ᴡᴀᴛᴄʜ ɪɴ ᴡᴇʙ ᴀᴘᴘ •", web_app=WebAppInfo(url=stream), style=ButtonStyle.SUCCESS)])
                    reply_markup = InlineKeyboardMarkup(button) if button else None
                try:
                    p = await msg.copy(message.chat.id, caption=f_caption, parse_mode=enums.ParseMode.HTML, protect_content=(protect == "/pbatch"), reply_markup=reply_markup)
                except FloodWait as e:
                    await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
                    p = await msg.copy(message.chat.id, caption=f_caption, parse_mode=enums.ParseMode.HTML, protect_content=(protect == "/pbatch"), reply_markup=reply_markup)
                except Exception:
                    continue
            elif msg.empty:
                continue
            else:
                try:
                    p = await msg.copy(message.chat.id, protect_content=(protect == "/pbatch"))
                except FloodWait as e:
                    await asyncio.sleep(getattr(e, "value", getattr(e, "x", 5)))
                    p = await msg.copy(message.chat.id, protect_content=(protect == "/pbatch"))
                except Exception:
                    continue
            filesarr.append(p)
            await asyncio.sleep(0.35)
        await sts.delete()
        k = await client.send_message(
            chat_id=message.from_user.id,
            text="<blockquote><b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b><u>10 mins</u> 🫥</b> <i>(ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs)</i>.\n\n<b><i>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ᴏʀ ᴀɴʏ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ.</i></b></blockquote>"
        )
        asyncio.create_task(_auto_delete_later(filesarr, k, delay=600))
        return

    elif data.split("-", 1)[0] == "verify":
        parts = data.split("-", 2)
        if len(parts) < 3:
            return await message.reply_text(text="<b>⚠️ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ</b>", protect_content=True)
        userid = parts[1]
        token = parts[2]
        if str(message.from_user.id) != str(userid):
            return await message.reply_text(text="<b>⚠️ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ</b>", protect_content=True)
        is_valid = await check_token(client, userid, token)
        if is_valid:
            granted = await verify_user(client, userid, token)
            g_mode = granted.get("granted_mode", "time")
            if g_mode == "credits":
                added_c = granted.get("granted_credits", 5)
                tot_c = granted.get("verify_credits", added_c)
                text = (
                    f"<b><blockquote>✅ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗</blockquote>\n\n"
                    f"👋 Hey {_safe_mention(message.from_user)},\n"
                    f"🎉 Verification completed!\n\n"
                    f"🎟 <b>Credits Added:</b> <code>+{added_c} Credits</code>\n"
                    f"💳 <b>Available Balance:</b> <code>{tot_c} File Credits</code>\n\n"
                    f"<i>You can now download files directly using your credits!</i></b>"
                )
            else:
                dur_str = format_seconds_human(granted.get("granted_seconds", 86400))
                text = (
                    f"<b><blockquote>✅ 𝗠𝗢𝗩𝗜𝗘𝗦𝗭𝗢𝗡𝗘𝗙𝗟𝗜𝗫 • 𝗩𝗘𝗥𝗜𝗙𝗜𝗘𝗗</blockquote>\n\n"
                    f"👋 Hey {_safe_mention(message.from_user)},\n"
                    f"🎉 Verification completed!\n\n"
                    f"⏳ <b>Direct Access Duration:</b> <code>{dur_str}</code>\n\n"
                    f"<i>Enjoy unlimited direct file downloads until your pass expires!</i></b>"
                )
            if PREMIUM_AND_REFERAL_MODE:
                text += "\n\n💎 <i>Want permanent ad-free access? Send /plan to view Premium plans.</i>"
            await message.reply_text(text=text, protect_content=True)

            # Automatically deliver any pending file that triggered verification
            pending = granted.get("pending")
            if pending and isinstance(pending, str):
                if pending.startswith("file:"):
                    _, p_pre, p_fid = pending.split(":", 2)
                    if g_mode == "credits":
                        await db.check_and_consume_access(message.from_user.id, cost=1, consume=True)
                    await _deliver_single_file(client, message.from_user.id, p_fid, pre=p_pre)
            return
        else:
            return await message.reply_text(text="<b>⚠️ ɪɴᴠᴀʟɪᴅ ʟɪɴᴋ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ</b>", protect_content=True)

    # Determine group & shortener mode context
    user_id = message.from_user.id
    chat_id = temp.SHORT.get(user_id)
    scfg = await db.get_shortener_config()

    if data.startswith("sendfiles"):
        try:
            chat_id = int("-" + file_id.split("-")[1])
        except Exception:
            pass
        settings = await get_settings(chat_id)
        pre = 'allfilesp' if settings['file_secure'] else 'allfiles'
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        eff_mode = grp_mode if grp_mode in ("time", "credits", "link", "off") else scfg["mode"]

        if eff_mode in ("time", "credits") and not await db.has_premium_access(user_id):
            if await check_verification(client, user_id, chat_id=chat_id, cost=1, consume=False):
                # User is already verified; redirect straight to sending all files!
                data = f"{pre}_{file_id}"
            else:
                v_text, v_markup = await build_verification_prompt(
                    client,
                    user_id,
                    _safe_mention(message.from_user),
                    f"https://telegram.me/{temp.U_NAME}?start=",
                    chat_id=chat_id,
                )
                return await message.reply_text(v_text, reply_markup=v_markup, protect_content=True)
        elif eff_mode == "link" and not await db.has_premium_access(user_id):
            g = await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start={pre}_{file_id}")
            btn = [[InlineKeyboardButton('📥 ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ 📥', url=g, style=ButtonStyle.SUCCESS)]]
            tut = await get_tutorial(chat_id)
            if tut:
                btn.append([InlineKeyboardButton('🎬 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ', url=tut, style=ButtonStyle.PRIMARY)])
            text = "<b>✅ ʏᴏᴜʀ ғɪʟᴇs ᴀʀᴇ ʀᴇᴀᴅʏ! ᴄʟɪᴄᴋ ᴏɴ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ᴜɴʟᴏᴄᴋ ᴀʟʟ ғɪʟᴇs.\n\n</b>"
            if PREMIUM_AND_REFERAL_MODE:
                text += "<b>💎 ᴡᴀɴᴛ ᴅɪʀᴇᴄᴛ ғɪʟᴇꜱ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʟɪɴᴋs? ꜱᴇɴᴅ /plan ᴛᴏ ʙᴜʏ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ.</b>"
            k = await client.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(btn))
            asyncio.create_task(_auto_delete_later([], k, delay=300))
            return
        else:
            data = f"{pre}_{file_id}"

    elif data.startswith("short"):
        settings = await get_settings(chat_id)
        pre = 'filep' if settings['file_secure'] else 'file'
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        eff_mode = grp_mode if grp_mode in ("time", "credits", "link", "off") else scfg["mode"]

        if eff_mode in ("time", "credits") and not await db.has_premium_access(user_id):
            if await check_verification(client, user_id, chat_id=chat_id, cost=1, consume=True):
                return await _deliver_single_file(client, user_id, file_id, pre=pre)
            v_text, v_markup = await build_verification_prompt(
                client,
                user_id,
                _safe_mention(message.from_user),
                f"https://telegram.me/{temp.U_NAME}?start=",
                pending_data=f"file:{pre}:{file_id}",
                chat_id=chat_id,
            )
            return await message.reply_text(v_text, reply_markup=v_markup, protect_content=True)

        g = await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start={pre}_{file_id}")
        btn = [[InlineKeyboardButton('📥 ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ 📥', url=g, style=ButtonStyle.SUCCESS)]]
        tut = await get_tutorial(chat_id)
        if tut:
            btn.append([InlineKeyboardButton('🎬 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ', url=tut, style=ButtonStyle.PRIMARY)])
        text = "<b>✅ ʏᴏᴜʀ ғɪʟᴇ ɪs ʀᴇᴀᴅʏ! ᴄʟɪᴄᴋ ᴏɴ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇ.\n\n</b>"
        if PREMIUM_AND_REFERAL_MODE:
            text += "<b>💎 ᴡᴀɴᴛ ᴅɪʀᴇᴄᴛ ғɪʟᴇꜱ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʟɪɴᴋs? ꜱᴇɴᴅ /plan ᴛᴏ ʙᴜʏ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ.</b>"
        k = await client.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(btn))
        asyncio.create_task(_auto_delete_later([], k, delay=1200))
        return

    if data.startswith("all"):
        files = temp.GETALL.get(file_id)
        if not files:
            return await message.reply('<b><i>No such file exist.</i></b>')
        if not await db.has_premium_access(user_id) and await is_verification_needed(chat_id=chat_id):
            if not await check_verification(client, user_id, chat_id=chat_id, cost=1, consume=True):
                v_text, v_markup = await build_verification_prompt(
                    client,
                    user_id,
                    _safe_mention(message.from_user),
                    f"https://telegram.me/{temp.U_NAME}?start=",
                    chat_id=chat_id,
                )
                return await message.reply_text(v_text, reply_markup=v_markup, protect_content=True)
        filesarr = []
        for file in files:
            fid = file["file_id"]
            files1 = await get_file_details(fid)
            if not files1:
                continue
            title = files1["file_name"]
            f_caption = format_file_caption(files1.get("caption"), title, CHNL_LNK)
            reply_markup = await get_file_stream_markup(fid)
            msg = await client.send_cached_media(
                chat_id=user_id,
                file_id=fid,
                caption=f_caption,
                parse_mode=enums.ParseMode.HTML,
                protect_content=(pre == 'allfilesp'),
                reply_markup=reply_markup
            )
            filesarr.append(msg)
        k = await client.send_message(
            chat_id=user_id,
            text="<blockquote><b><u>❗️❗️❗️IMPORTANT❗️️❗️❗️</u></b>\n\nᴛʜɪs ᴍᴇssᴀɢᴇ ᴡɪʟʟ ʙᴇ ᴅᴇʟᴇᴛᴇᴅ ɪɴ <b><u>10 mins</u> 🫥</b> <i>(ᴅᴜᴇ ᴛᴏ ᴄᴏᴘʏʀɪɢʜᴛ ɪssᴜᴇs)</i>.\n\n<b><i>ᴘʟᴇᴀsᴇ ғᴏʀᴡᴀʀᴅ ᴛʜɪs ᴍᴇssᴀɢᴇ ᴛᴏ ʏᴏᴜʀ sᴀᴠᴇᴅ ᴍᴇssᴀɢᴇs ᴏʀ ᴀɴʏ ᴘʀɪᴠᴀᴛᴇ ᴄʜᴀᴛ.</i></b></blockquote>"
        )
        asyncio.create_task(_auto_delete_later(filesarr, k, delay=600))
        return

    elif data.startswith("files"):
        settings = await get_settings(chat_id)
        pre = 'filep' if settings['file_secure'] else 'file'
        grp_mode = str(settings.get("shortener_mode") or "global").lower()
        eff_mode = grp_mode if grp_mode in ("time", "credits", "link", "off") else scfg["mode"]
        if eff_mode == "link" and settings.get('is_shortlink') and not await db.has_premium_access(user_id):
            g = await get_shortlink(chat_id, f"https://telegram.me/{temp.U_NAME}?start={pre}_{file_id}")
            btn = [[InlineKeyboardButton('📥 ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ 📥', url=g, style=ButtonStyle.SUCCESS)]]
            tut = await get_tutorial(chat_id)
            if tut:
                btn.append([InlineKeyboardButton('🎬 ʜᴏᴡ ᴛᴏ ᴅᴏᴡɴʟᴏᴀᴅ', url=tut, style=ButtonStyle.PRIMARY)])
            text = "<b>✅ ʏᴏᴜʀ ғɪʟᴇ ɪs ʀᴇᴀᴅʏ! ᴄʟɪᴄᴋ ᴏɴ ᴅᴏᴡɴʟᴏᴀᴅ ɴᴏᴡ ʙᴜᴛᴛᴏɴ ᴛᴏ ɢᴇᴛ ʏᴏᴜʀ ғɪʟᴇ.\n\n</b>"
            if PREMIUM_AND_REFERAL_MODE:
                text += "<b>💎 ᴡᴀɴᴛ ᴅɪʀᴇᴄᴛ ғɪʟᴇꜱ ᴡɪᴛʜᴏᴜᴛ ᴀɴʏ ʟɪɴᴋs? ꜱᴇɴᴅ /plan ᴛᴏ ʙᴜʏ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ.</b>"
            k = await client.send_message(chat_id=user_id, text=text, reply_markup=InlineKeyboardMarkup(btn))
            asyncio.create_task(_auto_delete_later([], k, delay=1200))
            return

    files_ = await get_file_details(file_id)
    if not files_:
        try:
            pre, file_id = ((base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))).decode("ascii")).split("_", 1)
        except Exception:
            return await message.reply('No such file exist.')

    if not await db.has_premium_access(user_id) and await is_verification_needed(chat_id=chat_id):
        if not await check_verification(client, user_id, chat_id=chat_id, cost=1, consume=True):
            v_text, v_markup = await build_verification_prompt(
                client,
                user_id,
                _safe_mention(message.from_user),
                f"https://telegram.me/{temp.U_NAME}?start=",
                pending_data=f"file:{pre}:{file_id}",
                chat_id=chat_id,
            )
            return await message.reply_text(v_text, reply_markup=v_markup, protect_content=True)

    try:
        await _deliver_single_file(client, user_id, file_id, pre=pre)
    except Exception:
        return await message.reply('No such file exist.')


@Client.on_message(filters.command('channel') & ADMIN_FILTER)
async def channel_info(bot, message):
    managed = await db.get_managed_channels()
    text = '📑 **Configured Auto-Index Channels/Groups**\n'
    for channel in managed:
        try:
            chat = await bot.get_chat(channel)
            if chat.username:
                text += f'\n• @{chat.username} (`{channel}`)'
            else:
                text += f'\n• {chat.title or chat.first_name} (`{channel}`)'
        except Exception:
            text += f'\n• `{channel}`'

    text += f'\n\n**Total:** {len(managed)}'

    if len(text) < 4096:
        await message.reply(text)
    else:
        file = 'Indexed channels.txt'
        with open(file, 'w') as f:
            f.write(text)
        await message.reply_document(file)
        os.remove(file)


@Client.on_message(filters.command('logs') & ADMIN_FILTER)
async def log_file(bot, message):
    try:
        await message.reply_document('TELEGRAM BOT.LOG')
    except Exception as e:
        await message.reply(str(e))


@Client.on_message(filters.command('delete') & ADMIN_FILTER)
async def delete(bot, message):
    reply = await bot.ask(message.from_user.id, "Now Send Me Media Which You Want to delete")
    if reply.media:
        msg = await message.reply("Processing...⏳", quote=True)
    else:
        await message.reply('Send Me Video, File Or Document.', quote=True)
        return

    for file_type in ("document", "video", "audio"):
        media = getattr(reply, file_type, None)
        if media is not None:
            break
    else:
        await msg.edit('This is not supported file format')
        return

    file_id = unpack_new_file_id(media.file_id)
    deleted_count = delete_file_everywhere({'file_id': file_id})
    if deleted_count:
        await msg.edit('File is successfully deleted from database')
    else:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        for char in ('[', ']', '(', ')'):
            file_name = file_name.replace(char, '')
        file_name = ' '.join(filter(lambda x: not x.startswith('@'), file_name.split()))
        deleted_count = delete_file_everywhere({'file_name': file_name, 'file_size': media.file_size}, many=True)
        if deleted_count:
            await msg.edit('File is successfully deleted from database')
        else:
            deleted_count = delete_file_everywhere({'file_name': media.file_name, 'file_size': media.file_size}, many=True)
            if deleted_count:
                await msg.edit('File is successfully deleted from database')
            else:
                await msg.edit('File not found in database')


@Client.on_message(filters.command('deleteall') & ADMIN_FILTER)
async def delete_all_index(bot, message):
    await message.reply_text(
        'This will delete all indexed files.\nDo you want to continue??',
        reply_markup=InlineKeyboardMarkup(
            [[
                InlineKeyboardButton(text="YES", callback_data="autofilter_delete", style=ButtonStyle.DANGER)
            ], [
                InlineKeyboardButton(text="CANCEL", callback_data="close_data", style=ButtonStyle.DANGER)
            ]]
        ),
        quote=True,
    )


@Client.on_callback_query(filters.regex(r'^autofilter_delete'))
async def delete_all_index_confirm(bot, query):
    drop_all_file_collections()
    await query.answer('Piracy Is Crime')
    await query.message.edit('Succesfully Deleted All The Indexed Files.')


def build_group_settings_buttons(settings, grp_id):
    smode = str(settings.get("shortener_mode") or "global").lower()
    smode_badge = {
        "global": "🌐 Global",
        "time": f"⏱ Time ({format_seconds_human(settings.get('verify_expire_seconds', 86400))})",
        "credits": f"💳 Credits ({settings.get('verify_credits', 5)})",
        "link": "🔗 Every File",
        "off": "✘ Off",
    }.get(smode, "🌐 Global")
    return [
        [
            InlineKeyboardButton('Rᴇsᴜʟᴛ Pᴀɢᴇ', callback_data=f'setgs#button#{settings["button"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('Bᴜᴛᴛᴏɴ' if settings["button"] else 'Tᴇxᴛ', callback_data=f'setgs#button#{settings["button"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["button"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Pʀᴏᴛᴇᴄᴛ Cᴏɴᴛᴇɴᴛ', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["file_secure"] else '✘ Oғғ', callback_data=f'setgs#file_secure#{settings["file_secure"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["file_secure"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Iᴍᴅʙ Pᴏsᴛᴇʀ', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["imdb"] else '✘ Oғғ', callback_data=f'setgs#imdb#{settings["imdb"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["imdb"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Sᴘᴇʟʟ Cʜᴇᴄᴋ', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["spell_check"] else '✘ Oғғ', callback_data=f'setgs#spell_check#{settings["spell_check"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["spell_check"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Wᴇʟᴄᴏᴍᴇ Msɢ', callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["welcome"] else '✘ Oғғ', callback_data=f'setgs#welcome#{settings["welcome"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["welcome"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Aᴜᴛᴏ-Dᴇʟᴇᴛᴇ', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('5 Mɪɴs' if settings["auto_delete"] else '✘ Oғғ', callback_data=f'setgs#auto_delete#{settings["auto_delete"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["auto_delete"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Aᴜᴛᴏ-Fɪʟᴛᴇʀ', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["auto_ffilter"] else '✘ Oғғ', callback_data=f'setgs#auto_ffilter#{settings["auto_ffilter"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["auto_ffilter"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Mᴀx Bᴜᴛᴛᴏɴs', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('10' if settings["max_btn"] else f'{MAX_B_TN}', callback_data=f'setgs#max_btn#{settings["max_btn"]}#{grp_id}', style=ButtonStyle.SUCCESS),
        ],
        [
            InlineKeyboardButton('SʜᴏʀᴛLɪɴᴋ', callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton('✔ Oɴ' if settings["is_shortlink"] else '✘ Oғғ', callback_data=f'setgs#is_shortlink#{settings["is_shortlink"]}#{grp_id}', style=ButtonStyle.SUCCESS if settings["is_shortlink"] else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton('Sʜᴏʀᴛᴇɴᴇʀ Mᴏᴅᴇ', callback_data=f'setgs#shortener_mode#{smode}#{grp_id}', style=ButtonStyle.PRIMARY),
            InlineKeyboardButton(smode_badge, callback_data=f'setgs#shortener_mode#{smode}#{grp_id}', style=ButtonStyle.SUCCESS),
        ],
    ]


@Client.on_message(filters.command('settings'))
async def settings(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except Exception:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and userid not in ADMINS
    ):
        return

    settings_data = await get_settings(grp_id)
    if settings_data is not None:
        buttons = build_group_settings_buttons(settings_data, grp_id)
        btn = [[
            InlineKeyboardButton("Oᴘᴇɴ Hᴇʀᴇ ↓", callback_data=f"opnsetgrp#{grp_id}", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("Oᴘᴇɴ Iɴ PM ⇲", callback_data=f"opnsetpm#{grp_id}", style=ButtonStyle.SUCCESS)
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        if chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
            await message.reply_text(
                text="<b>⚙️ ᴅᴏ ʏᴏᴜ ᴡᴀɴᴛ ᴛᴏ ᴏᴘᴇɴ sᴇᴛᴛɪɴɢs ʜᴇʀᴇ ?</b>",
                reply_markup=InlineKeyboardMarkup(btn),
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
            )
        else:
            await message.reply_text(
                text=f"<b>⚙️ Cʜᴀɴɢᴇ Yᴏᴜʀ Sᴇᴛᴛɪɴɢs Fᴏʀ {html_lib.escape(str(title))} As Yᴏᴜʀ Wɪsʜ</b>",
                reply_markup=reply_markup,
                disable_web_page_preview=True,
                parse_mode=enums.ParseMode.HTML,
                reply_to_message_id=message.id
            )


@Client.on_message(filters.command('set_template'))
async def save_template(client, message):
    sts = await message.reply("Checking template")
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply(f"You are anonymous admin. Use /connect {message.chat.id} in PM")
    chat_type = message.chat.type

    if chat_type == enums.ChatType.PRIVATE:
        grpid = await active_connection(str(userid))
        if grpid is not None:
            grp_id = grpid
            try:
                chat = await client.get_chat(grpid)
                title = chat.title
            except Exception:
                await message.reply_text("Make sure I'm present in your group!!", quote=True)
                return
        else:
            await message.reply_text("I'm not connected to any groups!", quote=True)
            return
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grp_id = message.chat.id
        title = message.chat.title
    else:
        return

    st = await client.get_chat_member(grp_id, userid)
    if (
        st.status != enums.ChatMemberStatus.ADMINISTRATOR
        and st.status != enums.ChatMemberStatus.OWNER
        and userid not in ADMINS
    ):
        return

    if len(message.command) < 2:
        return await sts.edit("No Input!!")
    template = message.text.split(" ", 1)[1]
    await save_group_settings(grp_id, 'template', template)
    await sts.edit(f"Successfully changed template for {title} to\n\n{template}")


@Client.on_message((filters.command(["request", "Request"]) | filters.regex("#request") | filters.regex("#Request")) & filters.group)
async def requests(bot, message):
    if REQST_CHANNEL is None:
        return
    if message.reply_to_message:
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.reply_to_message.text
        try:
            if REQST_CHANNEL is not None:
                btn = [[
                    InlineKeyboardButton('View Request', url=f"{message.reply_to_message.link}", style=ButtonStyle.PRIMARY),
                    InlineKeyboardButton('Show Options', callback_data=f'show_option#{reporter}', style=ButtonStyle.DANGER)
                ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('View Request', url=f"{message.reply_to_message.link}", style=ButtonStyle.PRIMARY),
                        InlineKeyboardButton('Show Options', callback_data=f'show_option#{reporter}', style=ButtonStyle.DANGER)
                    ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")

    elif message.text:
        reporter = str(message.from_user.id)
        mention = message.from_user.mention
        success = True
        content = message.text
        keywords = ["#request", "/request", "#Request", "/Request"]
        for keyword in keywords:
            if keyword in content:
                content = content.replace(keyword, "")
        try:
            if REQST_CHANNEL is not None and len(content) >= 3:
                btn = [[
                    InlineKeyboardButton('View Request', url=f"{message.link}", style=ButtonStyle.PRIMARY),
                    InlineKeyboardButton('Show Options', callback_data=f'show_option#{reporter}', style=ButtonStyle.DANGER)
                ]]
                reported_post = await bot.send_message(chat_id=REQST_CHANNEL, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
                success = True
            elif len(content) >= 3:
                for admin in ADMINS:
                    btn = [[
                        InlineKeyboardButton('View Request', url=f"{message.link}", style=ButtonStyle.PRIMARY),
                        InlineKeyboardButton('Show Options', callback_data=f'show_option#{reporter}', style=ButtonStyle.DANGER)
                    ]]
                    reported_post = await bot.send_message(chat_id=admin, text=f"<b>𝖱𝖾𝗉𝗈𝗋𝗍𝖾𝗋 : {mention} ({reporter})\n\n𝖬𝖾𝗌𝗌𝖺𝗀𝖾 : {content}</b>", reply_markup=InlineKeyboardMarkup(btn))
                    success = True
            else:
                if len(content) < 3:
                    await message.reply_text("<b>You must type about your request [Minimum 3 Characters]. Requests can't be empty.</b>")
            if len(content) < 3:
                success = False
        except Exception as e:
            await message.reply_text(f"Error: {e}")
    else:
        success = False

    if success:
        link = await bot.create_chat_invite_link(int(REQST_CHANNEL))
        btn = [[
            InlineKeyboardButton('Join Channel', url=link.invite_link, style=ButtonStyle.SUCCESS),
            InlineKeyboardButton('View Request', url=f"{reported_post.link}", style=ButtonStyle.PRIMARY)
        ]]
        await message.reply_text("<b>Your request has been added! Please wait for some time.\n\nJoin Channel First & View Request</b>", reply_markup=InlineKeyboardMarkup(btn))


@Client.on_message(filters.command("send") & ADMIN_FILTER)
async def send_msg(bot, message):
    if message.reply_to_message:
        target_id = message.text.split(" ", 1)[1]
        out = "Users Saved In DB Are:\n\n"
        success = False
        try:
            user = await bot.get_users(target_id)
            users = await db.get_all_users()
            async for usr in users:
                out += f"{usr['id']}\n"
            if str(user.id) in str(out):
                await message.reply_to_message.copy(int(user.id))
                success = True
            if success:
                await message.reply_text(f"<b>Your message has been successfully send to {user.mention}.</b>")
            else:
                await message.reply_text("<b>This user didn't started this bot yet !</b>")
        except Exception as e:
            await message.reply_text(f"<b>Error: {e}</b>")
    else:
        await message.reply_text("<b>Use this command as a reply to any message using the target chat id. For eg: /send userid</b>")


@Client.on_message(filters.command("deletefiles") & ADMIN_FILTER)
async def deletemultiplefiles(bot, message):
    chat_type = message.chat.type
    if chat_type != enums.ChatType.PRIVATE:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, This command won't work in groups. It only works on my PM !</b>")
    try:
        keyword = message.text.split(" ", 1)[1]
    except Exception:
        return await message.reply_text(f"<b>Hey {message.from_user.mention}, Give me a keyword along with the command to delete files.</b>")
    k = await bot.send_message(chat_id=message.chat.id, text=f"<b>Fetching Files for your query {keyword} on DB... Please wait...</b>")
    files, total = await get_bad_files(keyword)
    await k.delete()
    btn = [[
        InlineKeyboardButton("Yes, Continue !", callback_data=f"killfilesdq#{keyword}", style=ButtonStyle.DANGER)
    ], [
        InlineKeyboardButton("No, Abort operation !", callback_data="close_data", style=ButtonStyle.DANGER)
    ]]
    await message.reply_text(
        text=f"<b>Found {total} files for your query {keyword} !\n\nDo you want to delete?</b>",
        reply_markup=InlineKeyboardMarkup(btn),
        parse_mode=enums.ParseMode.HTML
    )


@Client.on_message(filters.command("shortlink"))
async def shortlink(bot, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("You are anonymous admin. Turn off anonymous admin and try again this command")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text(
            f"<b>Hey {message.from_user.mention}, to manage global shorteners and Shortener Modes (Time Expiry / Credits) in PM, use:\n"
            f"👉 <code>/shortmode</code> or <code>/panel</code>\n\n"
            f"<u>To connect a group-specific shortener:</u>\n"
            f"Send in your group:\n<code>/shortlink kpslink.in YOUR_API_KEY</code>\n"
            f"<code>/shortlink mode time 12h</code>\n"
            f"<code>/shortlink mode credits 5</code></b>"
        )
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
        title = message.chat.title
    else:
        return
    data = message.text
    userid = message.from_user.id
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return await message.reply_text("<b>You don't have access to use this command!\n\nAdd Me to Your Own Group as Admin and Try This Command</b>")

    parts = data.split()
    if len(parts) >= 3 and parts[1].lower() == "mode":
        chosen = parts[2].lower()
        if chosen in ("time", "duration", "expire"):
            secs = parse_duration_to_seconds(parts[3], default=86400) if len(parts) >= 4 else 86400
            await save_group_settings(grpid, 'shortener_mode', 'time')
            await save_group_settings(grpid, 'verify_expire_seconds', secs)
            return await message.reply_text(f"<b>✅ Shortener Mode for {html_lib.escape(title)} set to <u>Time Expiry Mode</u> ({format_seconds_human(secs)}).</b>")
        if chosen in ("credits", "credit"):
            creds = int(parts[3]) if (len(parts) >= 4 and parts[3].isdigit()) else 5
            await save_group_settings(grpid, 'shortener_mode', 'credits')
            await save_group_settings(grpid, 'verify_credits', max(1, creds))
            return await message.reply_text(f"<b>✅ Shortener Mode for {html_lib.escape(title)} set to <u>Credits Mode</u> ({max(1, creds)} credits per verification).</b>")
        if chosen in ("link", "every"):
            await save_group_settings(grpid, 'shortener_mode', 'link')
            return await message.reply_text(f"<b>✅ Shortener Mode for {html_lib.escape(title)} set to <u>Every-File Shortlink Mode</u>.</b>")
        if chosen in ("off", "disable"):
            await save_group_settings(grpid, 'shortener_mode', 'off')
            await save_group_settings(grpid, 'is_shortlink', False)
            return await message.reply_text(f"<b>✅ Shortener disabled for {html_lib.escape(title)}.</b>")
        if chosen == "global":
            await save_group_settings(grpid, 'shortener_mode', 'global')
            return await message.reply_text(f"<b>✅ Shortener Mode for {html_lib.escape(title)} synced to <u>Global Panel Mode</u>.</b>")

    try:
        command, shortlink_url, api = data.split(" ", 2)
        api = api.strip()
    except Exception:
        return await message.reply_text(
            "<b>Command Incomplete :(\n\n"
            "Format: <code>/shortlink kpslink.in YOUR_API_KEY</code>\n"
            "Set Time Mode: <code>/shortlink mode time 12h</code>\n"
            "Set Credits Mode: <code>/shortlink mode credits 5</code></b>"
        )
    reply = await message.reply_text("<b>Please Wait...</b>")
    shortlink_url = re.sub(r"https?://?", "", shortlink_url)
    shortlink_url = re.sub(r"[:/]", "", shortlink_url)
    await save_group_settings(grpid, 'shortlink', shortlink_url)
    await save_group_settings(grpid, 'shortlink_api', api)
    await save_group_settings(grpid, 'is_shortlink', True)
    await reply.edit_text(
        f"<b>✅ Successfully added shortlink API for {html_lib.escape(title)}.\n\n"
        f"🌐 Website: <code>{shortlink_url}</code>\n"
        f"🔑 API: <code>{api}</code>\n\n"
        f"💡 Tip: Use <code>/shortlink mode time 12h</code> or <code>/shortlink mode credits 5</code> to configure verification rewards!</b>"
    )


@Client.on_message(filters.command("setshortlinkoff"))
async def offshortlink(bot, message):
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text("I will Work Only in group")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
    else:
        return
    userid = message.from_user.id
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return await message.reply_text("<b>You don't have access to use this command!</b>")
    await save_group_settings(grpid, 'is_shortlink', False)
    await save_group_settings(grpid, 'shortener_mode', 'off')
    return await message.reply_text("✅ Successfully disabled shortlink")


@Client.on_message(filters.command("setshortlinkon"))
async def onshortlink(bot, message):
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text("I will Work Only in group")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
    else:
        return
    userid = message.from_user.id
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return await message.reply_text("<b>You don't have access to use this command!</b>")
    settings_data = await get_settings(grpid)
    pool = await db.get_shortener_pool()
    if not settings_data['shortlink'] and not pool and not SHORTLINK_URL:
        return await message.reply_text("**First Add Your Shortlink Url And Api By /shortlink Command (or /shortmode), Then Turn Me On.**")
    await save_group_settings(grpid, 'is_shortlink', True)
    if settings_data.get('shortener_mode') == 'off':
        await save_group_settings(grpid, 'shortener_mode', 'global')
    return await message.reply_text("✅ Successfully enabled shortlink")


@Client.on_message(filters.command("shortlink_info"))
async def showshortlink(bot, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("You are anonymous admin. Turn off anonymous admin and try again this command")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        scfg = await db.get_shortener_config()
        return await message.reply_text(
            f"<b>🔀 Global Shortener Info</b>\n\n"
            f"• <b>Mode:</b> <code>{scfg['mode'].upper()}</code>\n"
            f"• <b>Expire Duration:</b> <code>{scfg['expire_human']}</code>\n"
            f"• <b>Credits per Verify:</b> <code>{scfg['credits_per_verify']}</code>\n"
            f"• <b>Pool Providers:</b> <code>{scfg['pool_count']}</code>\n\n"
            f"Admins can manage shortener modes with <code>/shortmode</code> or <code>/panel</code>."
        )
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
    else:
        return
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return await message.reply_text("<b>Tʜɪs ᴄᴏᴍᴍᴀɴᴅ Wᴏʀᴋs Oɴʟʏ Fᴏʀ ᴛʜɪs Gʀᴏᴜᴘ Oᴡɴᴇʀ/Aᴅᴍɪɴ</b>")
    settings_data = await get_settings(grpid)
    su = settings_data.get('shortlink') or "Using Global Pool"
    sa = settings_data.get('shortlink_api') or "Global Pool"
    st = settings_data.get('tutorial') or "Default"
    sm = settings_data.get('shortener_mode') or "global"
    exp = format_seconds_human(settings_data.get('verify_expire_seconds', 86400))
    crd = settings_data.get('verify_credits', 5)
    return await message.reply_text(
        f"<b>🔀 Group Shortener Configuration</b>\n\n"
        f"🌐 <b>Website:</b> <code>{su}</code>\n"
        f"🔑 <b>API:</b> <code>{sa}</code>\n"
        f"🎬 <b>Tutorial:</b> <code>{st}</code>\n"
        f"🎛 <b>Mode:</b> <code>{sm.upper()}</code> (Time: <code>{exp}</code> | Credits: <code>{crd}</code>)"
    )


@Client.on_message(filters.command("set_tutorial"))
async def settutorial(bot, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("You are anonymous admin. Turn off anonymous admin and try again this command")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        if userid in ADMINS and len(message.command) == 2:
            await db.update_shortener_config(tutorial_url=message.command[1])
            return await message.reply_text(f"<b>✅ Global tutorial link updated to <code>{html_lib.escape(message.command[1])}</code></b>")
        return await message.reply_text("Use `/set_tutorial URL` in your group (or as bot admin in PM).")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
        title = message.chat.title
    else:
        return
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return
    if len(message.command) == 1:
        return await message.reply("<b>Give me a tutorial link along with this command\n\nCommand Usage: /set_tutorial your tutorial link</b>")
    elif len(message.command) == 2:
        reply = await message.reply_text("<b>Please Wait...</b>")
        tutorial = message.command[1]
        await save_group_settings(grpid, 'tutorial', tutorial)
        await save_group_settings(grpid, 'is_tutorial', True)
        await reply.edit_text(f"<b>Successfully Added Tutorial\n\nHere is your tutorial link for your group {title} - <code>{tutorial}</code></b>")
    else:
        return await message.reply("<b>You entered Incorrect Format\n\nFormat: /set_tutorial your tutorial link</b>")


@Client.on_message(filters.command("remove_tutorial"))
async def removetutorial(bot, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("You are anonymous admin. Turn off anonymous admin and try again this command")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text("This Command Work Only in group\n\nTry it in your own group")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
    else:
        return
    user = await bot.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return
    reply = await message.reply_text("<b>Please Wait...</b>")
    await save_group_settings(grpid, 'tutorial', "")
    await save_group_settings(grpid, 'is_tutorial', False)
    await reply.edit_text("<b>Successfully Removed Your Tutorial Link!!!</b>")


# ----------------------------------------------------------------------
# Enhanced /auto Command & Interactive Series + Movie Auto-Post Manager
# ----------------------------------------------------------------------
async def _build_auto_menu(client):
    settings_data = await db.get_auto_post_settings()
    enabled = settings_data["auto_index"]
    channel = settings_data["post_channel_id"]
    min_q = settings_data["min_qualities"]
    series_on = settings_data["series_enabled"]
    movies_on = settings_data["movies_enabled"]

    channel_label = f"<code>{channel}</code>" if channel else "<code>Not configured</code>"
    if channel and client:
        try:
            chat = await client.get_chat(int(channel))
            channel_label = f"<b>{html_lib.escape(chat.title or str(channel))}</b> (<code>{channel}</code>)"
        except Exception:
            pass

    text = (
        f"<b>🎬 MoviesZoneFlix • Auto Index & Auto Post (/auto)</b>\n\n"
        f"<blockquote>📡 <b>Status:</b> <b>{'🟢 Enabled' if enabled else '🔴 Disabled'}</b>\n"
        f"📢 <b>Post Destination:</b> {channel_label}\n"
        f"📺 <b>Series Auto-Post:</b> <b>{'🟢 ON' if series_on else '🔴 OFF'}</b> (Every 1 Episode)\n"
        f"🎞 <b>Movie Auto-Post:</b> <b>{'🟢 ON' if movies_on else '🔴 OFF'}</b>\n"
        f"🎯 <b>Quality Trigger:</b> <code>{min_q} Qualities</code> (e.g. 480p,720p and 1080p)</blockquote>\n\n"
        f"<b>Series Post Format in Destination Channel:</b>\n"
        f"<pre>Series : bigg boss\nSeason : 10\nEPISODE : 1\nQUALITY : 480p,720p and 1080p\nLanguage : Telugu</pre>\n"
        f"<i>(Automatically switches to <code>Languages : Telugu,Tamil,Hindi</code> when multiple languages are detected!)</i>\n\n"
        f"<b>Commands:</b>\n"
        f"• <code>/auto on</code> — Set destination post channel & enable\n"
        f"• <code>/auto off</code> — Disable auto-posting\n"
        f"• <code>/auto test FILENAME_OR_CAPTION</code> — Test parser output\n"
        f"• <code>/auto reset</code> — Reset posted history cache"
    )
    markup = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("▶️ Enable / Set Channel", callback_data="mzf_auto:enable", style=ButtonStyle.SUCCESS),
            InlineKeyboardButton("⏸ Disable", callback_data="mzf_auto:disable", style=ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton(f"📺 Series: {'🟢 ON' if series_on else '🔴 OFF'}", callback_data="mzf_auto:toggle_series", style=ButtonStyle.SUCCESS if series_on else ButtonStyle.DANGER),
            InlineKeyboardButton(f"🎬 Movies: {'🟢 ON' if movies_on else '🔴 OFF'}", callback_data="mzf_auto:toggle_movies", style=ButtonStyle.SUCCESS if movies_on else ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton(f"🎯 Trigger: {min_q} Qualities", callback_data="mzf_auto:cycle_q", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🧹 Reset Post Cache", callback_data="mzf_auto:reset_cache", style=ButtonStyle.DANGER),
        ],
        [
            InlineKeyboardButton("🔄 Refresh", callback_data="mzf_auto:menu", style=ButtonStyle.PRIMARY),
            InlineKeyboardButton("🎛 Control Panel", callback_data="tgbox_panel:home", style=ButtonStyle.PRIMARY),
        ],
    ])
    return text, markup


@Client.on_message(filters.command("auto") & ADMIN_FILTER)
async def auto_index_command(client, message):
    """Persistent admin wizard for caption/filename-driven Movie & Series automatic posting."""
    args = message.command[1:] if getattr(message, "command", None) else []
    action = args[0].lower() if args else "menu"

    if action in {"menu", "status", "help"}:
        text, markup = await _build_auto_menu(client)
        return await message.reply_text(text, reply_markup=markup, disable_web_page_preview=True)

    if action == "off":
        await db.set_auto_index_enabled(False)
        text, markup = await _build_auto_menu(client)
        return await message.reply_text("⏸️ <b>MoviesZoneFlix auto-indexing & auto-posting disabled.</b>\n\n" + text, reply_markup=markup)

    if action in {"reset", "clear"}:
        res = await db.config.delete_many({"_id": {"$regex": r"^auto_(?:post|movie):"}})
        return await message.reply_text(f"🧹 <b>Cleared {res.deleted_count} auto-post aggregation record(s).</b> Episodes and movies can now be posted fresh.")

    if action == "test":
        sample = message.text.split(None, 2)[2].strip() if len(message.text.split(None, 2)) > 2 else "BIGG BOSS SEASON 10 EPISODE 1 480p 720p 1080p Telugu,Tamil.mkv"
        parsed = parse_movie_caption(sample)
        if not parsed:
            return await message.reply_text("❌ Could not parse title from that sample.")
        preview = format_auto_post_message(parsed)
        return await message.reply_text(
            f"<b>🧪 Auto-Post Parser Test</b>\n\n"
            f"<b>Input:</b> <code>{html_lib.escape(sample)}</code>\n"
            f"<b>Detected Type:</b> <code>{'Series Episode' if parsed.get('is_series') else 'Movie'}</code>\n"
            f"<b>Qualities:</b> <code>{', '.join(parsed.get('qualities', [])) or 'None'}</code>\n"
            f"<b>Languages:</b> <code>{', '.join(parsed.get('languages', [])) or 'None'}</code>\n\n"
            f"<b>Destination Channel Post Preview:</b>\n{preview}"
        )

    if action == "on":
        if len(args) >= 2:
            return await _setup_auto_destination(client, message, args[1])
        await db.config.update_one(
            {"_id": "file_channels"},
            {"$set": {"auto_setup_user": int(message.from_user.id), "auto_setup_pending": True}},
            upsert=True,
        )
        return await message.reply_text(
            "📡 <b>Send the destination post channel ID, @username, channel link, or forward a message from the destination channel.</b>\n\n"
            "Make sure the bot is an administrator in that channel. Send /cancel to abort."
        )

    return await message.reply_text("Use <code>/auto</code>, <code>/auto on</code>, <code>/auto off</code>, <code>/auto test TEXT</code>, or <code>/auto reset</code>.")


async def _setup_auto_destination(client, message, raw_input, forwarded_chat=None):
    if forwarded_chat:
        channel_id = int(forwarded_chat.id)
    else:
        val = (raw_input or "").strip()
        m_link = re.match(r"^(?:https?://)?(?:t\.me|telegram\.me)/(?:c/)?([A-Za-z0-9_]+|-?\d+)", val, re.I)
        if m_link:
            val = m_link.group(1)
        norm = normalize_channel_id(val)
        if norm is not None:
            channel_id = int(norm)
        elif val.startswith("@") or re.match(r"^[A-Za-z0-9_]{4,}$", val):
            channel_id = "@" + val.lstrip("@")
        else:
            return await message.reply_text("❌ Invalid channel ID. Forward a message from the destination channel or send its numeric ID (e.g. <code>-100123456789</code>) or <code>@username</code>.")

    try:
        chat = await client.get_chat(channel_id)
        channel_id = int(chat.id)
        member = await client.get_chat_member(channel_id, (await client.get_me()).id)
        status = str(getattr(member, "status", "")).lower()
        if status.endswith("left") or status.endswith("banned"):
            raise ValueError("Bot is not a member of that channel")
        if status.endswith("member"):
            raise ValueError("Bot must be an administrator in the destination channel to publish posts")
    except Exception as exc:
        return await message.reply_text(f"❌ Cannot access that channel. Add the bot as an administrator and check the ID.\n<code>{html_lib.escape(str(exc))}</code>")

    await db.config.update_one(
        {"_id": "file_channels"},
        {
            "$set": {"post_channel_id": channel_id, "auto_index": True},
            "$unset": {"auto_setup_pending": "", "auto_setup_user": ""},
        },
        upsert=True,
    )
    db._cache_invalidate("config:file_channels")
    return await message.reply_text(
        f"✅ <b>Auto-indexing & Auto-Posting enabled!</b>\n\n"
        f"📢 Destination: <b>{html_lib.escape(chat.title or str(channel_id))}</b> (<code>{channel_id}</code>)\n\n"
        f"• <b>Series:</b> Every 1 episode with 3 qualities (e.g. <code>480p,720p and 1080p</code>) is automatically posted with Series, Season, Episode, Quality, and Language/Languages.\n"
        f"• <b>Movies:</b> Posted automatically when 3 qualities are detected."
    )


@Client.on_callback_query(filters.regex(r"^(?:auto_(?:enable|disable)|mzf_auto:.+)$") & ADMIN_FILTER, group=-1)
async def auto_index_buttons(client, query):
    data = query.data
    if data in ("auto_disable", "mzf_auto:disable"):
        await db.set_auto_index_enabled(False)
        text, markup = await _build_auto_menu(client)
        await query.answer("Auto-posting disabled.")
        return await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)

    if data in ("auto_enable", "mzf_auto:enable"):
        await db.config.update_one(
            {"_id": "file_channels"},
            {"$set": {"auto_setup_user": int(query.from_user.id), "auto_setup_pending": True}},
            upsert=True,
        )
        await query.answer("Send destination channel ID or forward a message from it.")
        return await query.message.edit_text(
            "📡 <b>Send the destination post channel ID, @username, or forward a message from the destination channel.</b>\n\n"
            "Make sure the bot is an administrator in that channel. Send /cancel to abort."
        )

    action = data.split(":", 1)[1] if ":" in data else "menu"
    settings_data = await db.get_auto_post_settings()

    if action == "toggle_series":
        new_val = not settings_data["series_enabled"]
        await db.update_auto_post_settings(series_enabled=new_val)
        await query.answer(f"Series Auto-Post {'ENABLED' if new_val else 'DISABLED'}.")
    elif action == "toggle_movies":
        new_val = not settings_data["movies_enabled"]
        await db.update_auto_post_settings(movies_enabled=new_val)
        await query.answer(f"Movie Auto-Post {'ENABLED' if new_val else 'DISABLED'}.")
    elif action == "cycle_q":
        cur_q = settings_data["min_qualities"]
        next_q = {1: 2, 2: 3, 3: 4, 4: 1}.get(cur_q, 3)
        await db.update_auto_post_settings(min_qualities=next_q)
        await query.answer(f"Quality trigger set to {next_q} qualities.")
    elif action == "reset_cache":
        res = await db.config.delete_many({"_id": {"$regex": r"^auto_(?:post|movie):"}})
        await query.answer(f"Cleared {res.deleted_count} cached episode/movie entries!", show_alert=True)

    text, markup = await _build_auto_menu(client)
    try:
        await query.message.edit_text(text, reply_markup=markup, disable_web_page_preview=True)
    except Exception:
        pass


@Client.on_message(filters.private & ~filters.command(["auto", "cancel"]) & ADMIN_FILTER, group=3)
async def auto_index_channel_setup(client, message):
    config = await db.config.find_one({"_id": "file_channels"}) or {}
    if not config.get("auto_setup_pending") or config.get("auto_setup_user") != int(message.from_user.id):
        return
    value = (message.text or message.caption or "").strip()
    if value.startswith("/") and value.split()[0].split("@")[0].lower() != "/cancel":
        return
    if value.lower() in ("/cancel", "cancel"):
        await db.config.update_one({"_id": "file_channels"}, {"$unset": {"auto_setup_pending": "", "auto_setup_user": ""}})
        db._cache_invalidate("config:file_channels")
        return await message.reply_text("Setup cancelled.")
    f_chat = getattr(message, "forward_from_chat", None)
    return await _setup_auto_destination(client, message, value, forwarded_chat=f_chat)


@Client.on_message(filters.command("restart") & ADMIN_FILTER)
async def stop_button(bot, message):
    msg = await bot.send_message(text="**🔄 𝙿𝚁𝙾𝙲𝙴𝚂𝚂𝙴𝚂 𝚂𝚃𝙾𝙿𝙴𝙳. 𝙱𝙾𝚃 𝙸𝚂 𝚁𝙴𝚂𝚃𝙰𝚁𝚃𝙸𝙽𝙶...**", chat_id=message.chat.id)
    await asyncio.sleep(1)
    await msg.edit("**✅️ 𝙱𝙾𝚃 𝙸𝚂 𝚁𝙴𝚂𝚃𝙰𝚁𝚃𝙴𝙳. 𝙽𝙾𝚆 𝚈𝙾𝚄 𝙲𝙰𝙽 𝚄𝚂𝙴 𝙼𝙴**")
    os.execl(sys.executable, sys.executable, *sys.argv)


@Client.on_message(filters.command("nofsub"))
async def nofsub(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("<b>You are anonymous admin. Turn off anonymous admin and try again this command</b>")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text("<b>This Command Work Only in group\n\nTry it in your own group</b>")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
        title = message.chat.title
    else:
        return
    user = await client.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return
    await save_group_settings(grpid, 'fsub', None)
    await message.reply_text(f"<b>Successfully removed force subscribe from {title}.</b>")


@Client.on_message(filters.command('fsub'))
async def fsub(client, message):
    userid = message.from_user.id if message.from_user else None
    if not userid:
        return await message.reply("<b>You are anonymous admin. Turn off anonymous admin and try again this command</b>")
    chat_type = message.chat.type
    if chat_type == enums.ChatType.PRIVATE:
        return await message.reply_text("<b>This Command Work Only in group\n\nTry it in your own group</b>")
    elif chat_type in [enums.ChatType.GROUP, enums.ChatType.SUPERGROUP]:
        grpid = message.chat.id
        title = message.chat.title
    else:
        return
    user = await client.get_chat_member(grpid, userid)
    if user.status != enums.ChatMemberStatus.ADMINISTRATOR and user.status != enums.ChatMemberStatus.OWNER and userid not in ADMINS:
        return
    try:
        ids = message.text.split(" ", 1)[1]
        fsub_ids = [int(id) for id in ids.split()]
    except IndexError:
        return await message.reply_text("<b>Command Incomplete!\n\nAdd Multiple Channel By Seperate Space. Like: /fsub id1 id2 id3</b>")
    except ValueError:
        return await message.reply_text('<b>Make Sure Ids are Integer.</b>')
    channels = "Channels:\n"
    for id in fsub_ids:
        try:
            chat = await client.get_chat(id)
        except Exception as e:
            return await message.reply_text(f"<b>{id} is invalid!\nMake sure this bot admin in that channel.\n\nError - {e}</b>")
        if chat.type not in (enums.ChatType.CHANNEL, enums.ChatType.GROUP, enums.ChatType.SUPERGROUP):
            return await message.reply_text(f"<b>{id} is not a channel, group, or supergroup.</b>")
        channels += f'{chat.title} ({chat.type.value})\n'
    await save_group_settings(grpid, 'fsub', fsub_ids)
    await message.reply_text(f"<b>Successfully set force-subscribe destinations for {title} to\n\n{channels}\n\nYou can remove it by /nofsub.</b>")


@Client.on_message(filters.command("add_premium"))
async def give_premium_cmd_handler(client, message):
    if not PREMIUM_AND_REFERAL_MODE:
        return
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.delete()
        return
    if len(message.command) == 3:
        target_uid = int(message.command[1])
        t_str = message.command[2]
        seconds = await get_seconds(t_str)
        if seconds > 0:
            expiry_time = datetime.datetime.now() + datetime.timedelta(seconds=seconds)
            user_data = {"id": target_uid, "expiry_time": expiry_time}
            await db.update_user(user_data)
            await message.reply_text("✅ Premium access added to the user.")
            await client.send_message(
                chat_id=target_uid,
                text=f"<b>💎 ᴘʀᴇᴍɪᴜᴍ ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ ꜰᴏʀ {t_str} ᴇɴᴊᴏʏ 😀</b>",
            )
        else:
            await message.reply_text("Invalid time format. Please use '1day', '1hour', '1min', '1month', or '1year'")
    else:
        await message.reply_text("<b>Usage: /add_premium user_id time \n\nExample: /add_premium 1252789 10day</b>")


@Client.on_message(filters.command("remove_premium"))
async def remove_premium_cmd_handler(client, message):
    if not PREMIUM_AND_REFERAL_MODE:
        return
    user_id = message.from_user.id
    if user_id not in ADMINS:
        await message.delete()
        return
    if len(message.command) == 2:
        target_uid = int(message.command[1])
        user_data = {"id": target_uid, "expiry_time": None}
        await db.update_user(user_data)
        await message.reply_text("Premium access removed from the user.")
        await client.send_message(
            chat_id=target_uid,
            text="<b>Premium removed by admins.\n\nContact Admin if this is a mistake:\n👮 Admin : {}</b>".format(OWNER_LNK),
        )
    else:
        await message.reply_text("Usage: /remove_premium user_id")


@Client.on_message(filters.command("plan"))
async def plans_cmd_handler(client, message):
    if not PREMIUM_AND_REFERAL_MODE:
        return
    btn = [
        [InlineKeyboardButton("ꜱᴇɴᴅ ᴘᴀʏᴍᴇɴᴛ ʀᴇᴄᴇɪᴘᴛ 🧾", url=OWNER_LNK, style=ButtonStyle.PRIMARY)],
        [InlineKeyboardButton("⚠️ ᴄʟᴏsᴇ / ᴅᴇʟᴇᴛᴇ ⚠️", callback_data="close_data", style=ButtonStyle.DANGER)]
    ]
    reply_markup = InlineKeyboardMarkup(btn)
    plan_cfg = await db.config.find_one({"_id": "panel_plan_settings"}) or {}
    if not plan_cfg.get("enabled", True):
        return await message.reply_text("⚠️ Premium plans are currently disabled by the administrator.")
    payment_qr = plan_cfg.get("payment_qr", PAYMENT_QR)
    payment_text = plan_cfg.get("payment_text", PAYMENT_TEXT)
    upi_id = plan_cfg.get("upi_id")
    if upi_id:
        payment_text = re.sub(r"(<b>UPI ID:</b>\s*<code>).*?(</code>)", lambda m: m.group(1) + upi_id + m.group(2), payment_text, flags=re.I)
    await message.reply_photo(
        photo=payment_qr,
        caption=payment_text,
        reply_markup=reply_markup
    )


@Client.on_message(filters.command(["myplan", "mycredits", "status"]))
async def check_plans_cmd(client, message):
    user_id = message.from_user.id
    v_state = await db.get_user_verify_state(user_id)
    scfg = await db.get_shortener_config()
    now = datetime.datetime.now()
    v_until = v_state.get("verified_until")
    v_rem = format_seconds_human((v_until - now).total_seconds()) if (isinstance(v_until, datetime.datetime) and v_until > now) else "Expired / Not Verified"
    v_creds = v_state.get("verify_credits", 0)

    verify_summary = (
        f"\n\n<blockquote>🔀 <b>Shortener Verification Status</b>\n"
        f"• <b>Active Mode:</b> <code>{scfg['mode'].upper()}</code>\n"
        f"• <b>Time Pass Remaining:</b> <code>{v_rem}</code>\n"
        f"• <b>Available Credits:</b> <code>{v_creds} Credits</code></blockquote>"
    )

    if await db.has_premium_access(user_id):
        remaining_time = await db.check_remaining_uasge(user_id)
        expiry_time = remaining_time + datetime.datetime.now()
        await message.reply_text(
            f"<b>💎 Your Premium Plan Details</b>\n\n"
            f"⏳ <b>Remaining Time:</b> <code>{remaining_time}</code>\n"
            f"📅 <b>Expiry Time:</b> <code>{expiry_time.strftime('%Y-%m-%d %H:%M:%S')}</code>"
            f"{verify_summary}"
        )
    else:
        btn = [
            [InlineKeyboardButton("ɢᴇᴛ ғʀᴇᴇ ᴛʀɪᴀʟ ғᴏʀ 𝟻 ᴍɪɴᴜᴛᴇꜱ ☺️", callback_data="get_trail", style=ButtonStyle.SUCCESS)],
            [InlineKeyboardButton("💎 ʙᴜʏ sᴜʙsᴄʀɪᴘᴛɪᴏɴ : ʀᴇᴍᴏᴠᴇ ᴀᴅs", callback_data="buy_premium", style=ButtonStyle.PRIMARY)],
            [InlineKeyboardButton("⚠️ ᴄʟᴏsᴇ / ᴅᴇʟᴇᴛᴇ ⚠️", callback_data="close_data", style=ButtonStyle.DANGER)]
        ]
        reply_markup = InlineKeyboardMarkup(btn)
        await message.reply_text(
            f"<b>😢 You Don't Have Any Active Premium Subscription.</b>\n"
            f"Check out our Premium plans with /plan.{verify_summary}",
            reply_markup=reply_markup
        )


@Client.on_message(filters.command("totalrequests") & filters.private & ADMIN_FILTER)
async def total_requests(client, message):
    if join_db().isActive():
        total = await join_db().get_all_users_count()
        await message.reply_text(
            text=f"Total Requests: {total}",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )


@Client.on_message(filters.command("purgerequests") & filters.private & ADMIN_FILTER)
async def purge_requests(client, message):
    if join_db().isActive():
        await join_db().delete_all_users()
        await message.reply_text(
            text="Purged All Requests.",
            parse_mode=enums.ParseMode.MARKDOWN,
            disable_web_page_preview=True
        )
