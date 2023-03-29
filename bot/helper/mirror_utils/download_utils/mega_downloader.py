#!/usr/bin/env python3
from random import SystemRandom
from string import ascii_letters, digits
from aiofiles.os import makedirs
from asyncio import Event
from mega import (MegaApi, MegaListener, MegaRequest, MegaTransfer, MegaError)

from bot import LOGGER, config_dict, download_dict_lock, download_dict, non_queued_dl, non_queued_up, queued_dl, queue_dict_lock
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import get_mega_link_type, async_to_sync, sync_to_async
from bot.helper.mirror_utils.status_utils.mega_download_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.fs_utils import get_base_name


class MegaAppListener(MegaListener):
    _NO_EVENT_ON = (MegaRequest.TYPE_LOGIN, MegaRequest.TYPE_FETCH_NODES)
    NO_ERROR = "no error"

    def __init__(self, continue_event: Event, listener):
        self.continue_event = continue_event
        self.node = None
        self.public_node = None
        self.listener = listener
        self.__bytes_transferred = 0
        self.is_cancelled = False
        self.__speed = 0
        self.__name = ''
        self.__size = 0
        self.error = None
        self.gid = ""
        super().__init__()

    @property
    def speed(self):
        """Returns speed of the download in bytes/second"""
        return self.__speed

    @property
    def name(self):
        """Returns name of the download"""
        return self.__name

    def setValues(self, name, size, gid):
        self.__name = name
        self.__size = size
        self.gid = gid

    @property
    def size(self):
        """Size of download in bytes"""
        return self.__size

    @property
    def downloaded_bytes(self):
        return self.__bytes_transferred

    def onRequestFinish(self, api, request, error):
        if str(error).lower() != "no error":
            self.error = error.copy()
            LOGGER.error(f'Mega onRequestFinishError: {self.error}')
            async_to_sync(self.event_setter)
            return
        request_type = request.getType()
        if request_type == MegaRequest.TYPE_LOGIN:
            api.fetchNodes()
        elif request_type == MegaRequest.TYPE_GET_PUBLIC_NODE:
            self.public_node = request.getPublicMegaNode()
        elif request_type == MegaRequest.TYPE_FETCH_NODES:
            LOGGER.info("Fetching Root Node.")
            self.node = api.getRootNode()
            LOGGER.info(f"Node Name: {self.node.getName()}")
        if request_type not in self._NO_EVENT_ON or self.node and "cloud drive" not in self.node.getName().lower():
            async_to_sync(self.event_setter)

    def onRequestTemporaryError(self, api, request, error: MegaError):
        LOGGER.error(f'Mega Request error in {error}')
        if not self.is_cancelled:
            self.is_cancelled = True
            async_to_sync(self.listener.onDownloadError, f"RequestTempError: {error.toString()}")
        self.error = error.toString()
        async_to_sync(self.event_setter)

    def onTransferUpdate(self, api: MegaApi, transfer: MegaTransfer):
        if self.is_cancelled:
            api.cancelTransfer(transfer, None)
            async_to_sync(self.event_setter)
            return
        self.__speed = transfer.getSpeed()
        self.__bytes_transferred = transfer.getTransferredBytes()

    def onTransferFinish(self, api: MegaApi, transfer: MegaTransfer, error):
        try:
            if self.is_cancelled:
                async_to_sync(self.event_setter)
            elif transfer.isFinished() and (transfer.isFolderTransfer() or transfer.getFileName() == self.name):
                async_to_sync(self.listener.onDownloadComplete)
                async_to_sync(self.event_setter)
        except Exception as e:
            LOGGER.error(e)

    def onTransferTemporaryError(self, api, transfer, error):
        filen = transfer.getFileName()
        state = transfer.getState()
        errStr = error.toString()
        LOGGER.error(f'Mega download error in file {transfer} {filen}: {error}')
        if state in [1, 4]:
            # Sometimes MEGA (offical client) can't stream a node either and raises a temp failed error.
            # Don't break the transfer queue if transfer's in queued (1) or retrying (4) state [causes seg fault]
            return

        self.error = errStr
        if not self.is_cancelled:
            self.is_cancelled = True
            async_to_sync(self.listener.onDownloadError, f"TransferTempError: {errStr} ({filen})")
            async_to_sync(self.event_setter)

    async def event_setter(self):
        self.continue_event.set()

    async def cancel_download(self):
        self.is_cancelled = True
        await self.listener.onDownloadError("Download Canceled by user")


class AsyncExecutor:

    def __init__(self):
        self.continue_event = Event()

    async def do(self, function, args):
        self.continue_event.clear()
        await sync_to_async(function, *args)
        await self.continue_event.wait()


async def add_mega_download(mega_link, path, listener, name):
    MEGA_API_KEY = config_dict['MEGA_API_KEY']
    MEGA_EMAIL_ID = config_dict['MEGA_EMAIL_ID']
    MEGA_PASSWORD = config_dict['MEGA_PASSWORD']
    executor = AsyncExecutor()
    api = MegaApi(MEGA_API_KEY, None, None, 'mirror-leech-telegram-bot')
    folder_api = None
    mega_listener = MegaAppListener(executor.continue_event, listener)
    await sync_to_async(api.addListener, mega_listener)
    if MEGA_EMAIL_ID and MEGA_PASSWORD:
        await executor.do(api.login, (MEGA_EMAIL_ID, MEGA_PASSWORD))
    if get_mega_link_type(mega_link) == "file":
        await executor.do(api.getPublicNode, (mega_link,))
        node = mega_listener.public_node
    else:
        folder_api = MegaApi(MEGA_API_KEY, None, None, 'mltb')
        await sync_to_async(folder_api.addListener, mega_listener)
        await executor.do(folder_api.loginToFolder, (mega_link,))
        node = await sync_to_async(folder_api.authorizeNode, mega_listener.node)
    if mega_listener.error is not None:
        await sendMessage(listener.message, str(mega_listener.error))
        await sync_to_async(api.removeListener, mega_listener)
        if folder_api is not None:
            await sync_to_async(folder_api.removeListener, mega_listener)
        return
    mname = name or await sync_to_async(node.getName)
    if config_dict['STOP_DUPLICATE'] and not listener.isLeech and listener.upPath == 'gd':
        LOGGER.info('Checking File/Folder if already in Drive')
        if listener.isZip:
            mname = f"{mname}.zip"
        elif listener.extract:
            try:
                mname = get_base_name(mname)
            except:
                mname = None
        if mname is not None:
            smsg, button = await sync_to_async(GoogleDriveHelper().drive_list, mname, True)
            if smsg:
                msg1 = "File/Folder is already available in Drive.\nHere are the search results:"
                await sendMessage(listener.message, msg1, button)
                await sync_to_async(api.removeListener, mega_listener)
                if folder_api is not None:
                    await sync_to_async(folder_api.removeListener, mega_listener)
                return
    gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=8))
    mname = name or await sync_to_async(node.getName)
    size = await sync_to_async(api.getSize, node)
    all_limit = config_dict['QUEUE_ALL']
    dl_limit = config_dict['QUEUE_DOWNLOAD']
    from_queue = False
    if all_limit or dl_limit:
        added_to_queue = False
        async with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)) or (dl_limit and dl >= dl_limit):
                added_to_queue = True
                event = Event()
                queued_dl[listener.uid] = event
        if added_to_queue:
            LOGGER.info(f"Added to Queue/Download: {mname}")
            async with download_dict_lock:
                download_dict[listener.uid] = QueueStatus(mname, size, gid, listener, 'Dl')
            await listener.onDownloadStart()
            await sendStatusMessage(listener.message)
            await event.wait()
            async with download_dict_lock:
                if listener.uid not in download_dict:
                    return
            from_queue = True
    async with download_dict_lock:
        download_dict[listener.uid] = MegaDownloadStatus(mega_listener, listener.message)
    async with queue_dict_lock:
        non_queued_dl.add(listener.uid)
    await makedirs(path, exist_ok=True)
    mega_listener.setValues(mname, size, gid)
    if not from_queue:
        await listener.onDownloadStart()
        await sendStatusMessage(listener.message)
        LOGGER.info(f"Download from Mega: {mname}")
    else:
        LOGGER.info(f'Start Queued Download from Mega: {mname}')
    await executor.do(api.startDownload, (node, path, name, None, False, None))
    await sync_to_async(api.removeListener, mega_listener)
    if folder_api is not None:
        await sync_to_async(folder_api.removeListener, mega_listener)
