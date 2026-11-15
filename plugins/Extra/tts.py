# Don't Remove Credit @MoviesZoneFlix
# Subscribe YouTube Channel For Amazing Bot @MoviesZoneFlix
# Ask Doubt on telegram @MoviesZoneFlix

import traceback
from asyncio import get_running_loop
from io import BytesIO
try:
    from googletrans import Translator
except Exception:
    Translator = None
from gtts import gTTS
from pyrogram import Client, filters
from pyrogram.types import Message


def convert(text):
    audio = BytesIO()
    lang = "en"
    if Translator is not None:
        try:
            i = Translator().translate(text, dest="en")
            lang = i.src or "en"
        except Exception:
            lang = "en"
    tts = gTTS(text, lang=lang)
    audio.name = lang + ".mp3"
    tts.write_to_fp(audio)
    return audio


@Client.on_message(filters.command("tts"))
async def text_to_speech(bot, message: Message):
    vj = await bot.ask(chat_id = message.from_user.id, text = "Now send me your text.")
    if vj.text:
        m = await vj.reply_text("Processing")
        text = vj.text
        try:
            loop = get_running_loop()
            audio = await loop.run_in_executor(None, convert, text)
            await vj.reply_audio(audio)
            await m.delete()
            audio.close()
        except Exception as e:
            await m.edit(e)
            e = traceback.format_exc()
            print(e)
    else:
        await vj.reply_text("Send me only text Buddy.")



