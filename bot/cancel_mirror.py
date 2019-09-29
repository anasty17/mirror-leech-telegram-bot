from telegram.ext import CommandHandler, run_async
from bot.helper.message_utils import *
from bot import download_dict, aria2, dispatcher


@run_async
def cancel_mirror(update: Update, context):
    mirror_message = update.message.reply_to_message
    if mirror_message is None or mirror_message.message_id not in download_dict.keys():
        if '/mirror' in mirror_message.text:
            msg = 'Message has already been cancelled'
        else:
            msg = 'Please reply to the /mirror message which was used to start the download to cancel it!'
        sendMessage(msg, context, update)
        return
    download = download_dict[mirror_message.message_id].download()
    aria2.pause([download])
    sendMessage("Download canceled", context, update)


cancel_mirror_handler = CommandHandler('cancel', cancel_mirror)
dispatcher.add_handler(cancel_mirror_handler)