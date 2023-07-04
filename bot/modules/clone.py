#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from random import SystemRandom
from string import ascii_letters, digits
from asyncio import sleep, gather
from aiofiles.os import path as aiopath
from json import loads

from bot import LOGGER, download_dict, download_dict_lock, config_dict, bot
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, sendStatusMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.ext_utils.bot_utils import is_gdrive_link, new_task, sync_to_async, is_share_link, new_task, is_rclone_path, cmd_exec, get_telegraph_list, arg_parser
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.ext_utils.help_messages import CLONE_HELP_MESSAGE
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.listeners.tasks_listener import MirrorLeechListener


async def rcloneNode(client, message, link, dst_path, rcf, tag):
    if link == 'rcl':
        link = await RcloneList(client, message).get_rclone_path('rcd')
        if not is_rclone_path(link):
            await sendMessage(message, link)
            return

    if link.startswith('mrcc:'):
        link = link.split('mrcc:', 1)[1]
        config_path = f'rclone/{message.from_user.id}.conf'
    else:
        config_path = 'rclone.conf'

    if not await aiopath.exists(config_path):
        await sendMessage(message, f"Rclone Config: {config_path} not Exists!")
        return

    if dst_path == 'rcl' or config_dict['RCLONE_PATH'] == 'rcl':
        dst_path = await RcloneList(client, message).get_rclone_path('rcu', config_path)
        if not is_rclone_path(dst_path):
            await sendMessage(message, dst_path)
            return

    dst_path = (dst_path or config_dict['RCLONE_PATH']).strip('/')
    if not is_rclone_path(dst_path):
        await sendMessage(message, 'Wrong Rclone Clone Destination!')
        return
    if dst_path.startswith('mrcc:'):
        if config_path != f'rclone/{message.from_user.id}.conf':
            await sendMessage(message, 'You should use same rclone.conf to clone between pathies!')
            return
        dst_path = dst_path.lstrip('mrcc:')
    elif config_path != 'rclone.conf':
        await sendMessage(message, 'You should use same rclone.conf to clone between pathies!')
        return

    remote, src_path = link.split(':', 1)
    src_path = src_path.strip('/')

    cmd = ['rclone', 'lsjson', '--fast-list', '--stat',
           '--no-modtime', '--config', config_path, f'{remote}:{src_path}']
    res = await cmd_exec(cmd)
    if res[2] != 0:
        if res[2] != -9:
            msg = f'Error: While getting rclone stat. Path: {remote}:{src_path}. Stderr: {res[1][:4000]}'
            await sendMessage(message, msg)
        return
    rstat = loads(res[0])
    if rstat['IsDir']:
        name = src_path.rsplit('/', 1)[-1] if src_path else remote
        dst_path += name if dst_path.endswith(':') else f'/{name}'
        mime_type = 'Folder'
    else:
        name = src_path.rsplit('/', 1)[-1]
        mime_type = rstat['MimeType']

    listener = MirrorLeechListener(message, tag=tag)
    await listener.onDownloadStart()

    RCTransfer = RcloneTransferHelper(listener, name)
    LOGGER.info(
        f'Clone Started: Name: {name} - Source: {link} - Destination: {dst_path}')
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
    async with download_dict_lock:
        download_dict[message.id] = RcloneStatus(
            RCTransfer, message, gid, 'cl')
    await sendStatusMessage(message)
    link, destination = await RCTransfer.clone(config_path, remote, src_path, dst_path, rcf, mime_type)
    if not link:
        return
    LOGGER.info(f'Cloning Done: {name}')
    cmd1 = ['rclone', 'lsf', '--fast-list', '-R',
            '--files-only', '--config', config_path, destination]
    cmd2 = ['rclone', 'lsf', '--fast-list', '-R',
            '--dirs-only', '--config', config_path, destination]
    cmd3 = ['rclone', 'size', '--fast-list', '--json',
            '--config', config_path, destination]
    res1, res2, res3 = await gather(cmd_exec(cmd1), cmd_exec(cmd2), cmd_exec(cmd3))
    if res1[2] != res2[2] != res3[2] != 0:
        if res1[2] == -9:
            return
        files = None
        folders = None
        size = 0
        LOGGER.error(
            f'Error: While getting rclone stat. Path: {destination}. Stderr: {res1[1][:4000]}')
    else:
        files = len(res1[0].split("\n"))
        folders = len(res2[0].split("\n"))
        rsize = loads(res3[0])
        size = rsize['bytes']
    await listener.onUploadComplete(link, size, files, folders, mime_type, name, destination)


async def gdcloneNode(message, link, tag):
    if is_share_link(link):
        try:
            link = await sync_to_async(direct_link_generator, link)
            LOGGER.info(f"Generated link: {link}")
        except DirectDownloadLinkException as e:
            LOGGER.error(str(e))
            if str(e).startswith('ERROR:'):
                await sendMessage(message, str(e))
                return
    if is_gdrive_link(link):
        gd = GoogleDriveHelper()
        name, mime_type, size, files, _ = await sync_to_async(gd.count, link)
        if mime_type is None:
            await sendMessage(message, name)
            return
        if config_dict['STOP_DUPLICATE']:
            LOGGER.info('Checking File/Folder if already in Drive...')
            telegraph_content, contents_no = await sync_to_async(gd.drive_list, name, True, True)
            if telegraph_content:
                msg = f"File/Folder is already available in Drive.\nHere are {contents_no} list results:"
                button = await get_telegraph_list(telegraph_content)
                await sendMessage(message, msg, button)
                return
        listener = MirrorLeechListener(message, tag=tag)
        await listener.onDownloadStart()
        LOGGER.info(f'Clone Started: Name: {name} - Source: {link}')
        drive = GoogleDriveHelper(name, listener=listener)
        if files <= 20:
            msg = await sendMessage(message, f"Cloning: <code>{link}</code>")
            link, size, mime_type, files, folders = await sync_to_async(drive.clone, link)
            await deleteMessage(msg)
        else:
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            async with download_dict_lock:
                download_dict[message.id] = GdriveStatus(
                    drive, size, message, gid, 'cl')
            await sendStatusMessage(message)
            link, size, mime_type, files, folders = await sync_to_async(drive.clone, link)
        if not link:
            return
        LOGGER.info(f'Cloning Done: {name}')
        await listener.onUploadComplete(link, size, files, folders, mime_type, name)
    else:
        await sendMessage(message, CLONE_HELP_MESSAGE)


@new_task
async def clone(client, message):
    input_list = message.text.split(' ')

    arg_base = {'link': '', '-i': 0, '-up': '', '-rcf': ''}

    args = arg_parser(input_list[1:], arg_base)

    try:
        multi = int(args['-i'])
    except:
        multi = 0

    dst_path = args['-up']
    rcf = args['-rcf']
    link = args['link']

    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if not link and (reply_to := message.reply_to_message):
        link = reply_to.text.split('\n', 1)[0].strip()

    @new_task
    async def __run_multi():
        if multi > 1:
            await sleep(5)
            msg = [s.strip() for s in input_list]
            index = msg.index('-i')
            msg[index+1] = f"{multi - 1}"
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
            nextmsg = await sendMessage(nextmsg, " ".join(msg))
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
            nextmsg.from_user = message.from_user
            await sleep(5)
            clone(client, nextmsg)

    __run_multi()

    if len(link) == 0:
        await sendMessage(message, CLONE_HELP_MESSAGE)
        return

    if is_rclone_path(link):
        if not await aiopath.exists('rclone.conf') and not await aiopath.exists(f'rclone/{message.from_user.id}.conf'):
            await sendMessage(message, 'Rclone Config Not exists!')
            return
        if not config_dict['RCLONE_PATH'] and not dst_path:
            await sendMessage(message, 'Destination not specified!')
            return
        await rcloneNode(client, message, link, dst_path, rcf, tag)
    else:
        if not config_dict['GDRIVE_ID']:
            await sendMessage(message, 'GDRIVE_ID not Provided!')
            return
        await gdcloneNode(message, link, tag)


bot.add_handler(MessageHandler(clone, filters=command(
    BotCommands.CloneCommand) & CustomFilters.authorized))
