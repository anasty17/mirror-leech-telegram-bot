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

from bot import download_dict, download_dict_lock, BASE_URL, dispatcher, get_client, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STOP_DUPLICATE, WEB_PINCODE
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, sendStatusMessage
from bot.helper.ext_utils.bot_utils import setInterval, MirrorStatus, getDownloadByGid, get_readable_file_size, new_thread
from bot.helper.telegram_helper import button_build

LOGGER = logging.getLogger(__name__)
logging.getLogger('qbittorrentapi').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)


class QbitTorrent:
    def __init__(self):
        self.update_interval = 4
        self.client = get_client()
        self.meta_time = time.time()
        self.stalled_time = time.time()
        self.sizeChecked = False
        self.dupChecked = False
        self.is_file = False
        self.pincode = ""
        self.get_info = 0

    @new_thread
    def add_torrent(self, link, dire, listener, qbitsel):
        self.listener = listener
        self.dire = dire
        self.qbitsel = qbitsel
        try:
            if os.path.exists(link):
                self.is_file = True
                self.ext_hash = get_hash_file(link)
            else:
                self.ext_hash = get_hash_magnet(link)
            tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
            if len(tor_info) > 0:
                sendMessage("This Torrent is already in list.", listener.bot, listener.update)
                self.client.auth_log_out()
                return
            if self.is_file:
                op = self.client.torrents_add(torrent_files=[link], save_path=dire)
                os.remove(link)
            else:
                op = self.client.torrents_add(link, save_path=dire)
            time.sleep(0.3)
            if op.lower() == "ok.":
                tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
                if len(tor_info) == 0:
                    while True:
                        if time.time() - self.meta_time >= 20:
                            sendMessage("The Torrent was not added. Report when you see this error", listener.bot, listener.update)
                            self.client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
                            self.client.auth_log_out()
                            return False
                        tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
                        if len(tor_info) > 0:
                            break
            else:
                sendMessage("This is an unsupported/invalid link.", listener.bot, listener.update)
                self.client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
                self.client.auth_log_out()
                return
            tor_info = tor_info[0]
            self.ext_hash = tor_info.hash
            gid = ''.join(random.SystemRandom().choices(string.ascii_letters + string.digits, k=14))
            with download_dict_lock:
                download_dict[listener.uid] = QbDownloadStatus(gid, listener, self.ext_hash, self.client)
            LOGGER.info(f"QbitDownload started: {tor_info.name} {self.ext_hash}")
            self.updater = setInterval(self.update_interval, self.update)
            if BASE_URL is not None and qbitsel:
                if not self.is_file:
                    meta = sendMessage("Downloading Metadata, wait then you can select files or mirror Torrent file if it have low seeders", listener.bot, listener.update)
                    while True:
                        tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
                        if len(tor_info) == 0:
                            deleteMessage(listener.bot, meta)
                            return False
                        try:
                            tor_info = tor_info[0]
                            if tor_info.state in ["metaDL", "checkingResumeData"]:
                                time.sleep(1)
                            else:
                                deleteMessage(listener.bot, meta)
                                break
                        except:
                            deleteMessage(listener.bot, meta)
                            return False
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                for n in str(self.ext_hash):
                    if n.isdigit():
                        self.pincode += str(n)
                    if len(self.pincode) == 4:
                        break
                buttons = button_build.ButtonMaker()
                if WEB_PINCODE:
                    buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{self.ext_hash}")
                    buttons.sbutton("Pincode", f"pin {gid} {self.pincode}")
                else:
                     buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{self.ext_hash}?pin_code={self.pincode}")
                buttons.sbutton("Done Selecting", f"done {gid} {self.ext_hash}")
                QBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
                msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
                sendMarkup(msg, listener.bot, listener.update, QBBUTTONS)
            else:
                sendStatusMessage(listener.update, listener.bot)
        except qba.UnsupportedMediaType415Error as e:
            LOGGER.error(str(e))
            sendMessage(f"This is an unsupported/invalid link: {str(e)}", listener.bot, listener.update)
            self.client.auth_log_out()
        except Exception as e:
            sendMessage(str(e), listener.bot, listener.update)
            self.client.auth_log_out()

    def update(self):
        tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
        if len(tor_info) == 0:
            self.get_info += 1
            if self.get_info > 10:
                self.client.auth_log_out()
                self.updater.cancel()
            return
        try:
            tor_info = tor_info[0]
            if tor_info.state == "metaDL":
                self.stalled_time = time.time()
                if time.time() - self.meta_time >= 999999999: # timeout while downloading metadata
                    self.client.torrents_pause(torrent_hashes=self.ext_hash)
                    time.sleep(0.3)
                    self.listener.onDownloadError("Dead Torrent!")
                    self.client.torrents_delete(torrent_hashes=self.ext_hash)
                    self.client.auth_log_out()
                    self.updater.cancel()
            elif tor_info.state == "downloading":
                self.stalled_time = time.time()
                if STOP_DUPLICATE and not self.listener.isLeech and not self.dupChecked and os.path.isdir(f'{self.dire}'):
                    LOGGER.info('Checking File/Folder if already in Drive')
                    qbname = str(os.listdir(f'{self.dire}')[-1])
                    if qbname.endswith('.!qB'):
                        qbname = os.path.splitext(qbname)[0]
                    if self.listener.isZip:
                        qbname = qbname + ".zip"
                    if not self.listener.extract:
                        gd = GoogleDriveHelper()
                        qbmsg, button = gd.drive_list(qbname, True)
                        if qbmsg:
                            msg = "File/Folder is already available in Drive."
                            self.client.torrents_pause(torrent_hashes=self.ext_hash)
                            time.sleep(0.3)
                            self.listener.onDownloadError(msg)
                            sendMarkup("Here are the search results:", self.listener.bot, self.listener.update, button)
                            self.client.torrents_delete(torrent_hashes=self.ext_hash)
                            self.client.auth_log_out()
                            self.updater.cancel()
                            return
                    self.dupChecked = True
                if not self.sizeChecked:
                    limit = None
                    if ZIP_UNZIP_LIMIT is not None and (self.listener.isZip or self.listener.extract):
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
                            self.client.torrents_pause(torrent_hashes=self.ext_hash)
                            time.sleep(0.3)
                            self.listener.onDownloadError(f"{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}")
                            self.client.torrents_delete(torrent_hashes=self.ext_hash)
                            self.client.auth_log_out()
                            self.updater.cancel()
                    self.sizeChecked = True
            elif tor_info.state == "stalledDL":
                if time.time() - self.stalled_time >= 999999999: # timeout after downloading metadata
                    self.client.torrents_pause(torrent_hashes=self.ext_hash)
                    time.sleep(0.3)
                    self.listener.onDownloadError("Dead Torrent!")
                    self.client.torrents_delete(torrent_hashes=self.ext_hash)
                    self.client.auth_log_out()
                    self.updater.cancel()
            elif tor_info.state == "error":
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                time.sleep(0.3)
                self.listener.onDownloadError("No enough space for this torrent on device")
                self.client.torrents_delete(torrent_hashes=self.ext_hash)
                self.client.auth_log_out()
                self.updater.cancel()
            elif tor_info.state != "checkingUP" and (tor_info.state == "uploading" or \
                                                     tor_info.state.lower().endswith("up")):
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                if self.qbitsel:
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
                self.listener.onDownloadComplete()
                self.client.torrents_delete(torrent_hashes=self.ext_hash)
                self.client.auth_log_out()
                self.updater.cancel()
        except (IndexError, NameError):
            self.get_info += 1
            if self.get_info > 10:
                self.client.auth_log_out()
                self.updater.cancel()

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
