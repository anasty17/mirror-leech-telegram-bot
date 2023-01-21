from random import SystemRandom
from string import ascii_letters, digits
from telegram.ext import CommandHandler
from threading import Thread
from time import sleep
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator

from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, delete_all_messages, update_all_messages, sendStatusMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot import dispatcher, LOGGER, download_dict, download_dict_lock, Interval, config_dict
from bot.helper.ext_utils.bot_utils import is_gdrive_link, new_thread, is_Sharerlink


def _clone(message, bot):
    if not config_dict['GDRIVE_ID']:
        sendMessage('GDRIVE_ID not Provided!', bot, message)
        return
    args = message.text.split()
    reply_to = message.reply_to_message
    link = ''
    multi = 0
    if len(args) > 1:
        link = args[1].strip()
        if link.strip().isdigit():
            multi = int(link)
            link = ''
        elif message.from_user.username:
            tag = f"@{message.from_user.username}"
        else:
            tag = message.from_user.mention_html(message.from_user.first_name)
    if reply_to:
        if len(link) == 0:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if reply_to.from_user.username:
            tag = f"@{reply_to.from_user.username}"
        else:
            tag = reply_to.from_user.mention_html(reply_to.from_user.first_name)

    def __run_multi():
        if multi <= 1:
            return
        sleep(4)
        nextmsg = type('nextmsg', (object, ), {'chat_id': message.chat_id,
                                                'message_id': message.reply_to_message.message_id + 1})
        cmsg = message.text.split()
        cmsg[1] = f"{multi - 1}"
        nextmsg = sendMessage(" ".join(cmsg), bot, nextmsg)
        nextmsg.from_user.id = message.from_user.id
        sleep(4)
        Thread(target=_clone, args=(nextmsg, bot)).start()

    if is_Sharerlink(link):
        try:
            link = direct_link_generator(link)
            LOGGER.info(f"Generated link: {link}")
        except DirectDownloadLinkException as e:
            LOGGER.info(str(e))
            if str(e).startswith('ERROR:'):
                sendMessage(str(e), bot, message)
                __run_multi()
                return
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        res, size, name, files = gd.helper(link)
        if res != "":
            sendMessage(res, bot, message)
            __run_multi()
            return
        if config_dict['STOP_DUPLICATE']:
            LOGGER.info('Checking File/Folder if already in Drive...')
            smsg, button = gd.drive_list(name, True, True)
            if smsg:
                msg = "File/Folder is already available in Drive.\nHere are the search results:"
                sendMessage(msg, bot, message, button)
                __run_multi()
                return
        __run_multi()
        if files <= 20:
            msg = sendMessage(f"Cloning: <code>{link}</code>", bot, message)
            result, button = gd.clone(link)
            deleteMessage(bot, msg)
        else:
            drive = GoogleDriveHelper(name)
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            clone_status = CloneStatus(drive, size, message, gid)
            with download_dict_lock:
                download_dict[message.message_id] = clone_status
            sendStatusMessage(message, bot)
            result, button = drive.clone(link)
            with download_dict_lock:
                del download_dict[message.message_id]
                count = len(download_dict)
            try:
                if count == 0:
                    Interval[0].cancel()
                    del Interval[0]
                    delete_all_messages()
                else:
                    update_all_messages()
            except IndexError:
                pass
        cc = f'\n\n<b>cc: </b>{tag}'
        if button in ["cancelled", ""]:
            sendMessage(f"{tag} {result}", bot, message)
        else:
            sendMessage(result + cc, bot, message, button)
            LOGGER.info(f'Cloning Done: {name}')
    else:
        sendMessage("Send Gdrive link along with command or by replying to the link by command\n\n<b>Multi links only by replying to first link:</b>\n<code>/cmd</code> 10(number of links)", bot, message)

@new_thread
def cloneNode(update, context):
    _clone(update.message, context.bot)

clone_handler = CommandHandler(BotCommands.CloneCommand, cloneNode,
                               filters=CustomFilters.authorized_chat | CustomFilters.authorized_user)

dispatcher.add_handler(clone_handler)
