from telegram.ext import CommandHandler, run_async
from bot.helper.message_utils import *
from bot import download_dict, aria2, dispatcher


@run_async
def cancel_mirror(update: Update, context):
    if update.message.reply_to_message is None:
        sendMessage("Please reply to the /mirror message which was used to start the download to cancel it",
                    context, update)
        return
    download = download_dict[update.message.reply_to_message.message_id].download()
    aria2.pause([download])
    sendMessage("Download canceled", context, update)


cancel_mirror_handler = CommandHandler('cancel', cancel_mirror)
dispatcher.add_handler(cancel_mirror_handler)