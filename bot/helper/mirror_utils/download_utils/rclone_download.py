#!/usr/bin/env python3
from asyncio import gather
from json import loads
from random import SystemRandom
from string import ascii_letters, digits

from bot import download_dict, download_dict_lock, queue_dict_lock, non_queued_dl, LOGGER
from bot.helper.ext_utils.bot_utils import cmd_exec
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.task_manager import is_queued, stop_duplicate_check
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper


async def add_rclone_download(rc_path, config_path, path, name, listener):
    remote, rc_path = rc_path.split(':', 1)
    rc_path = rc_path.strip('/')

    cmd1 = ['rclone', 'lsjson', '--fast-list', '--stat', '--no-mimetype',
            '--no-modtime', '--config', config_path, f'{remote}:{rc_path}']
    cmd2 = ['rclone', 'size', '--fast-list',
            '--json', '--config', config_path, f'{remote}:{rc_path}']
    res1, res2 = await gather(cmd_exec(cmd1), cmd_exec(cmd2))
    if res1[2] != res2[2] != 0:
        if res1[2] != -9:
            msg = f'Error: While getting rclone stat/size. Path: {remote}:{rc_path}. Stderr: {res1[1][:4000]}'
            await sendMessage(listener.message, msg)
        return
    rstat = loads(res1[0])
    rsize = loads(res2[0])
    if rstat['IsDir']:
        if not name:
            name = rc_path.rsplit('/', 1)[-1] if rc_path else remote
        path += name
    else:
        name = rc_path.rsplit('/', 1)[-1]
    size = rsize['bytes']
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))

    msg, button = await stop_duplicate_check(name, listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        return

    added_to_queue, event = await is_queued(listener.uid)
    if added_to_queue:
        LOGGER.info(f"Added to Queue/Download: {name}")
        async with download_dict_lock:
            download_dict[listener.uid] = QueueStatus(
                name, size, gid, listener, 'dl')
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        await event.wait()
        async with download_dict_lock:
            if listener.uid not in download_dict:
                return
        from_queue = True
    else:
        from_queue = False

    RCTransfer = RcloneTransferHelper(listener, name)
    async with download_dict_lock:
        download_dict[listener.uid] = RcloneStatus(
            RCTransfer, listener.message, size, gid, 'dl')
    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)

    if from_queue:
        LOGGER.info(f'Start Queued Download with rclone: {rc_path}')
    else:
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        LOGGER.info(f"Download with rclone: {rc_path}")

    await RCTransfer.download(remote, rc_path, config_path, path)
