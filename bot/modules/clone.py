#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from random import SystemRandom
from string import ascii_letters, digits
from asyncio import sleep

from bot import LOGGER, download_dict, download_dict_lock, Interval, config_dict, status_reply_dict_lock, bot
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, delete_all_messages, update_all_messages, sendStatusMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.clone_status import CloneStatus
from bot.helper.ext_utils.bot_utils import is_gdrive_link, new_task, sync_to_async, is_share_link, new_task
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator


@new_task
async def cloneNode(client, message):
    if not config_dict['GDRIVE_ID']:
        await sendMessage(message, 'GDRIVE_ID not Provided!')
        return
    args = message.text.split()
    link = ''
    multi = 0
    if len(args) > 1:
        link = args[1].strip()
        if link.strip().isdigit():
            multi = int(link)
            link = ''
        elif username := message.from_user.username:
            tag = f"@{username}"
        else:
            tag = message.from_user.mention
    if reply_to := message.reply_to_message:
        if len(link) == 0:
            link = reply_to.text.split(maxsplit=1)[0].strip()
        if not reply_to.from_user.is_bot:
            if username := reply_to.from_user.username:
                tag = f"@{username}"
            else:
                tag = reply_to.from_user.mention

    @new_task
    async def __run_multi():
        if multi > 1:
            await sleep(4)
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
            args[1] = f"{multi - 1}"
            nextmsg = await sendMessage(nextmsg, " ".join(args))
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
            nextmsg.from_user = message.from_user
            await sleep(4)
            await cloneNode(client, nextmsg)

    if is_share_link(link):
        try:
            link = await sync_to_async(direct_link_generator, link)
            LOGGER.info(f"Generated link: {link}")
        except DirectDownloadLinkException as e:
            LOGGER.error(str(e))
            if str(e).startswith('ERROR:'):
                await sendMessage(message, str(e))
                __run_multi()
                return
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        res, size, name, files = await sync_to_async(gd.helper, link)
        if res != "":
            await sendMessage(message, res)
            __run_multi()
            return
        if config_dict['STOP_DUPLICATE']:
            LOGGER.info('Checking File/Folder if already in Drive...')
            smsg, button = await sync_to_async(gd.drive_list, name, True, True)
            if smsg:
                msg = "File/Folder is already available in Drive.\nHere are the search results:"
                await sendMessage(message, msg, button)
                __run_multi()
                return
        __run_multi()
        if files <= 20:
            msg = await sendMessage(message, f"Cloning: <code>{link}</code>")
            result, button = await sync_to_async(gd.clone, link)
            await deleteMessage(msg)
        else:
            drive = GoogleDriveHelper(name)
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            clone_status = CloneStatus(drive, size, message, gid)
            async with download_dict_lock:
                download_dict[message.id] = clone_status
            await sendStatusMessage(message)
            result, button = await sync_to_async(drive.clone, link)
            async with download_dict_lock:
                del download_dict[message.id]
                count = len(download_dict)
            try:
                if count == 0:
                    async with status_reply_dict_lock:
                        if Interval:
                            Interval[0].cancel()
                            del Interval[0]
                    await delete_all_messages()
                else:
                    await update_all_messages()
            except:
                pass
        cc = f'\n\n<b>cc: </b>{tag}'
        if button in ["cancelled", ""]:
            await sendMessage(message, f"{tag} {result}")
        else:
            await sendMessage(message, result + cc, button)
            LOGGER.info(f'Cloning Done: {name}')
    else:
        await sendMessage(message, "Send Gdrive link along with command or by replying to the link by command\n\n<b>Multi links only by replying to first link:</b>\n<code>/cmd</code> 10(number of links)")


bot.add_handler(MessageHandler(cloneNode, filters=command(
    BotCommands.CloneCommand) & CustomFilters.authorized))
