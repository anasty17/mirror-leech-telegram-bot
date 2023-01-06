from requests import utils as rutils
from re import search as re_search
from time import sleep
from os import path as ospath, remove as osremove, listdir, walk, rename, makedirs
from subprocess import Popen
from html import escape
from shutil import move

from bot import Interval, aria2, DOWNLOAD_DIR, download_dict, download_dict_lock, LOGGER, DATABASE_URL, MAX_SPLIT_SIZE, config_dict, status_reply_dict_lock, user_data, non_queued_up, non_queued_dl, queued_up, queued_dl, queue_dict_lock
from bot.helper.ext_utils.fs_utils import get_base_name, get_path_size, split_file, clean_download, clean_target
from bot.helper.ext_utils.exceptions import NotSupportedExtractionArchive
from bot.helper.ext_utils.queued_starter import start_from_queued
from bot.helper.mirror_utils.status_utils.extract_status import ExtractStatus
from bot.helper.mirror_utils.status_utils.zip_status import ZipStatus
from bot.helper.mirror_utils.status_utils.split_status import SplitStatus
from bot.helper.mirror_utils.status_utils.upload_status import UploadStatus
from bot.helper.mirror_utils.status_utils.tg_upload_status import TgUploadStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.mirror_utils.upload_utils.pyrogramEngine import TgUploader
from bot.helper.telegram_helper.message_utils import sendMessage, delete_all_messages, update_all_messages
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger


class MirrorLeechListener:
    def __init__(self, bot, message, isZip=False, extract=False, isQbit=False, isLeech=False, pswd=None, tag=None, select=False, seed=False, sameDir={}):
        self.bot = bot
        self.message = message
        self.uid = message.message_id
        self.extract = extract
        self.isZip = isZip
        self.isQbit = isQbit
        self.isLeech = isLeech
        self.pswd = pswd
        self.tag = tag
        self.seed = seed
        self.newDir = ""
        self.dir = f"{DOWNLOAD_DIR}{self.uid}"
        self.select = select
        self.isPrivate = message.chat.type in ['private', 'group']
        self.suproc = None
        self.queuedUp = False
        self.sameDir = sameDir

    def clean(self):
        try:
            with status_reply_dict_lock:
                Interval[0].cancel()
                Interval.clear()
            aria2.purge()
            delete_all_messages()
        except:
            pass

    def onDownloadStart(self):
        if not self.isPrivate and config_dict['INCOMPLETE_TASK_NOTIFIER'] and DATABASE_URL:
            DbManger().add_incomplete_task(self.message.chat.id, self.message.link, self.tag)

    def onDownloadComplete(self):
        with download_dict_lock:
            if len(self.sameDir) > 1:
                self.sameDir.remove(self.uid)
                folder_name = listdir(self.dir)[-1]
                path = f"{self.dir}/{folder_name}"
                des_path = f"{DOWNLOAD_DIR}{list(self.sameDir)[0]}/{folder_name}"
                makedirs(des_path, exist_ok=True)
                for subdir in listdir(path):
                    sub_path = f"{self.dir}/{folder_name}/{subdir}"
                    if subdir in listdir(des_path):
                        sub_path = rename(sub_path, f"{self.dir}/{folder_name}/1-{subdir}")
                    move(sub_path, des_path)
                del download_dict[self.uid]
                return
            download = download_dict[self.uid]
            name = str(download.name()).replace('/', '')
            gid = download.gid()
        LOGGER.info(f"Download completed: {name}")
        if name == "None" or self.isQbit or not ospath.exists(f"{self.dir}/{name}"):
            name = listdir(self.dir)[-1]
        m_path = f"{self.dir}/{name}"
        size = get_path_size(m_path)
        with queue_dict_lock:
            if self.uid in non_queued_dl:
                non_queued_dl.remove(self.uid)
        start_from_queued()
        user_dict = user_data.get(self.message.from_user.id, {})
        if self.isZip:
            if self.seed and self.isLeech:
                self.newDir = f"{self.dir}10000"
                path = f"{self.newDir}/{name}.zip"
            else:
                path = f"{m_path}.zip"
            with download_dict_lock:
                download_dict[self.uid] = ZipStatus(name, size, gid, self)
            LEECH_SPLIT_SIZE = user_dict.get('split_size', False) or config_dict['LEECH_SPLIT_SIZE']
            if self.pswd is not None:
                if self.isLeech and int(size) > LEECH_SPLIT_SIZE:
                    LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}.0*')
                    self.suproc = Popen(["7z", f"-v{LEECH_SPLIT_SIZE}b", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
                else:
                    LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}')
                    self.suproc = Popen(["7z", "a", "-mx=0", f"-p{self.pswd}", path, m_path])
            elif self.isLeech and int(size) > LEECH_SPLIT_SIZE:
                LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}.0*')
                self.suproc = Popen(["7z", f"-v{LEECH_SPLIT_SIZE}b", "a", "-mx=0", path, m_path])
            else:
                LOGGER.info(f'Zip: orig_path: {m_path}, zip_path: {path}')
                self.suproc = Popen(["7z", "a", "-mx=0", path, m_path])
            self.suproc.wait()
            if self.suproc.returncode == -9:
                return
            elif not self.seed:
                clean_target(m_path)
        elif self.extract:
            try:
                if ospath.isfile(m_path):
                    path = get_base_name(m_path)
                LOGGER.info(f"Extracting: {name}")
                with download_dict_lock:
                    download_dict[self.uid] = ExtractStatus(name, size, gid, self)
                if ospath.isdir(m_path):
                    if self.seed:
                        self.newDir = f"{self.dir}10000"
                        path = f"{self.newDir}/{name}"
                    else:
                        path = m_path
                    for dirpath, subdir, files in walk(m_path, topdown=False):
                        for file_ in files:
                            if re_search(r'\.part0*1\.rar$|\.7z\.0*1$|\.zip\.0*1$|\.zip$|\.7z$|^.(?!.*\.part\d+\.rar)(?=.*\.rar$)', file_):
                                f_path = ospath.join(dirpath, file_)
                                t_path = dirpath.replace(self.dir, self.newDir) if self.seed else dirpath
                                if self.pswd is not None:
                                    self.suproc = Popen(["7z", "x", f"-p{self.pswd}", f_path, f"-o{t_path}", "-aot"])
                                else:
                                    self.suproc = Popen(["7z", "x", f_path, f"-o{t_path}", "-aot"])
                                self.suproc.wait()
                                if self.suproc.returncode == -9:
                                    return
                                elif self.suproc.returncode != 0:
                                    LOGGER.error('Unable to extract archive splits!')
                        if not self.seed and self.suproc is not None and self.suproc.returncode == 0:
                            for file_ in files:
                                if re_search(r'\.r\d+$|\.7z\.\d+$|\.z\d+$|\.zip\.\d+$|\.zip$|\.rar$|\.7z$', file_):
                                    del_path = ospath.join(dirpath, file_)
                                    try:
                                        osremove(del_path)
                                    except:
                                        return
                else:
                    if self.seed and self.isLeech:
                        self.newDir = f"{self.dir}10000"
                        path = path.replace(self.dir, self.newDir)
                    if self.pswd is not None:
                        self.suproc = Popen(["7z", "x", f"-p{self.pswd}", m_path, f"-o{path}", "-aot"])
                    else:
                        self.suproc = Popen(["7z", "x", m_path, f"-o{path}", "-aot"])
                    self.suproc.wait()
                    if self.suproc.returncode == -9:
                        return
                    elif self.suproc.returncode == 0:
                        LOGGER.info(f"Extracted Path: {path}")
                        if not self.seed:
                            try:
                                osremove(m_path)
                            except:
                                return
                    else:
                        LOGGER.error('Unable to extract archive! Uploading anyway')
                        self.newDir = ""
                        path = m_path
            except NotSupportedExtractionArchive:
                LOGGER.info("Not any valid archive, uploading file as it is.")
                self.newDir = ""
                path = m_path
        else:
            path = m_path
        up_dir, up_name = path.rsplit('/', 1)
        size = get_path_size(up_dir)
        if self.isLeech:
            m_size = []
            o_files = []
            if not self.isZip:
                checked = False
                LEECH_SPLIT_SIZE = user_dict.get('split_size', False) or config_dict['LEECH_SPLIT_SIZE']
                for dirpath, subdir, files in walk(up_dir, topdown=False):
                    for file_ in files:
                        f_path = ospath.join(dirpath, file_)
                        f_size = ospath.getsize(f_path)
                        if f_size > LEECH_SPLIT_SIZE:
                            if not checked:
                                checked = True
                                with download_dict_lock:
                                    download_dict[self.uid] = SplitStatus(up_name, size, gid, self)
                                LOGGER.info(f"Splitting: {up_name}")
                            res = split_file(f_path, f_size, file_, dirpath, LEECH_SPLIT_SIZE, self)
                            if not res:
                                return
                            if res == "errored":
                                if f_size <= MAX_SPLIT_SIZE:
                                    continue
                                try:
                                    osremove(f_path)
                                except:
                                    return
                            elif not self.seed or self.newDir:
                                try:
                                    osremove(f_path)
                                except:
                                    return
                            else:
                                m_size.append(f_size)
                                o_files.append(file_)

        up_limit = config_dict['QUEUE_UPLOAD']
        all_limit = config_dict['QUEUE_ALL']
        added_to_queue = False
        with queue_dict_lock:
            dl = len(non_queued_dl)
            up = len(non_queued_up)
            if (all_limit and dl + up >= all_limit and (not up_limit or up >= up_limit)) or (up_limit and up >= up_limit):
                added_to_queue = True
                LOGGER.info(f"Added to Queue/Upload: {name}")
                queued_up[self.uid] = [self]
        if added_to_queue:
            with download_dict_lock:
                download_dict[self.uid] = QueueStatus(name, size, gid, self, 'Up')
                self.queuedUp = True
            while self.queuedUp:
                sleep(1)
            with download_dict_lock:
                if self.uid not in download_dict.keys():
                    return
            LOGGER.info(f'Start from Queued/Upload: {name}')
        with queue_dict_lock:
            non_queued_up.add(self.uid)

        if self.isLeech:
            size = get_path_size(up_dir)
            for s in m_size:
                size = size - s
            LOGGER.info(f"Leech Name: {up_name}")
            tg = TgUploader(up_name, up_dir, size, self)
            tg_upload_status = TgUploadStatus(tg, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = tg_upload_status
            update_all_messages()
            tg.upload(o_files, m_size)
        else:
            up_path = f'{up_dir}/{up_name}'
            size = get_path_size(up_path)
            LOGGER.info(f"Upload Name: {up_name}")
            drive = GoogleDriveHelper(up_name, up_dir, size, self)
            upload_status = UploadStatus(drive, size, gid, self)
            with download_dict_lock:
                download_dict[self.uid] = upload_status
            update_all_messages()
            drive.upload(up_name)

    def onUploadComplete(self, link: str, size, files, folders, typ, name):
        if not self.isPrivate and config_dict['INCOMPLETE_TASK_NOTIFIER'] and DATABASE_URL:
            DbManger().rm_complete_task(self.message.link)
        msg = f"<b>Name: </b><code>{escape(name)}</code>\n\n<b>Size: </b>{size}"
        if self.isLeech:
            msg += f'\n<b>Total Files: </b>{folders}'
            if typ != 0:
                msg += f'\n<b>Corrupted Files: </b>{typ}'
            msg += f'\n<b>cc: </b>{self.tag}\n\n'
            if not files:
                sendMessage(msg, self.bot, self.message)
            else:
                fmsg = ''
                for index, (link, name) in enumerate(files.items(), start=1):
                    fmsg += f"{index}. <a href='{link}'>{name}</a>\n"
                    if len(fmsg.encode() + msg.encode()) > 4000:
                        sendMessage(msg + fmsg, self.bot, self.message)
                        sleep(1)
                        fmsg = ''
                if fmsg != '':
                    sendMessage(msg + fmsg, self.bot, self.message)
            if self.seed:
                if self.newDir:
                    clean_target(self.newDir)
                with queue_dict_lock:
                    if self.uid in non_queued_up:
                        non_queued_up.remove(self.uid)
                return
        else:
            msg += f'\n\n<b>Type: </b>{typ}'
            if typ == "Folder":
                msg += f'\n<b>SubFolders: </b>{folders}'
                msg += f'\n<b>Files: </b>{files}'
            msg += f'\n\n<b>cc: </b>{self.tag}'
            buttons = ButtonMaker()
            buttons.buildbutton("☁️ Drive Link", link)
            LOGGER.info(f'Done Uploading {name}')
            if INDEX_URL:= config_dict['INDEX_URL']:
                url_path = rutils.quote(f'{name}')
                share_url = f'{INDEX_URL}/{url_path}'
                if typ == "Folder":
                    share_url += '/'
                    buttons.buildbutton("⚡ Index Link", share_url)
                else:
                    buttons.buildbutton("⚡ Index Link", share_url)
                    if config_dict['VIEW_LINK']:
                        share_urls = f'{INDEX_URL}/{url_path}?a=view'
                        buttons.buildbutton("🌐 View Link", share_urls)
            sendMessage(msg, self.bot, self.message, buttons.build_menu(2))
            if self.seed:
                if self.isZip:
                    clean_target(f"{self.dir}/{name}")
                elif self.newDir:
                    clean_target(self.newDir)
                with queue_dict_lock:
                    if self.uid in non_queued_up:
                        non_queued_up.remove(self.uid)
                return
        clean_download(self.dir)
        with download_dict_lock:
            if self.uid in download_dict.keys():
                del download_dict[self.uid]
            count = len(download_dict)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        with queue_dict_lock:
            if self.uid in non_queued_up:
                non_queued_up.remove(self.uid)

        start_from_queued()

    def onDownloadError(self, error):
        clean_download(self.dir)
        if self.newDir:
            clean_download(self.newDir)
        with download_dict_lock:
            if self.uid in download_dict.keys():
                del download_dict[self.uid]
            count = len(download_dict)
            if self.uid in self.sameDir:
                self.sameDir.remove(self.uid)
        msg = f"{self.tag} your download has been stopped due to: {escape(error)}"
        sendMessage(msg, self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and config_dict['INCOMPLETE_TASK_NOTIFIER'] and DATABASE_URL:
            DbManger().rm_complete_task(self.message.link)

        with queue_dict_lock:
            if self.uid in queued_dl:
                del queued_dl[self.uid]
            if self.uid in non_queued_dl:
                non_queued_dl.remove(self.uid)
            if self.uid in queued_up:
                del queued_up[self.uid]
            if self.uid in non_queued_up:
                non_queued_up.remove(self.uid)

        self.queuedUp = False
        start_from_queued()

    def onUploadError(self, error):
        clean_download(self.dir)
        if self.newDir:
            clean_download(self.newDir)
        with download_dict_lock:
            if self.uid in download_dict.keys():
                del download_dict[self.uid]
            count = len(download_dict)
            if self.uid in self.sameDir:
                self.sameDir.remove(self.uid)
        sendMessage(f"{self.tag} {escape(error)}", self.bot, self.message)
        if count == 0:
            self.clean()
        else:
            update_all_messages()

        if not self.isPrivate and config_dict['INCOMPLETE_TASK_NOTIFIER'] and DATABASE_URL:
            DbManger().rm_complete_task(self.message.link)

        with queue_dict_lock:
            if self.uid in queued_up:
                del queued_up[self.uid]
            if self.uid in non_queued_up:
                non_queued_up.remove(self.uid)

        self.queuedUp = False
        start_from_queued()
