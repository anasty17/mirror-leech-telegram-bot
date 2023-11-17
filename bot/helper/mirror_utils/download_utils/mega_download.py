from secrets import token_urlsafe
from aiofiles.os import makedirs
from threading import Event
from mega import (
    MegaApi,
    MegaListener,
    MegaRequest,
    MegaTransfer,
    MegaError,
)

from bot import (
    LOGGER,
    config_dict,
    task_dict_lock,
    task_dict,
    non_queued_dl,
    queue_dict_lock,
)
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import sync_to_async
from bot.helper.ext_utils.links_utils import get_mega_link_type
from bot.helper.mirror_utils.status_utils.mega_download_status import MegaDownloadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.ext_utils.task_manager import is_queued, stop_duplicate_check


class MegaAppListener(MegaListener):
    _NO_EVENT_ON = (MegaRequest.TYPE_LOGIN, MegaRequest.TYPE_FETCH_NODES)
    NO_ERROR = "no error"

    def __init__(self, continue_event: Event, listener):
        self.continue_event = continue_event
        self.node = None
        self.public_node = None
        self.listener = listener
        self.is_cancelled = False
        self.error = None
        self.completed = False
        self.isFile = False
        self._bytes_transferred = 0
        self._speed = 0
        self._name = ""
        super().__init__()

    @property
    def speed(self):
        return self._speed

    @property
    def downloaded_bytes(self):
        return self._bytes_transferred

    def onRequestFinish(self, api: MegaApi, request: MegaRequest, error):
        if self.is_cancelled:
            return
        if str(error).lower() != "no error":
            self.error = error.copy()
            LOGGER.error(f"Mega onRequestFinishError: {self.error}")
            self.continue_event.set()
            return
        request_type = request.getType()
        if request_type == MegaRequest.TYPE_LOGIN:
            api.fetchNodes()
        elif request_type == MegaRequest.TYPE_GET_PUBLIC_NODE:
            self.public_node = request.getPublicMegaNode()
            self._name = self.public_node.getName()
        elif request_type == MegaRequest.TYPE_FETCH_NODES:
            LOGGER.info("Fetching Root Node.")
            self.node = api.getRootNode()
            self._name = self.node.getName()
            LOGGER.info(f"Node Name: {self.node.getName()}")
        if (
            request_type not in self._NO_EVENT_ON
            or self.node
            and "cloud drive" not in self._name.lower()
        ):
            self.continue_event.set()

    def onRequestTemporaryError(self, api, request, error: MegaError):
        LOGGER.error(f"Mega Request error in {error}")
        if not self.is_cancelled:
            self.is_cancelled = True
        self.error = f"RequestTempError: {error.toString()}"
        self.continue_event.set()

    def onTransferUpdate(self, api: MegaApi, transfer: MegaTransfer):
        if self.is_cancelled:
            api.cancelTransfer(transfer, None)
            self.continue_event.set()
            return
        self._speed = transfer.getSpeed()
        self._bytes_transferred = transfer.getTransferredBytes()

    def onTransferFinish(self, api, transfer: MegaTransfer, error):
        try:
            if self.is_cancelled:
                self.continue_event.set()
            elif transfer.isFinished() and (transfer.isFolderTransfer() or self.isFile):
                self.completed = True
                self.continue_event.set()
        except Exception as e:
            LOGGER.error(e)

    def onTransferTemporaryError(self, api, transfer: MegaTransfer, error: MegaError):
        filen = transfer.getFileName()
        state = transfer.getState()
        errStr = error.toString()
        LOGGER.error(f"Mega download error in file {transfer} {filen}: {error}")
        if state in [1, 4]:
            # Sometimes MEGA (offical client) can't stream a node either and raises a temp failed error.
            # Don't break the transfer queue if transfer's in queued (1) or retrying (4) state [causes seg fault]
            return

        self.error = f"TransferTempError: {errStr} ({filen}"
        if not self.is_cancelled:
            self.is_cancelled = True
            self.continue_event.set()

    async def cancel_task(self):
        self.is_cancelled = True
        await self.listener.onDownloadError("Download Canceled by user")


class AsyncExecutor:
    def __init__(self):
        self.continue_event = Event()

    def do(self, function, args):
        self.continue_event.clear()
        function(*args)
        self.continue_event.wait()


async def add_mega_download(listener, path):
    MEGA_EMAIL = config_dict["MEGA_EMAIL"]
    MEGA_PASSWORD = config_dict["MEGA_PASSWORD"]

    executor = AsyncExecutor()
    api = MegaApi(None, None, None, "mirror-leech-telegram-bot")
    folder_api = None

    mega_listener = MegaAppListener(executor.continue_event, listener)
    api.addListener(mega_listener)

    if MEGA_EMAIL and MEGA_PASSWORD:
        await sync_to_async(executor.do, api.login, (MEGA_EMAIL, MEGA_PASSWORD))

    if get_mega_link_type(listener.link) == "file":
        await sync_to_async(executor.do, api.getPublicNode, (listener.link,))
        node = mega_listener.public_node
        mega_listener.isFile = True
    else:
        folder_api = MegaApi(None, None, None, "mirror-leech-telegram-bot")
        folder_api.addListener(mega_listener)
        await sync_to_async(executor.do, folder_api.loginToFolder, (listener.link,))
        node = await sync_to_async(folder_api.authorizeNode, mega_listener.node)
    if mega_listener.error is not None:
        await sendMessage(listener.message, str(mega_listener.error))
        await sync_to_async(executor.do, api.logout, ())
        if folder_api is not None:
            await sync_to_async(executor.do, folder_api.logout, ())
        return

    listener.name = listener.name or node.getName()
    msg, button = await stop_duplicate_check(listener)
    if msg:
        await sendMessage(listener.message, msg, button)
        await sync_to_async(executor.do, api.logout, ())
        if folder_api is not None:
            await sync_to_async(executor.do, folder_api.logout, ())
        return

    gid = token_urlsafe(8)
    size = api.getSize(node)

    add_to_queue, event = await is_queued(listener.mid)
    if add_to_queue:
        LOGGER.info(f"Added to Queue/Download: {listener.name}")
        async with task_dict_lock:
            task_dict[listener.mid] = QueueStatus(listener, size, gid, "Dl")
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)
        await event.wait()
        async with task_dict_lock:
            if listener.mid not in task_dict:
                await sync_to_async(executor.do, api.logout, ())
                if folder_api is not None:
                    await sync_to_async(executor.do, folder_api.logout, ())
                return
        from_queue = True
        LOGGER.info(f"Start Queued Download from Mega: {listener.name}")
    else:
        from_queue = False

    async with task_dict_lock:
        task_dict[listener.mid] = MegaDownloadStatus(listener, mega_listener, size, gid)
    async with queue_dict_lock:
        non_queued_dl.add(listener.mid)

    if from_queue:
        LOGGER.info(f"Start Queued Download from Mega: {listener.name}")
    else:
        await listener.onDownloadStart()
        if listener.multi <= 1:
            await sendStatusMessage(listener.message)
        LOGGER.info(f"Download from Mega: {listener.name}")

    await makedirs(path, exist_ok=True)
    await sync_to_async(
        executor.do, api.startDownload, (node, path, listener.name, None, False, None)
    )
    await sync_to_async(executor.do, api.logout, ())
    if folder_api is not None:
        await sync_to_async(executor.do, folder_api.logout, ())

    if mega_listener.completed:
        await listener.onDownloadComplete()
    elif (error := mega_listener.error) and mega_listener.is_cancelled:
        await listener.onDownloadError(error)
