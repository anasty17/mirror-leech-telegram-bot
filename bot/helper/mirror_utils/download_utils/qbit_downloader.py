import os
import random
import string
import time
import logging
import shutil
import re
import qbittorrentapi as qba

from torrentool.api import Torrent
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot import download_dict, download_dict_lock, BASE_URL, dispatcher, get_client, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STOP_DUPLICATE, WEB_PINCODE, QB_SEED
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, sendStatusMessage, update_all_messages
from bot.helper.ext_utils.bot_utils import setInterval, MirrorStatus, getDownloadByGid, get_readable_file_size, get_readable_time
from bot.helper.telegram_helper import button_build

LOGGER = logging.getLogger(__name__)
logging.getLogger('qbittorrentapi').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


class QbitTorrent:
    def __init__(self, listener, qbitsel):
        self.update_interval = 4
        self.__listener = listener
        self.__client = get_client()
        self.__qbitsel = qbitsel
        self.meta_time = time.time()
        self.stalled_time = time.time()
        self.uploaded = False
        self.sizeChecked = False
        self.dupChecked = False
        self.recheck = False
        self.is_file = False
        self.pincode = ""
        self.get_info = 0

    def add_torrent(self, link, dire):
        self.dire = dire
        try:
            if os.path.exists(link):
                self.is_file = True
                self.ext_hash = get_hash_file(link)
            else:
                self.ext_hash = get_hash_magnet(link)
            tor_info = self.__client.torrents_info(torrent_hashes=self.ext_hash)
            if len(tor_info) > 0:
                sendMessage("This Torrent is already in list.", self.__listener.bot, self.__listener.update)
                self.__client.auth_log_out()
                return
            if self.is_file:
                op = self.__client.torrents_add(torrent_files=[link], save_path=dire)
                os.remove(link)
            else:
                op = self.__client.torrents_add(link, save_path=dire)
            time.sleep(0.3)
            if op.lower() == "ok.":
                tor_info = self.__client.torrents_info(torrent_hashes=self.ext_hash)
                if len(tor_info) == 0:
                    while True:
                        if time.time() - self.meta_time >= 20:
                            ermsg = "The Torrent was not added. Report when you see this error"
                            sendMessage(ermsg, self.__listener.bot, self.__listener.update)
                            self.__client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
                            self.__client.auth_log_out()
                            return
                        tor_info = self.__client.torrents_info(torrent_hashes=self.ext_hash)
                        if len(tor_info) > 0:
                            break
            else:
                sendMessage("This is an unsupported/invalid link.", self.__listener.bot, self.__listener.update)
                self.__client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
                self.__client.auth_log_out()
                return
            tor_info = tor_info[0]
            self.ext_hash = tor_info.hash
            self.gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=14))
            with download_dict_lock:
                download_dict[self.__listener.uid] = QbDownloadStatus(self.gid, self.__listener, self.ext_hash, self.__client, self.__qbitsel)
            LOGGER.info(f"QbitDownload started: {tor_info.name} - Hash: {self.ext_hash}")
            self.updater = setInterval(self.update_interval, self.update)
            if BASE_URL is not None and self.__qbitsel:
                if not self.is_file:
                    metamsg = "Downloading Metadata, wait then you can select files or mirror torrent file"
                    meta = sendMessage(metamsg, self.__listener.bot, self.__listener.update)
                    while True:
                        tor_info = self.__client.torrents_info(torrent_hashes=self.ext_hash)
                        if len(tor_info) == 0:
                            deleteMessage(self.__listener.bot, meta)
                            return
                        try:
                            tor_info = tor_info[0]
                            if tor_info.state in ["metaDL", "checkingResumeData"]:
                                time.sleep(1)
                            else:
                                deleteMessage(self.__listener.bot, meta)
                                break
                        except:
                            deleteMessage(self.__listener.bot, meta)
                            return
                time.sleep(0.5)
                self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                for n in str(self.ext_hash):
                    if n.isdigit():
                        self.pincode += str(n)
                    if len(self.pincode) == 4:
                        break
                buttons = button_build.ButtonMaker()
                if WEB_PINCODE:
                    buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{self.ext_hash}")
                    buttons.sbutton("Pincode", f"pin {self.gid} {self.pincode}")
                else:
                    buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{self.ext_hash}?pin_code={self.pincode}")
                buttons.sbutton("Done Selecting", f"done {self.gid} {self.ext_hash}")
                QBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
                msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
                sendMarkup(msg, self.__listener.bot, self.__listener.update, QBBUTTONS)
            else:
                sendStatusMessage(self.__listener.update, self.__listener.bot)
        except qba.UnsupportedMediaType415Error as e:
            LOGGER.error(str(e))
            sendMessage(f"This is an unsupported/invalid link: {str(e)}", self.__listener.bot, self.__listener.update)
            self.__client.auth_log_out()
        except Exception as e:
            sendMessage(str(e), self.__listener.bot, self.__listener.update)
            self.__client.auth_log_out()

    def update(self):
        tor_info = self.__client.torrents_info(torrent_hashes=self.ext_hash)
        if len(tor_info) == 0:
            self.get_info += 1
            if self.get_info > 10:
                self.__client.auth_log_out()
                self.updater.cancel()
            return
        self.get_info = 0
        try:
            tor_info = tor_info[0]
            if tor_info.state == "metaDL":
                self.stalled_time = time.time()
                if time.time() - self.meta_time >= 999999999: # timeout while downloading metadata
                    self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                    time.sleep(0.3)
                    self.__listener.onDownloadError("Dead Torrent!")
                    self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                    self.__client.auth_log_out()
                    self.updater.cancel()
            elif tor_info.state == "downloading":
                self.stalled_time = time.time()
                if STOP_DUPLICATE and not self.__listener.isLeech and not self.dupChecked and os.path.isdir(f'{self.dire}'):
                    LOGGER.info('Checking File/Folder if already in Drive')
                    qbname = str(os.listdir(f'{self.dire}')[-1])
                    if qbname.endswith('.!qB'):
                        qbname = os.path.splitext(qbname)[0]
                    if self.__listener.isZip:
                        qbname = qbname + ".zip"
                    if not self.__listener.extract:
                        gd = GoogleDriveHelper()
                        qbmsg, button = gd.drive_list(qbname, True)
                        if qbmsg:
                            msg = "File/Folder is already available in Drive."
                            self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                            time.sleep(0.3)
                            self.__listener.onDownloadError(msg)
                            sendMarkup("Here are the search results:", self.__listener.bot, self.__listener.update, button)
                            self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                            self.__client.auth_log_out()
                            self.updater.cancel()
                            return
                    self.dupChecked = True
                if not self.sizeChecked:
                    limit = None
                    if ZIP_UNZIP_LIMIT is not None and (self.__listener.isZip or self.__listener.extract):
                        mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                        limit = ZIP_UNZIP_LIMIT
                    elif TORRENT_DIRECT_LIMIT is not None:
                        mssg = f'Torrent limit is {TORRENT_DIRECT_LIMIT}GB'
                        limit = TORRENT_DIRECT_LIMIT
                    if limit is not None:
                        LOGGER.info('Checking File/Folder Size...')
                        time.sleep(1)
                        size = tor_info.size
                        if size > limit * 1024**3:
                            self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                            time.sleep(0.3)
                            self.__listener.onDownloadError(f"{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}")
                            self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                            self.__client.auth_log_out()
                            self.updater.cancel()
                    self.sizeChecked = True
            elif tor_info.state == "stalledDL":
                if not self.recheck and 0.99989999999999999 < tor_info.progress < 1:
                    LOGGER.info(f"Force recheck - Name: {tor_info.name} Hash: {self.ext_hash} Downloaded Bytes: {tor_info.downloaded} Size: {tor_info.size} Total Size: {tor_info.total_size}")
                    self.__client.torrents_recheck(torrent_hashes=self.ext_hash)
                    self.recheck = True
                elif time.time() - self.stalled_time >= 999999999: # timeout after downloading metadata
                    self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                    time.sleep(0.3)
                    self.__listener.onDownloadError("Dead Torrent!")
                    self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                    self.__client.auth_log_out()
                    self.updater.cancel()
            elif tor_info.state == "missingFiles":
                self.__client.torrents_recheck(torrent_hashes=self.ext_hash)
            elif tor_info.state == "error":
                self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                time.sleep(0.3)
                self.__listener.onDownloadError("No enough space for this torrent on device")
                self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                self.__client.auth_log_out()
                self.updater.cancel()
            elif tor_info.state in ["uploading", "queuedUP", "stalledUP", "forcedUP"] and not self.uploaded:
                self.uploaded = True
                if not QB_SEED:
                    self.__client.torrents_pause(torrent_hashes=self.ext_hash)
                if self.__qbitsel:
                    for dirpath, subdir, files in os.walk(f"{self.dire}", topdown=False):
                        for filee in files:
                            if filee.endswith(".!qB") or filee.endswith('.parts') and filee.startswith('.'):
                                os.remove(os.path.join(dirpath, filee))
                        for folder in subdir:
                            if folder == ".unwanted":
                                shutil.rmtree(os.path.join(dirpath, folder))
                    for dirpath, subdir, files in os.walk(f"{self.dire}", topdown=False):
                        if not os.listdir(dirpath):
                            os.rmdir(dirpath)
                self.__listener.onDownloadComplete()
                if QB_SEED:
                    with download_dict_lock:
                        download_dict[self.__listener.uid] = QbDownloadStatus(self.gid, self.__listener, self.ext_hash, self.__client, self.__qbitsel)
                    update_all_messages()
                    LOGGER.info(f"Seeding started: {tor_info.name}")
                else:
                    self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                    self.__client.auth_log_out()
                    self.updater.cancel()
            elif tor_info.state == 'pausedUP' and QB_SEED:
                self.__listener.onUploadError(f"Seeding stopped with Ratio: {round(tor_info.ratio, 3)} and Time: {get_readable_time(tor_info.seeding_time)}")
                self.__client.torrents_delete(torrent_hashes=self.ext_hash)
                self.__client.auth_log_out()
                self.updater.cancel()
        except:
            pass

def get_confirm(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    qbdl = getDownloadByGid(data[1])
    if qbdl is None:
        query.answer(text="This task has been cancelled!", show_alert=True)
        query.message.delete()
    elif user_id != qbdl.listener.message.from_user.id:
        query.answer(text="Don't waste your time!", show_alert=True)
    elif data[0] == "pin":
        query.answer(text=data[2], show_alert=True)
    elif data[0] == "done":
        query.answer()
        qbdl.client.torrents_resume(torrent_hashes=data[2])
        sendStatusMessage(qbdl.listener.update, qbdl.listener.bot)
        query.message.delete()

def get_hash_magnet(mgt):
    if mgt.startswith('magnet:'):
        mHash = re.search(r'(?<=xt=urn:btih:)[a-zA-Z0-9]+', mgt).group(0)
        return mHash.lower()

def get_hash_file(path):
    tr = Torrent.from_file(path)
    mgt = tr.magnet_link
    return get_hash_magnet(mgt)


pin_handler = CallbackQueryHandler(get_confirm, pattern="pin", run_async=True)
done_handler = CallbackQueryHandler(get_confirm, pattern="done", run_async=True)
dispatcher.add_handler(pin_handler)
dispatcher.add_handler(done_handler)
