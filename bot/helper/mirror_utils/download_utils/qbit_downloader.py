# Implement By - @anasty17 (https://github.com/SlamDevs/slam-mirrorbot/commit/0bfba523f095ab1dccad431d72561e0e002e7a59)
# (c) https://github.com/SlamDevs/slam-mirrorbot
# All rights reserved

import os
import random
import string
import time
import logging
import shutil

import qbittorrentapi as qba
from urllib.parse import urlparse, parse_qs
from torrentool.api import Torrent
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot import download_dict, download_dict_lock, BASE_URL, dispatcher, get_client, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STOP_DUPLICATE
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import *
from bot.helper.ext_utils.bot_utils import setInterval, new_thread, MirrorStatus, getDownloadByGid, get_readable_file_size
from bot.helper.telegram_helper import button_build

LOGGER = logging.getLogger(__name__)
logging.getLogger('qbittorrentapi').setLevel(logging.ERROR)
logging.getLogger('requests').setLevel(logging.ERROR)
logging.getLogger('urllib3').setLevel(logging.ERROR)

class QbitTorrent:


    def __init__(self):
        self.update_interval = 2
        self.meta_time = time.time()
        self.stalled_time = time.time()
        self.sizechecked = False
        self.dupchecked = False

    @new_thread
    def add_torrent(self, link, dire, listener, qbitsel):
        self.client = get_client()
        self.listener = listener
        self.dire = dire
        self.qbitsel = qbitsel
        is_file = False
        count = 0
        pincode = ""
        try:
            if os.path.exists(link):
                is_file = True
                self.ext_hash = get_hash_file(link)
            else:
                self.ext_hash = get_hash_magnet(link)
            tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
            if len(tor_info) > 0:
                sendMessage("This Torrent is already in list.", listener.bot, listener.update)
                self.client.auth_log_out()
                return
            if is_file:
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
            LOGGER.info(f"QbitDownload started: {tor_info.name}")
            self.updater = setInterval(self.update_interval, self.update)
            if BASE_URL is not None and qbitsel:
                if not is_file:
                    meta = sendMessage("Downloading Metadata...Please wait then you can select files or mirror Torrent file if it have low seeders", listener.bot, listener.update)
                    while True:
                            tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
                            if len(tor_info) == 0:
                                deleteMessage(listener.bot, meta)
                                return False
                            try:
                                tor_info = tor_info[0]
                                if tor_info.state == "metaDL" or tor_info.state == "checkingResumeData":
                                    time.sleep(1)
                                else:
                                    deleteMessage(listener.bot, meta)
                                    break
                            except:
                                deleteMessage(listener.bot, meta)
                                return False
                time.sleep(0.5)
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                for n in str(self.ext_hash):
                    if n.isdigit():
                        pincode += str(n)
                        count += 1
                    if count == 4:
                        break
                URL = f"{BASE_URL}/app/files/{self.ext_hash}"
                pindata = f"pin {gid} {pincode}"
                donedata = f"done {gid} {self.ext_hash}"
                buttons = button_build.ButtonMaker()
                buttons.buildbutton("Select Files", URL)
                buttons.sbutton("Pincode", pindata)
                buttons.sbutton("Done Selecting", donedata)
                QBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
                msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
                sendMarkup(msg, listener.bot, listener.update, QBBUTTONS)
            else:
                sendStatusMessage(listener.update, listener.bot)
        except qba.UnsupportedMediaType415Error as e:
            LOGGER.error(str(e))
            sendMessage("This is an unsupported/invalid link: {str(e)}", listener.bot, listener.update)
            self.client.torrents_delete(torrent_hashes=self.ext_hash, delete_files=True)
            self.client.auth_log_out()
        except Exception as e:
            LOGGER.error(str(e))
            sendMessage(str(e), listener.bot, listener.update)
            self.client.auth_log_out()


    def update(self):
        tor_info = self.client.torrents_info(torrent_hashes=self.ext_hash)
        if len(tor_info) == 0:
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
                if STOP_DUPLICATE and not self.listener.isLeech and not self.dupchecked and os.path.isdir(f'{self.dire}'):
                    LOGGER.info('Checking File/Folder if already in Drive')
                    qbname = str(os.listdir(f'{self.dire}')[0])
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
                    self.dupchecked = True
                if not self.sizechecked:
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
                    self.sizechecked = True
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
            elif tor_info.state == "uploading" or tor_info.state.lower().endswith("up"):
                self.client.torrents_pause(torrent_hashes=self.ext_hash)
                if self.qbitsel:
                    for dirpath, subdir, files in os.walk(f"{self.dire}", topdown=False):
                        for filee in files:
                            if filee.endswith(".!qB"):
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
        except:
            self.client.auth_log_out()
            self.updater.cancel()


def get_confirm(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    qdl = getDownloadByGid(data[1])
    if qdl is None:
        query.answer(text="This task has been cancelled!", show_alert=True)
        query.message.delete()

    elif user_id != qdl.listener.message.from_user.id:
        query.answer(text="Don't waste your time!", show_alert=True)
    elif data[0] == "pin":
        query.answer(text=data[2], show_alert=True)
    elif data[0] == "done":
        query.answer()
        qdl.client.torrents_resume(torrent_hashes=data[2])
        sendStatusMessage(qdl.listener.update, qdl.listener.bot)
        query.message.delete()


def get_hash_magnet(mgt):
    if mgt.startswith('magnet:'):
        _, _, _, _, query, _ = urlparse(mgt)
    qs = parse_qs(query)
    v = qs.get('xt', None)
    if v is None or v == []:
        LOGGER.error('Invalid magnet URI: no "xt" query parameter.')
        return
    v = v[0]
    if not v.startswith('urn:btih:'):
        LOGGER.error('Invalid magnet URI: "xt" value not valid for BitTorrent.')
        return
    mgt = v[len('urn:btih:'):]
    return mgt.lower()


def get_hash_file(path):
    tr = Torrent.from_file(path)
    mgt = tr.magnet_link
    return get_hash_magnet(mgt)


pin_handler = CallbackQueryHandler(get_confirm, pattern="pin", run_async=True)
done_handler = CallbackQueryHandler(get_confirm, pattern="done", run_async=True)
dispatcher.add_handler(pin_handler)
dispatcher.add_handler(done_handler)
