# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

import logging, re, asyncio
from utils import temp
from info import ADMINS
from plugins.admin_filter import ADMIN_FILTER
from pyrogram import Client, filters, enums
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.errors.exceptions.bad_request_400 import ChannelInvalid, ChatAdminRequired, UsernameInvalid, UsernameNotModified
from info import INDEX_REQ_CHANNEL as LOG_CHANNEL
from database.ia_filterdb import save_file, save_files_batch
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
lock = asyncio.Lock()

@Client.on_callback_query(filters.regex(r'^index'))
async def index_files(bot, query):
    if query.data.startswith('index_cancel'):
        if query.from_user.id not in ADMINS:
            return await query.answer("Only bot admins can cancel indexing.", show_alert=True)
        temp.CANCEL = True
        return await query.answer("Cancellation requested…")
    if query.from_user.id not in ADMINS:
        return await query.answer("Admin access only.", show_alert=True)
    try:
        _, raju, chat, lst_msg_id, from_user = query.data.split("#")
    except ValueError:
        return await query.answer("Invalid indexing request.", show_alert=True)
    if raju == 'reject':
        await query.message.delete()
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been decliened by our moderators.',
            reply_to_message_id=int(lst_msg_id)
        )
        return

    if lock.locked():
        return await query.answer('Wait until previous process complete.', show_alert=True)
    msg = query.message

    await query.answer('Processing...⏳', show_alert=True)
    if int(from_user) not in ADMINS:
        await bot.send_message(
            int(from_user),
            f'Your Submission for indexing {chat} has been accepted by our moderators and will be added soon.',
            reply_to_message_id=int(lst_msg_id)
        )
    await msg.edit(
        "Starting Indexing",
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton('Cancel', callback_data='index_cancel')]]
        )
    )
    try:
        chat = int(chat)
    except:
        chat = chat
    await index_files_to_db(int(lst_msg_id), chat, msg, bot)


@Client.on_message(filters.private & filters.command('index'))
async def send_for_index(bot, message):
    vj = await bot.ask(message.chat.id, "**Now Send Me Your Channel Last Post Link Or Forward A Last Message From Your Index Channel.\n\nAnd You Can Set Skip Number By - /setskip yourskipnumber**")
    if vj.forward_from_chat and vj.forward_from_chat.type == enums.ChatType.CHANNEL:
        last_msg_id = vj.forward_from_message_id
        chat_id = vj.forward_from_chat.username or vj.forward_from_chat.id
    elif vj.text:
        regex = re.compile(r"(https://)?(t\.me/|telegram\.me/|telegram\.dog/)(c/)?(\d+|[a-zA-Z_0-9]+)/(\d+)$")
        match = regex.match(vj.text)
        if not match:
            return await vj.reply('Invalid link\n\nTry again by /index')
        chat_id = match.group(4)
        last_msg_id = int(match.group(5))
        if chat_id.isnumeric():
            chat_id  = int(("-100" + chat_id))
    else:
        return
    try:
        await bot.get_chat(chat_id)
    except ChannelInvalid:
        return await vj.reply('This may be a private channel / group. Make me an admin over there to index the files.')
    except (UsernameInvalid, UsernameNotModified):
        return await vj.reply('Invalid Link specified.')
    except Exception as e:
        logger.exception(e)
        return await vj.reply(f'Errors - {e}')
    try:
        k = await bot.get_messages(chat_id, last_msg_id)
    except:
        return await message.reply('Make Sure That Iam An Admin In The Channel, if channel is private')
    if k.empty:
        return await message.reply('This may be group and iam not a admin of the group.')

    if message.from_user.id in ADMINS:
        buttons = [[
            InlineKeyboardButton('Yes', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
        ],[
            InlineKeyboardButton('close', callback_data='close_data')
        ]]
        reply_markup = InlineKeyboardMarkup(buttons)
        return await message.reply(
            f'Do you Want To Index This Channel/ Group ?\n\nChat ID/ Username: <code>{chat_id}</code>\nLast Message ID: <code>{last_msg_id}</code>',
            reply_markup=reply_markup
        )

    if type(chat_id) is int:
        try:
            link = (await bot.create_chat_invite_link(chat_id)).invite_link
        except ChatAdminRequired:
            return await message.reply('Make sure iam an admin in the chat and have permission to invite users.')
    else:
        link = f"@{message.forward_from_chat.username}"
    buttons = [[
        InlineKeyboardButton('Accept Index', callback_data=f'index#accept#{chat_id}#{last_msg_id}#{message.from_user.id}')
    ],[
        InlineKeyboardButton('Reject Index', callback_data=f'index#reject#{chat_id}#{message.id}#{message.from_user.id}'),
    ]]
    reply_markup = InlineKeyboardMarkup(buttons)
    await bot.send_message(
        LOG_CHANNEL,
        f'#IndexRequest\n\nBy : {message.from_user.mention} (<code>{message.from_user.id}</code>)\nChat ID/ Username - <code> {chat_id}</code>\nLast Message ID - <code>{last_msg_id}</code>\nInviteLink - {link}',
        reply_markup=reply_markup
    )
    await message.reply('ThankYou For the Contribution, Wait For My Moderators to verify the files.')


@Client.on_message(filters.command('setskip') & ADMIN_FILTER)
async def set_skip_number(bot, message):
    if ' ' in message.text:
        _, skip = message.text.split(" ")
        try:
            skip = int(skip)
            if skip < 0:
                raise ValueError
        except ValueError:
            return await message.reply("Skip number must be a non-negative integer.")
        await message.reply(f"Successfully set indexing start message ID as {skip}")
        temp.CURRENT = skip
    else:
        await message.reply("Give me a skip number")


async def index_files_to_db(lst_msg_id, chat, msg, bot):
    """Index messages using bounded bulk database writes and throttled updates."""
    total_files = duplicate = errors = deleted = no_media = unsupported = 0
    processed = 0
    batch = []
    batch_size = 100
    last_update = asyncio.get_running_loop().time()

    async def flush_batch():
        nonlocal total_files, duplicate, errors, batch
        if not batch:
            return
        pending, batch = batch, []
        try:
            saved, duplicates, failed = await save_files_batch(pending)
            total_files += saved
            duplicate += duplicates
            errors += failed
        except Exception:
            logger.exception("Bulk index database write failed")
            errors += len(pending)

    async def update_progress(force=False):
        nonlocal last_update
        now = asyncio.get_running_loop().time()
        if not force and processed % 300 != 0 and now - last_update < 5:
            return
        last_update = now
        text = (
            f"<b>⚡ INDEXING IN PROGRESS</b>\n\n"
            f"Messages scanned: <code>{processed:,}</code>\n"
            f"Files saved: <code>{total_files:,}</code>\n"
            f"Duplicates skipped: <code>{duplicate:,}</code>\n"
            f"Deleted messages: <code>{deleted:,}</code>\n"
            f"Non-media/unsupported: <code>{no_media + unsupported:,}</code>\n"
            f"Errors: <code>{errors:,}</code>"
        )
        try:
            await msg.edit_text(text, reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("✖ Cancel indexing", callback_data="index_cancel")]]
            ))
        except MessageNotModified:
            pass
        except Exception as exc:
            logger.debug("Index progress update skipped: %s", exc)

    async with lock:
        try:
            temp.CANCEL = False
            # The project's iterator fetches message IDs in chunks of up to 200.
            async for message in bot.iter_messages(chat, int(lst_msg_id), int(temp.CURRENT)):
                if temp.CANCEL:
                    await flush_batch()
                    await update_progress(force=True)
                    await msg.edit_text(
                        f"<b>⏹ INDEXING CANCELLED</b>\n\nSaved: <code>{total_files:,}</code>\n"
                        f"Duplicates: <code>{duplicate:,}</code>\nErrors: <code>{errors:,}</code>"
                    )
                    return
                processed += 1
                if message.empty:
                    deleted += 1
                elif not message.media:
                    no_media += 1
                elif message.media not in (enums.MessageMediaType.VIDEO,
                                           enums.MessageMediaType.AUDIO,
                                           enums.MessageMediaType.DOCUMENT):
                    unsupported += 1
                else:
                    media = getattr(message, message.media.value, None)
                    if not media or not getattr(media, "file_id", None):
                        unsupported += 1
                    else:
                        media.caption = message.caption
                        batch.append(media)
                        if len(batch) >= batch_size:
                            await flush_batch()
                if processed % 300 == 0:
                    await update_progress()

            await flush_batch()
            await update_progress(force=True)
            await msg.edit_text(
                f"<b>✅ INDEXING COMPLETED</b>\n\n"
                f"Messages scanned: <code>{processed:,}</code>\n"
                f"Files saved: <code>{total_files:,}</code>\n"
                f"Duplicates skipped: <code>{duplicate:,}</code>\n"
                f"Deleted messages: <code>{deleted:,}</code>\n"
                f"Non-media/unsupported: <code>{no_media + unsupported:,}</code>\n"
                f"Errors: <code>{errors:,}</code>"
            )
        except Exception as exc:
            await flush_batch()
            logger.exception("Indexing failed")
            try:
                await msg.edit_text(
                    f"<b>⚠️ INDEXING STOPPED</b>\n<code>{str(exc)[:700]}</code>\n\n"
                    f"Saved: <code>{total_files:,}</code> | Duplicates: <code>{duplicate:,}</code> | Errors: <code>{errors:,}</code>"
                )
            except Exception:
                pass

