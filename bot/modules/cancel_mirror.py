from telegram.ext import CommandHandler, run_async
from bot.helper.telegram_helper.message_utils import *
from bot import download_dict, aria2, dispatcher, download_dict_lock, DOWNLOAD_DIR
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.ext_utils.fs_utils import clean_download
from bot.helper.telegram_helper.bot_commands import BotCommands
from time import sleep

@run_async
def cancel_mirror(bot,update):
    mirror_message = update.message.reply_to_message
    with download_dict_lock:
        keys = download_dict.keys()
        dl = download_dict[mirror_message.message_id]
        download = download_dict[mirror_message.message_id].download()
    if mirror_message is None or mirror_message.message_id not in keys:
        if '/mirror' in mirror_message.text or '/tarmirror' in mirror_message.text:
            msg = 'Message has already been cancelled'
        else:
            msg = 'Please reply to the /mirror message which was used to start the download to cancel it!'
        sendMessage(msg, bot, update)
        return
    if dl.status() != "Queued":
        if len(download.followed_by_ids) != 0:
            downloads = aria2.get_downloads(download.followed_by_ids)
            aria2.pause(downloads)
        aria2.pause([download])
    elif dl.status() == "Uploading":
        sendMessage("Upload in Progress, Dont Cancel it.",bot,update)
        return
    else:
        dl._listener.onDownloadError("Download stopped by user!")
    sleep(1) #Wait a Second For Aria2 To free Resources. 
    clean_download(f'{DOWNLOAD_DIR}{mirror_message.message_id}/')


@run_async
def cancel_all(update, bot):
    with download_dict_lock:
        for dlDetails in list(download_dict.values()):
            if dlDetails.download().is_waiting:
                dlDetails._listener.onDownloadError("Download Manually Cancelled By user.")
            aria2.pause([dlDetails.download()])
    delete_all_messages()
    sendMessage('Cancelled all downloads!',update,bot)
    sleep(0.5)#Wait a Second For Aria2 To free Resources. 
    clean_download(DOWNLOAD_DIR)


cancel_mirror_handler = CommandHandler(BotCommands.CancelMirror, cancel_mirror,
                                       filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)
cancel_all_handler = CommandHandler(BotCommands.CancelAllCommand, cancel_all,
                                    filters=CustomFilters.owner_filter)
dispatcher.add_handler(cancel_all_handler)
dispatcher.add_handler(cancel_mirror_handler)
