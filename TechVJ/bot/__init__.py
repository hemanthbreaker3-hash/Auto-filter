# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

from pyrogram import Client, types
from info import *
from utils import temp
from typing import Union, Optional, AsyncGenerator
from aiohttp import web


class TechVJXBot(Client):

    def __init__(self):
        super().__init__(
            name=SESSION,
            api_id=API_ID,
            api_hash=API_HASH,
            bot_token=BOT_TOKEN,
            workers=150,
            plugins={"root": "plugins"},
            sleep_threshold=5,
        )

    async def send_rich_message(self, chat_id, html, **kwargs):
        from TechVJ.util.telegram_rich import send_rich_message
        return await send_rich_message(self, chat_id, html, **kwargs)

    async def send_rich_markdown(self, chat_id, markdown, **kwargs):
        from TechVJ.util.telegram_rich import send_rich_markdown
        return await send_rich_markdown(self, chat_id, markdown, **kwargs)

    async def send_styled_message(self, chat_id, text, buttons=None, **kwargs):
        from TechVJ.util.telegram_rich import send_styled_message
        return await send_styled_message(self, chat_id, text, buttons=buttons, **kwargs)

    async def set_self(self):
        temp.BOT = self
    
    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially.
        This convenience method does the same as repeatedly calling :meth:`~pyrogram.Client.get_messages` in a loop, thus saving
        you from the hassle of setting up boilerplate code. It is useful for getting the whole chat messages with a
        single call.
        Parameters:
            chat_id (``int`` | ``str``):
                Unique identifier (int) or username (str) of the target chat.
                For your personal cloud (Saved Messages) you can simply use "me" or "self".
                For a contact that exists in your Telegram address book you can use his phone number (str).
                
            limit (``int``):
                Identifier of the last message to be returned.
                
            offset (``int``, *optional*):
                Identifier of the first message to be returned.
                Defaults to 0.
        Returns:
            ``Generator``: A generator yielding :obj:`~pyrogram.types.Message` objects.
        Example:
            .. code-block:: python
                for message in app.iter_messages("pyrogram", 1, 15000):
                    print(message.text)
        """
        current = offset
        while True:
            new_diff = min(200, limit - current + 1)
            if new_diff <= 0:
                return
            messages = await self.get_messages(chat_id, list(range(current, current + new_diff)))
            for message in messages:
                yield message
                current += 1
      
TechVJBot = TechVJXBot()

multi_clients = {}
work_loads = {}

