from hashlib import sha1
from base64 import b16encode, b32decode
from bencoding import bencode, bdecode
from time import sleep, time
from re import search as re_search
from os import remove
from threading import Lock, Thread

from bot import download_dict, download_dict_lock, get_client, LOGGER, QbInterval, config_dict
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, sendStatusMessage, update_all_messages, sendFile
from bot.helper.ext_utils.bot_utils import get_readable_time, setInterval, bt_selection_buttons, getDownloadByGid, new_thread
from bot.helper.ext_utils.fs_utils import clean_unwanted, get_base_name

qb_download_lock = Lock()
STALLED_TIME = {}
STOP_DUP_CHECK = set()
RECHECKED = set()
UPLOADED = set()
SEEDING = set()

def __get_hash_magnet(mgt: str):
    hash_ = re_search(r'(?<=xt=urn:btih:)[a-zA-Z0-9]+', mgt).group(0)
    if len(hash_) == 32:
        hash_ = b16encode(b32decode(hash_.upper())).decode()
    return str(hash_)

def __get_hash_file(path):
    with open(path, "rb") as f:
        decodedDict = bdecode(f.read())
        hash_ = sha1(bencode(decodedDict[b'info'])).hexdigest()
    return str(hash_)

def add_qb_torrent(link, path, listener, ratio, seed_time):
    client = get_client()
    ADD_TIME = time()
    try:
        if link.startswith('magnet:'):
            ext_hash = __get_hash_magnet(link)
        else:
            ext_hash = __get_hash_file(link)
        if ext_hash is None or len(ext_hash) < 30:
            sendMessage("Not a torrent! Qbittorrent only for torrents!", listener.bot, listener.message)
            return
        tor_info = client.torrents_info(torrent_hashes=ext_hash)
        if len(tor_info) > 0:
            sendMessage("This Torrent already added!", listener.bot, listener.message)
            return
        if link.startswith('magnet:'):
            op = client.torrents_add(link, save_path=path, ratio_limit=ratio, seeding_time_limit=seed_time)
        else:
            op = client.torrents_add(torrent_files=[link], save_path=path, ratio_limit=ratio, seeding_time_limit=seed_time)
        sleep(0.3)
        if op.lower() == "ok.":
            tor_info = client.torrents_info(torrent_hashes=ext_hash)
            if len(tor_info) == 0:
                while True:
                    tor_info = client.torrents_info(torrent_hashes=ext_hash)
                    if len(tor_info) > 0:
                        break
                    elif time() - ADD_TIME >= 60:
                        msg = "Not added, maybe it will took time and u should remove it manually using eval!"
                        sendMessage(msg, listener.bot, listener.message)
                        __remove_torrent(client, ext_hash)
                        return
        else:
            sendMessage("This is an unsupported/invalid link.", listener.bot, listener.message)
            __remove_torrent(client, ext_hash)
            return
        tor_info = tor_info[0]
        ext_hash = tor_info.hash
        with download_dict_lock:
            download_dict[listener.uid] = QbDownloadStatus(listener, ext_hash)
        with qb_download_lock:
            STALLED_TIME[ext_hash] = time()
            if not QbInterval:
                periodic = setInterval(5, __qb_listener)
                QbInterval.append(periodic)
        listener.onDownloadStart()
        LOGGER.info(f"QbitDownload started: {tor_info.name} - Hash: {ext_hash}")
        if config_dict['BASE_URL'] and listener.select:
            if link.startswith('magnet:'):
                metamsg = "Downloading Metadata, wait then you can select files. Use torrent file to avoid this wait."
                meta = sendMessage(metamsg, listener.bot, listener.message)
                while True:
                    tor_info = client.torrents_info(torrent_hashes=ext_hash)
                    if len(tor_info) == 0:
                        deleteMessage(listener.bot, meta)
                        return
                    try:
                        tor_info = tor_info[0]
                        if tor_info.state not in ["metaDL", "checkingResumeData", "pausedDL"]:
                            deleteMessage(listener.bot, meta)
                            break
                    except:
                        return deleteMessage(listener.bot, meta)
            client.torrents_pause(torrent_hashes=ext_hash)
            SBUTTONS = bt_selection_buttons(ext_hash)
            msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
            sendMarkup(msg, listener.bot, listener.message, SBUTTONS)
        else:
            sendStatusMessage(listener.message, listener.bot)
    except Exception as e:
        sendMessage(str(e), listener.bot, listener.message)
    finally:
        if not link.startswith('magnet:'):
            remove(link)
        client.auth_log_out()

def __remove_torrent(client, hash_):
    client.torrents_delete(torrent_hashes=hash_, delete_files=True)
    with qb_download_lock:
        if hash_ in STALLED_TIME:
            del STALLED_TIME[hash_]
        if hash_ in STOP_DUP_CHECK:
            STOP_DUP_CHECK.remove(hash_)
        if hash_ in RECHECKED:
            RECHECKED.remove(hash_)
        if hash_ in UPLOADED:
            UPLOADED.remove(hash_)
        if hash_ in SEEDING:
            SEEDING.remove(hash_)

def __onDownloadError(err, client, tor):
    LOGGER.info(f"Cancelling Download: {tor.name}")
    client.torrents_pause(torrent_hashes=tor.hash)
    sleep(0.3)
    download = getDownloadByGid(tor.hash[:12])
    try:
        listener = download.listener()
        listener.onDownloadError(err)
    except:
        pass
    __remove_torrent(client, tor.hash)

@new_thread
def __onSeedFinish(client, tor):
    LOGGER.info(f"Cancelling Seed: {tor.name}")
    download = getDownloadByGid(tor.hash[:12])
    try:
        listener = download.listener()
        listener.onUploadError(f"Seeding stopped with Ratio: {round(tor.ratio, 3)} and Time: {get_readable_time(tor.seeding_time)}")
    except:
        pass
    __remove_torrent(client, tor.hash)

@new_thread
def __stop_duplicate(client, tor):
    download = getDownloadByGid(tor.hash[:12])
    try:
        listener = download.listener()
        if not listener.select and not listener.isLeech:
            LOGGER.info('Checking File/Folder if already in Drive')
            qbname = tor.content_path.rsplit('/', 1)[-1].rsplit('.!qB', 1)[0]
            if listener.isZip:
                qbname = f"{qbname}.zip"
            elif listener.extract:
                try:
                    qbname = get_base_name(qbname)
                except:
                    qbname = None
            if qbname is not None:
                cap, f_name = GoogleDriveHelper().drive_list(qbname, True)
                if cap:
                    __onDownloadError("File/Folder is already available in Drive.", client, tor)
                    cap = f"Here are the search results:\n\n{cap}"
                    sendFile(listener.bot, listener.message, f_name, cap)
                    return
    except:
        pass

@new_thread
def __onDownloadComplete(client, tor):
    download = getDownloadByGid(tor.hash[:12])
    try:
        listener = download.listener()
    except:
        return
    if not listener.seed:
        client.torrents_pause(torrent_hashes=tor.hash)
    if listener.select:
        clean_unwanted(listener.dir)
    listener.onDownloadComplete()
    if listener.seed:
        with download_dict_lock:
            if listener.uid in download_dict:
                removed = False
                download_dict[listener.uid] = QbDownloadStatus(listener, tor.hash, True)
            else:
                removed = True
        if removed:
            __remove_torrent(client, tor.hash)
            return
        with qb_download_lock:
            SEEDING.add(tor.hash)
        update_all_messages()
        LOGGER.info(f"Seeding started: {tor.name} - Hash: {tor.hash}")
    else:
        __remove_torrent(client, tor.hash)

def __qb_listener():
    client = get_client()
    with qb_download_lock:
        if len(client.torrents_info()) == 0:
            QbInterval[0].cancel()
            QbInterval.clear()
            return
        try:
            for tor_info in client.torrents_info():
                if tor_info.state == "metaDL":
                    TORRENT_TIMEOUT = config_dict['TORRENT_TIMEOUT']
                    STALLED_TIME[tor_info.hash] = time()
                    if TORRENT_TIMEOUT and time() - tor_info.added_on >= TORRENT_TIMEOUT:
                        Thread(target=__onDownloadError, args=("Dead Torrent!", client, tor_info)).start()
                    else:
                        client.torrents_reannounce(torrent_hashes=tor_info.hash)
                elif tor_info.state == "downloading":
                    STALLED_TIME[tor_info.hash] = time()
                    if config_dict['STOP_DUPLICATE'] and tor_info.hash not in STOP_DUP_CHECK:
                        STOP_DUP_CHECK.add(tor_info.hash)
                        __stop_duplicate(client, tor_info)
                elif tor_info.state == "stalledDL":
                    TORRENT_TIMEOUT = config_dict['TORRENT_TIMEOUT']
                    if tor_info.hash not in RECHECKED and 0.99989999999999999 < tor_info.progress < 1:
                        msg = f"Force recheck - Name: {tor_info.name} Hash: "
                        msg += f"{tor_info.hash} Downloaded Bytes: {tor_info.downloaded} "
                        msg += f"Size: {tor_info.size} Total Size: {tor_info.total_size}"
                        LOGGER.error(msg)
                        client.torrents_recheck(torrent_hashes=tor_info.hash)
                        RECHECKED.add(tor_info.hash)
                    elif TORRENT_TIMEOUT and time() - STALLED_TIME.get(tor_info.hash, 0) >= TORRENT_TIMEOUT:
                        Thread(target=__onDownloadError, args=("Dead Torrent!", client, tor_info)).start()
                    else:
                        client.torrents_reannounce(torrent_hashes=tor_info.hash)
                elif tor_info.state == "missingFiles":
                    client.torrents_recheck(torrent_hashes=tor_info.hash)
                elif tor_info.state == "error":
                    Thread(target=__onDownloadError, args=("No enough space for this torrent on device", client, tor_info)).start()
                elif tor_info.completion_on != 0 and tor_info.hash not in UPLOADED and \
                      tor_info.state not in ['checkingUP', 'checkingDL', 'checkingResumeData']:
                    UPLOADED.add(tor_info.hash)
                    __onDownloadComplete(client, tor_info)
                elif tor_info.state in ['pausedUP', 'pausedDL'] and tor_info.hash in SEEDING:
                    SEEDING.remove(tor_info.hash)
                    __onSeedFinish(client, tor_info)
        except Exception as e:
            LOGGER.error(str(e))
