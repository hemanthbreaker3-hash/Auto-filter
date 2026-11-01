# Don't Remove Credit @TGBoxOffice
# Subscribe YouTube Channel For Amazing Bot @TGBoxOffice
# Ask Doubt on telegram @TGBoxOffice

import re, logging
from pyrogram import Client, filters
from info import DELETE_CHANNELS
from database.ia_filterdb import delete_file_everywhere, unpack_new_file_id

logger = logging.getLogger(__name__)
media_filter = filters.document | filters.video | filters.audio

@Client.on_message(filters.chat(DELETE_CHANNELS) & media_filter)
async def deletemultiplemedia(bot, message):
    """Delete Multiple files from database"""

    for file_type in ("document", "video", "audio"):
        media = getattr(message, file_type, None)
        if media is not None:
            break
    else:
        return

    file_id = unpack_new_file_id(media.file_id)

    deleted = delete_file_everywhere({'file_id': file_id})
    if not deleted:
        file_name = re.sub(r"(_|\-|\.|\+)", " ", str(media.file_name))
        unwanted_chars = ['[', ']', '(', ')']
        for char in unwanted_chars:
            file_name = file_name.replace(char, '')
        file_name = ' '.join(filter(lambda x: not x.startswith('@'), file_name.split()))
        deleted = delete_file_everywhere({'file_name': file_name, 'file_size': media.file_size}, many=True)
        if not deleted:
            deleted = delete_file_everywhere({'file_name': media.file_name, 'file_size': media.file_size}, many=True)
    if deleted:
        logger.info('File is successfully deleted from database.')
    else:
        logger.info('File not found in database.')
