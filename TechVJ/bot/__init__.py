# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

from pyrogram import Client, types
from info import *
from utils import temp
from typing import Union, Optional, AsyncGenerator
from aiohttp import web
from TechVJ.util.telegram_rich import (
    ButtonStyle,
    install_global_styled_buttons,
    send_rich_message,
    send_rich_markdown,
    send_styled_message,
)

install_global_styled_buttons()


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
        return await send_rich_message(self, chat_id, html, **kwargs)

    async def send_rich_markdown(self, chat_id, markdown, **kwargs):
        return await send_rich_markdown(self, chat_id, markdown, **kwargs)

    async def send_styled_message(self, chat_id, text, buttons=None, **kwargs):
        return await send_styled_message(self, chat_id, text, buttons=buttons, **kwargs)

    async def set_self(self):
        temp.BOT = self
    
    async def iter_messages(
        self,
        chat_id: Union[int, str],
        limit: int,
        offset: int = 0,
    ) -> Optional[AsyncGenerator["types.Message", None]]:
        """Iterate through a chat sequentially."""
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
