#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from random import SystemRandom
from string import ascii_letters, digits
from asyncio import sleep, gather
from aiofiles.os import path as aiopath
from json import loads

from bot import LOGGER, download_dict, download_dict_lock, config_dict, bot
from bot.helper.mirror_utils.gdrive_utlis.clone import gdClone
from bot.helper.mirror_utils.gdrive_utlis.count import gdCount
from bot.helper.mirror_utils.gdrive_utlis.search import gdSearch
from bot.helper.telegram_helper.message_utils import sendMessage, deleteMessage, sendStatusMessage
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.mirror_utils.status_utils.gdrive_status import GdriveStatus
from bot.helper.ext_utils.bot_utils import is_gdrive_link, new_task, sync_to_async, is_share_link, new_task, is_rclone_path, cmd_exec, get_telegraph_list, arg_parser, is_gdrive_id
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_utils.gdrive_utlis.list import gdriveList
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.ext_utils.help_messages import CLONE_HELP_MESSAGE
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.listeners.task_listener import MirrorLeechListener


async def rcloneNode(client, link, dst_path, rcf, listener):
    if link == 'rcl':
        link = await RcloneList(client, listener.message).get_rclone_path('rcd')
        if not is_rclone_path(link):
            await sendMessage(listener.message, link)
            return

    if link.startswith('mrcc:'):
        link = link.split('mrcc:', 1)[1]
        config_path = f'rclone/{listener.user_id}.conf'
        private = True
    else:
        config_path = 'rclone.conf'
        private = False

    if not await aiopath.exists(config_path):
        await sendMessage(listener.message, f"Rclone Config: {config_path} not Exists!")
        return

    if dst_path == 'rcl' or config_dict['RCLONE_PATH'] == 'rcl' or listener.user_dict.get('rclone_path') == 'rcl':
        dst_path = await RcloneList(client, listener.message).get_rclone_path('rcu', config_path)
        if not is_rclone_path(dst_path):
            await sendMessage(listener.message, dst_path)
            return

    dst_path = (dst_path or listener.user_dict.get('rclone_path', '')
                or config_dict['RCLONE_PATH']).strip('/')
    if not is_rclone_path(dst_path):
        await sendMessage(listener.message, 'Wrong Rclone Clone Destination!')
        return
    if dst_path.startswith('mrcc:'):
        if config_path != f'rclone/{listener.user_id}.conf':
            await sendMessage(listener.message, 'You should use same rclone.conf to clone between pathies!')
            return
        dst_path = dst_path.lstrip('mrcc:')
    elif config_path != 'rclone.conf':
        await sendMessage(listener.message, 'You should use same rclone.conf to clone between pathies!')
        return

    remote, src_path = link.split(':', 1)
    src_path = src_path.strip('/')

    cmd = ['rclone', 'lsjson', '--fast-list', '--stat',
           '--no-modtime', '--config', config_path, f'{remote}:{src_path}']
    res = await cmd_exec(cmd)
    if res[2] != 0:
        if res[2] != -9:
            msg = f'Error: While getting rclone stat. Path: {remote}:{src_path}. Stderr: {res[1][:4000]}'
            await sendMessage(listener.message, msg)
        return
    rstat = loads(res[0])
    if rstat['IsDir']:
        name = src_path.rsplit('/', 1)[-1] if src_path else remote
        dst_path += name if dst_path.endswith(':') else f'/{name}'
        mime_type = 'Folder'
    else:
        name = src_path.rsplit('/', 1)[-1]
        mime_type = rstat['MimeType']

    listener.upDest = dst_path
    await listener.onDownloadStart()

    RCTransfer = RcloneTransferHelper(listener, name)
    LOGGER.info(
        f'Clone Started: Name: {name} - Source: {link} - Destination: {dst_path}')
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
    async with download_dict_lock:
        download_dict[listener.uid] = RcloneStatus(
            RCTransfer, listener.message, gid, 'cl')
    await sendStatusMessage(listener.message)
    link, destination = await RCTransfer.clone(config_path, remote, src_path, rcf, mime_type)
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
    await listener.onUploadComplete(link, size, files, folders, mime_type, name, destination, private=private)


async def gdcloneNode(client, link, dest_id, listener):
    if is_share_link(link):
        try:
            link = await sync_to_async(direct_link_generator, link)
            LOGGER.info(f"Generated link: {link}")
        except DirectDownloadLinkException as e:
            LOGGER.error(str(e))
            if str(e).startswith('ERROR:'):
                await sendMessage(listener.message, str(e))
                return
    if is_gdrive_link(link) or is_gdrive_id(link):
        sa = config_dict['USE_SERVICE_ACCOUNTS']
        if link == 'gdl':
            gdl = gdriveList(client, listener.message)
            link = await gdl.get_target_id('gdd')
            if not is_gdrive_id(link):
                await sendMessage(listener.message, link)
                return
            sa = gdl.use_sa
        if link.startswith('mtp:'):
            token_path = f'tokens/{listener.user_id}.pickle'
            private = True
            sa = False
        elif sa:
            token_path = 'accounts'
            private = False
        else:
            token_path = 'token.pickle'
            private = False
        if dest_id == 'gdl' or config_dict['GDRIVE_ID'] == 'gdl' or listener.user_dict.get('gdrive_id') == 'gdl':
            dest_id = await gdriveList(client, listener.message).get_target_id('gdu', token_path)
            if not is_gdrive_id(dest_id):
                await sendMessage(listener.message, dest_id)
                return
        dest_id = dest_id or listener.user_dict.get(
            'gdrive_id', '') or config_dict['GDRIVE_ID']
        if not is_gdrive_id(dest_id):
            await sendMessage(listener.message, 'Wrong Gdrive ID!')
            return
        gdc = gdCount()
        if sa:
            gdc.use_sa = True
        name, mime_type, size, files, _ = await sync_to_async(gdc.count, link, listener.user_id)
        if mime_type is None:
            await sendMessage(listener.message, name)
            return
        listener.upDest = dest_id
        if dest_id.startswith('mtp:') and listener.user_dict('stop_duplicate', False) or not dest_id.startswith('mtp:') and config_dict['STOP_DUPLICATE']:
            LOGGER.info('Checking File/Folder if already in Drive...')
            gds = gdSearch(stopDup=True, noMulti=True)
            if sa:
                gds.use_sa = True
            telegraph_content, contents_no = await sync_to_async(gds.drive_list, name, dest_id, listener.user_id)
            if telegraph_content:
                msg = f"File/Folder is already available in Drive.\nHere are {contents_no} list results:"
                button = await get_telegraph_list(telegraph_content)
                await sendMessage(listener.message, msg, button)
                return
        await listener.onDownloadStart()
        LOGGER.info(f'Clone Started: Name: {name} - Source: {link}')
        drive = gdClone(name, listener=listener)
        if sa:
            drive.use_sa = True
        if files <= 10:
            msg = await sendMessage(listener.message, f"Cloning: <code>{link}</code>")
        else:
            msg = ''
            gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
            async with download_dict_lock:
                download_dict[listener.uid] = GdriveStatus(
                    drive, size, listener.message, gid, 'cl')
            await sendStatusMessage(listener.message)
        link, size, mime_type, files, folders, dir_id = await sync_to_async(drive.clone, link)
        if msg:
            await deleteMessage(msg)
        if not link:
            return
        LOGGER.info(f'Cloning Done: {name}')
        await listener.onUploadComplete(link, size, files, folders, mime_type, name, dir_id=dir_id, private=private)
    else:
        await sendMessage(listener.message, CLONE_HELP_MESSAGE)


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

    LOGGER.info(link)

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

    listener = MirrorLeechListener(message, tag=tag)

    if is_rclone_path(link):
        if not await aiopath.exists('rclone.conf') and not await aiopath.exists(f'rclone/{message.from_user.id}.conf'):
            await sendMessage(message, 'Rclone Config Not exists!')
            return
        if not config_dict['RCLONE_PATH'] and not listener.user_dict.get('rclone_path') and not dst_path:
            await sendMessage(message, 'Destination not specified!')
            return
        await rcloneNode(client, link, dst_path, rcf, listener)
    else:
        if not await aiopath.exists('token.pickle') and not await aiopath.exists(f'tokens/{message.from_user.id}.pickle') \
            and not await aiopath.exists('accounts'):
            await sendMessage(message, 'Token.pickle and service accounts Not exists!')
            return
        if not config_dict['GDRIVE_ID'] and not listener.user_dict.get('gdrive_id') and not dst_path:
            await sendMessage(message, 'GDRIVE_ID not Provided!')
            return
        await gdcloneNode(client, link, dst_path, listener)


bot.add_handler(MessageHandler(clone, filters=command(
    BotCommands.CloneCommand) & CustomFilters.authorized))
