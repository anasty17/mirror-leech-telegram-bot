from bot import LOGGER, MEGA_API_KEY, download_dict_lock, download_dict, MEGA_EMAIL_ID, MEGA_PASSWORD
import threading
from mega import (MegaApi, MegaListener, MegaRequest, MegaTransfer, MegaError)
from bot.helper.telegram_helper.message_utils import update_all_messages
import os
from bot.helper.ext_utils.bot_utils import new_thread, get_mega_link_type
from bot.helper.mirror_utils.status_utils.mega_download_status import MegaDownloadStatus
import random
import string

class MegaDownloaderException(Exception):
    pass


class MegaAppListener(MegaListener):
    _NO_EVENT_ON = (MegaRequest.TYPE_LOGIN,MegaRequest.TYPE_FETCH_NODES)
    NO_ERROR = "no error"

    def __init__(self, continue_event: threading.Event, listener):
        self.continue_event = continue_event
        self.node = None
        self.public_node = None
        self.listener = listener
        self.uid = listener.uid
        self.__bytes_transferred = 0
        self.is_cancelled = False
        self.__speed = 0
        self.__name = ''
        self.__size = 0
        self.error = None
        self.gid = ""
        super(MegaAppListener, self).__init__()

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

    def onRequestStart(self, api, request):
        LOGGER.info('Request start ({})'.format(request))

    def onRequestFinish(self, api, request, error):
        LOGGER.info('Mega Request finished ({}); Result: {}'
                    .format(request, error))

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
            self.continue_event.set()

    def onRequestTemporaryError(self, api, request, error: MegaError):
        LOGGER.info(f'Mega Request error in {error}')
        if not self.is_cancelled:
            self.listener.onDownloadError("RequestTempError: " + error.toString())
            self.is_cancelled = True
        self.error = error.toString()
        self.continue_event.set()

    def onTransferStart(self, api: MegaApi, transfer: MegaTransfer):
        LOGGER.info(f"Transfer Started: {transfer.getFileName()}")

    def onTransferUpdate(self, api: MegaApi, transfer: MegaTransfer):
        if self.is_cancelled:
            api.cancelTransfer(transfer, None)
        self.__speed = transfer.getSpeed()
        self.__bytes_transferred = transfer.getTransferredBytes()

    def onTransferFinish(self, api: MegaApi, transfer: MegaTransfer, error):
        try:
            LOGGER.info(f'Transfer finished ({transfer}); Result: {transfer.getFileName()}')
            if transfer.isFolderTransfer() and transfer.isFinished() or transfer.getFileName() == self.name and not self.is_cancelled:
                self.listener.onDownloadComplete()
                self.continue_event.set()
        except Exception as e:
            LOGGER.error(e)

    def onTransferTemporaryError(self, api, transfer, error):
        LOGGER.info(f'Mega download error in file {transfer} {transfer.getFileName()}: {error}')
        self.error = error.toString()
        if not self.is_cancelled:
            self.is_cancelled = True
            self.listener.onDownloadError("TransferTempError: "+self.error)

    def cancel_download(self):
        self.is_cancelled = True
        self.listener.onDownloadError("Download Canceled by user")


class AsyncExecutor:

    def __init__(self):
        self.continue_event = threading.Event()

    def do(self, function, args):
        self.continue_event.clear()
        function(*args)
        self.continue_event.wait()


class MegaDownloadHelper:
    def __init__(self):
        pass

    @staticmethod
    @new_thread
    def add_download(mega_link: str, path: str, listener):
        if MEGA_API_KEY is None:
            raise MegaDownloaderException('Mega API KEY not provided! Cannot mirror mega links')
        executor = AsyncExecutor()
        api = MegaApi(MEGA_API_KEY, None, None, 'telegram-mirror-bot')
        mega_listener = MegaAppListener(executor.continue_event, listener)
        with download_dict_lock:
            download_dict[listener.uid] = MegaDownloadStatus(mega_listener, listener)
        os.makedirs(path)
        api.addListener(mega_listener)
        if MEGA_EMAIL_ID is not None and MEGA_PASSWORD is not None:
            executor.do(api.login, (MEGA_EMAIL_ID, MEGA_PASSWORD))
        link_type = get_mega_link_type(mega_link)
        if link_type == "file":
            executor.do(api.getPublicNode, (mega_link,))
            node = mega_listener.public_node
        else:
            LOGGER.info("Logging into mega folder")
            folder_api = MegaApi(MEGA_API_KEY,None,None,'TgBot')
            folder_api.addListener(mega_listener)
            executor.do(folder_api.loginToFolder, (mega_link,))
            node = folder_api.authorizeNode(mega_listener.node)
        if mega_listener.error is not None:
            return listener.onDownloadError(str(mega_listener.error))
        gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=8))
        mega_listener.setValues(node.getName(), api.getSize(node), gid)
        executor.do(api.startDownload,(node,path))
