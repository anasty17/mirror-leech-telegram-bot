#!/usr/bin/env python3
from asyncio import Event

from bot import config_dict, queued_dl, queued_up, non_queued_up, non_queued_dl, queue_dict_lock, LOGGER
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.fs_utils import get_base_name, check_storage_threshold
from bot.helper.ext_utils.bot_utils import sync_to_async, get_readable_file_size


async def stop_duplicate_check(name, listener):
    if (
        not config_dict['STOP_DUPLICATE']
        or listener.isLeech
        or listener.upPath != 'gd'
    ):
        return False, None
    LOGGER.info('Checking File/Folder if already in Drive: {name}')
    if listener.isZip:
        name = f"{name}.zip"
    elif listener.extract:
        try:
            name = get_base_name(name)
        except:
            name = None
    if name is not None:
        smsg, button = await sync_to_async(GoogleDriveHelper().drive_list, name, stopDup=True)
        if smsg:
            msg = "File/Folder is already available in Drive.\nHere are the search results:"
            return msg, button
    return False, None


async def is_queued(uid):
    all_limit = config_dict['QUEUE_ALL']
    dl_limit = config_dict['QUEUE_DOWNLOAD']
    event = None
    added_to_queue = False
    if all_limit or dl_limit:
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)) or (dl_limit and dl >= dl_limit):
                added_to_queue = True
                event = Event()
                queued_dl[uid] = event
    return added_to_queue, event


def start_dl_from_queued(uid):
    queued_dl[uid].set()
    del queued_dl[uid]


def start_up_from_queued(uid):
    queued_up[uid].set()
    del queued_up[uid]


async def start_from_queued():
    if all_limit := config_dict['QUEUE_ALL']:
        dl_limit = config_dict['QUEUE_DOWNLOAD']
        up_limit = config_dict['QUEUE_UPLOAD']
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            all_ = dl + up
            if all_ < all_limit:
                f_tasks = all_limit - all_
                if queued_up and (not up_limit or up < up_limit):
                    for index, uid in enumerate(list(queued_up.keys()), start=1):
                        f_tasks = all_limit - all_
                        start_up_from_queued(uid)
                        f_tasks -= 1
                        if f_tasks == 0 or (up_limit and index >= up_limit - up):
                            break
                if queued_dl and (not dl_limit or dl < dl_limit) and f_tasks != 0:
                    for index, uid in enumerate(list(queued_dl.keys()), start=1):
                        start_dl_from_queued(uid)
                        if (dl_limit and index >= dl_limit - dl) or index == f_tasks:
                            break
        return

    if up_limit := config_dict['QUEUE_UPLOAD']:
        async with queue_dict_lock:
            up = len(non_queued_up)
            if queued_up and up < up_limit:
                f_tasks = up_limit - up
                for index, uid in enumerate(list(queued_up.keys()), start=1):
                    start_up_from_queued(uid)
                    if index == f_tasks:
                        break
    else:
        async with queue_dict_lock:
            if queued_up:
                for uid in list(queued_up.keys()):
                    start_up_from_queued(uid)

    if dl_limit := config_dict['QUEUE_DOWNLOAD']:
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            if queued_dl and dl < dl_limit:
                f_tasks = dl_limit - dl
                for index, uid in enumerate(list(queued_dl.keys()), start=1):
                    start_dl_from_queued(uid)
                    if index == f_tasks:
                        break
    else:
        async with queue_dict_lock:
            if queued_dl:
                for uid in list(queued_dl.keys()):
                    start_dl_from_queued(uid)


async def limit_checker(size, listener, isTorrent=False, isMega=False, isDriveLink=False, isYtdlp=False):
    limit_exceeded = ''
    if listener.isClone:
        if CLONE_LIMIT := config_dict['CLONE_LIMIT']:
            limit = CLONE_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Clone limit is {get_readable_file_size(limit)}.'
    elif isMega:
        if MEGA_LIMIT := config_dict['MEGA_LIMIT']:
            limit = MEGA_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Mega limit is {get_readable_file_size(limit)}'
    elif isDriveLink:
        if GDRIVE_LIMIT := config_dict['GDRIVE_LIMIT']:
            limit = GDRIVE_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Google drive limit is {get_readable_file_size(limit)}'
    elif isYtdlp:
        if YTDLP_LIMIT := config_dict['YTDLP_LIMIT']:
            limit = YTDLP_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Ytdlp limit is {get_readable_file_size(limit)}'
    elif isTorrent:
        if TORRENT_LIMIT := config_dict['TORRENT_LIMIT']:
            limit = TORRENT_LIMIT * 1024**3
            if size > limit:
                limit_exceeded = f'Torrent limit is {get_readable_file_size(limit)}'
    elif DIRECT_LIMIT := config_dict['DIRECT_LIMIT']:
        limit = DIRECT_LIMIT * 1024**3
        if size > limit:
            limit_exceeded = f'Direct limit is {get_readable_file_size(limit)}'
    if not limit_exceeded and (LEECH_LIMIT := config_dict['LEECH_LIMIT']) and listener.isLeech:
        limit = LEECH_LIMIT * 1024**3
        if size > limit:
            limit_exceeded = f'Leech limit is {get_readable_file_size(limit)}'
    if not limit_exceeded and (STORAGE_THRESHOLD := config_dict['STORAGE_THRESHOLD']) and not listener.isClone:
        arch = any([listener.isZip, listener.extract])
        limit = STORAGE_THRESHOLD * 1024**3
        acpt = await sync_to_async(check_storage_threshold, size, limit, arch)
        if not acpt:
            limit_exceeded = f'You must leave {get_readable_file_size(limit)} free storage.'
    if limit_exceeded:
        return f"{limit_exceeded}.\nYour File/Folder size is {get_readable_file_size(size)}"