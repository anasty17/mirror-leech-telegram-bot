from telegram.ext import CommandHandler, run_async
from bot.helper.telegram_helper.message_utils import *
from bot import download_dict, aria2, dispatcher, download_dict_lock, DOWNLOAD_DIR
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.ext_utils.fs_utils import clean_download
from bot.helper.telegram_helper.bot_commands import BotCommands
from time import sleep

@run_async
def cancel_mirror(update: Update, context):
    mirror_message = update.message.reply_to_message
    with download_dict_lock:
        keys = download_dict.keys()
        download = download_dict[mirror_message.message_id].download()
    if mirror_message is None or mirror_message.message_id not in keys:
        if '/mirror' in mirror_message.text or '/tarmirror' in mirror_message.text:
            msg = 'Message has already been cancelled'
        else:
            msg = 'Please reply to the /mirror message which was used to start the download to cancel it!'
        return
    else:
        msg = 'Download cancelled'
    sendMessage(msg, context, update)
    if len(download.followed_by_ids) != 0:
        downloads = aria2.get_downloads(download.followed_by_ids)
        aria2.pause(downloads)
    aria2.pause([download])
    with download_dict_lock:
        upload_helper = download_dict[mirror_message.message_id].upload_helper
    if upload_helper is not None:
        upload_helper.cancel()
    sleep(1) #Wait a Second For Aria2 To free Resources. 
    clean_download(f'{DOWNLOAD_DIR}{mirror_message.message_id}/')


@run_async
def cancel_all(update, context):
    aria2.pause_all(True)
    sendMessage('Cancelled all downloads!', context, update)
    sleep(1) #Wait a Second For Aria2 To free Resources. 
    clean_download(DOWNLOAD_DIR)


cancel_mirror_handler = CommandHandler(BotCommands.CancelMirror, cancel_mirror,
                                       filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
cancel_all_handler = CommandHandler(BotCommands.CancelAllCommand, cancel_all,
                                    filters=CustomFilters.owner_filter)
dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
