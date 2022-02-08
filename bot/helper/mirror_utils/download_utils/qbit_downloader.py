from hashlib import sha1
from bencoding import bencode, bdecode
from os import remove as osremove, path as ospath, listdir
from time import sleep, time
from re import search
from threading import Thread
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler

from bot import download_dict, download_dict_lock, BASE_URL, dispatcher, get_client, TORRENT_DIRECT_LIMIT, ZIP_UNZIP_LIMIT, STOP_DUPLICATE, WEB_PINCODE, QB_SEED, QB_TIMEOUT, LOGGER
from bot.helper.mirror_utils.status_utils.qbit_download_status import QbDownloadStatus
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.telegram_helper.message_utils import sendMessage, sendMarkup, deleteMessage, sendStatusMessage, update_all_messages
from bot.helper.ext_utils.bot_utils import MirrorStatus, getDownloadByGid, get_readable_file_size, get_readable_time
from bot.helper.ext_utils.fs_utils import clean_unwanted, get_base_name
from bot.helper.telegram_helper import button_build


def add_qb_torrent(link, path, listener, select):
    client = get_client()
    pincode = ""
    try:
        if ospath.exists(link):
            is_file = True
            ext_hash = _get_hash_file(link)
        else:
            is_file = False
            ext_hash = _get_hash_magnet(link)
        tor_info = client.torrents_info(torrent_hashes=ext_hash)
        if len(tor_info) > 0:
            sendMessage("This Torrent is already in list.", listener.bot, listener.update)
            client.auth_log_out()
            return
        if is_file:
            op = client.torrents_add(torrent_files=[link], save_path=path)
            osremove(link)
        else:
            op = client.torrents_add(link, save_path=path)
        sleep(0.3)
        if op.lower() == "ok.":
            add_time = time()
            tor_info = client.torrents_info(torrent_hashes=ext_hash)
            if len(tor_info) == 0:
                while True:
                    if time() - add_time >= 30:
                        ermsg = "The Torrent was not added. Report when you see this error"
                        sendMessage(ermsg, listener.bot, listener.update)
                        client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
                        client.auth_log_out()
                        return
                    tor_info = client.torrents_info(torrent_hashes=ext_hash, delete_files=True)
                    if len(tor_info) > 0:
                        break
        else:
            sendMessage("This is an unsupported/invalid link.", listener.bot, listener.update)
            client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
            client.auth_log_out()
            return
        tor_info = tor_info[0]
        ext_hash = tor_info.hash
        gid = ext_hash[:12]
        with download_dict_lock:
            download_dict[listener.uid] = QbDownloadStatus(listener, client, ext_hash, select)
        LOGGER.info(f"QbitDownload started: {tor_info.name} - Hash: {ext_hash}")
        Thread(target=_qb_listener, args=(listener, client, ext_hash, select, path)).start()
        if BASE_URL is not None and select:
            if not is_file:
                metamsg = "Downloading Metadata, wait then you can select files or mirror torrent file"
                meta = sendMessage(metamsg, listener.bot, listener.update)
                while True:
                    tor_info = client.torrents_info(torrent_hashes=ext_hash)
                    if len(tor_info) == 0:
                        return deleteMessage(listener.bot, meta)
                    try:
                        tor_info = tor_info[0]
                        if tor_info.state not in ["metaDL", "checkingResumeData", "pausedDL"]:
                            deleteMessage(listener.bot, meta)
                            break
                        sleep(1)
                    except:
                        return deleteMessage(listener.bot, meta)
            sleep(0.5)
            client.torrents_pause(torrent_hashes=ext_hash)
            for n in str(ext_hash):
                if n.isdigit():
                    pincode += str(n)
                if len(pincode) == 4:
                    break
            buttons = button_build.ButtonMaker()
            if WEB_PINCODE:
                buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{ext_hash}")
                buttons.sbutton("Pincode", f"qbs pin {gid} {pincode}")
            else:
                buttons.buildbutton("Select Files", f"{BASE_URL}/app/files/{ext_hash}?pin_code={pincode}")
            buttons.sbutton("Done Selecting", f"qbs done {gid} {ext_hash}")
            QBBUTTONS = InlineKeyboardMarkup(buttons.build_menu(2))
            msg = "Your download paused. Choose files then press Done Selecting button to start downloading."
            sendMarkup(msg, listener.bot, listener.update, QBBUTTONS)
        else:
            sendStatusMessage(listener.update, listener.bot)
    except Exception as e:
        sendMessage(str(e), listener.bot, listener.update)
        client.auth_log_out()

def _qb_listener(listener, client, ext_hash, select, path):
    stalled_time = time()
    uploaded = False
    sizeChecked = False
    dupChecked = False
    rechecked = False
    while True:
        sleep(4)
        try:
            tor_info = client.torrents_info(torrent_hashes=ext_hash)
            if len(tor_info) == 0:
                with download_dict_lock:
                    if listener.uid not in list(download_dict.keys()):
                        client.auth_log_out()
                        break
                continue
            tor_info = tor_info[0]
            if tor_info.state == "metaDL":
                stalled_time = time()
                if QB_TIMEOUT is not None and time() - tor_info.added_on >= QB_TIMEOUT: #timeout while downloading metadata
                    _onDownloadError("Dead Torrent!", client, ext_hash, listener)
                    break
            elif tor_info.state == "downloading":
                stalled_time = time()
                if STOP_DUPLICATE and not dupChecked and ospath.isdir(f'{path}') and not listener.isLeech:
                    LOGGER.info('Checking File/Folder if already in Drive')
                    qbname = str(listdir(f'{path}')[-1])
                    if qbname.endswith('.!qB'):
                        qbname = ospath.splitext(qbname)[0]
                    if listener.isZip:
                        qbname = qbname + ".zip"
                    elif listener.extract:
                        try:
                           qbname = get_base_name(qbname)
                        except:
                            qbname = None
                    if qbname is not None:
                        qbmsg, button = GoogleDriveHelper().drive_list(qbname, True)
                        if qbmsg:
                            msg = "File/Folder is already available in Drive."
                            _onDownloadError(msg, client, ext_hash, listener)
                            sendMarkup("Here are the search results:", listener.bot, listener.update, button)
                            break
                    dupChecked = True
                if not sizeChecked:
                    limit = None
                    if ZIP_UNZIP_LIMIT is not None and (listener.isZip or listener.extract):
                        mssg = f'Zip/Unzip limit is {ZIP_UNZIP_LIMIT}GB'
                        limit = ZIP_UNZIP_LIMIT
                    elif TORRENT_DIRECT_LIMIT is not None:
                        mssg = f'Torrent limit is {TORRENT_DIRECT_LIMIT}GB'
                        limit = TORRENT_DIRECT_LIMIT
                    if limit is not None:
                        LOGGER.info('Checking File/Folder Size...')
                        sleep(1)
                        size = tor_info.size
                        if size > limit * 1024**3:
                            fmsg = f"{mssg}.\nYour File/Folder size is {get_readable_file_size(size)}"
                            _onDownloadError(fmsg, client, ext_hash, listener)
                            break
                    sizeChecked = True
            elif tor_info.state == "stalledDL":
                if not rechecked and 0.99989999999999999 < tor_info.progress < 1:
                    msg = f"Force recheck - Name: {tor_info.name} Hash: "
                    msg += f"{ext_hash} Downloaded Bytes: {tor_info.downloaded} "
                    msg += f"Size: {tor_info.size} Total Size: {tor_info.total_size}"
                    LOGGER.info(msg)
                    client.torrents_recheck(torrent_hashes=ext_hash)
                    rechecked = True
                elif QB_TIMEOUT is not None and time() - stalled_time >= QB_TIMEOUT: # timeout after downloading metadata
                    _onDownloadError("Dead Torrent!", client, ext_hash, listener)
                    break
            elif tor_info.state == "missingFiles":
                client.torrents_recheck(torrent_hashes=ext_hash)
            elif tor_info.state == "error":
                _onDownloadError("No enough space for this torrent on device", client, ext_hash, listener)
                break
            elif (tor_info.state.lower().endswith("up") or tor_info.state == "uploading") and not uploaded:
                LOGGER.info(f"onQbDownloadComplete: {ext_hash}")
                uploaded = True
                if not QB_SEED:
                    client.torrents_pause(torrent_hashes=ext_hash)
                if select:
                    clean_unwanted(path)
                listener.onDownloadComplete()
                if QB_SEED and not listener.isLeech and not listener.extract:
                    with download_dict_lock:
                        if listener.uid not in list(download_dict.keys()):
                            client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
                            client.auth_log_out()
                            break
                        download_dict[listener.uid] = QbDownloadStatus(listener, client, ext_hash, select)
                    update_all_messages()
                    LOGGER.info(f"Seeding started: {tor_info.name}")
                else:
                    client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
                    client.auth_log_out()
                    break
            elif tor_info.state == 'pausedUP' and QB_SEED:
                listener.onUploadError(f"Seeding stopped with Ratio: {round(tor_info.ratio, 3)} and Time: {get_readable_time(tor_info.seeding_time)}")
                client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
                client.auth_log_out()
                update_all_messages()
                break
        except Exception as e:
            LOGGER.error(str(e))

def get_confirm(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    qbdl = getDownloadByGid(data[2])
    if qbdl is None:
        query.answer(text="This task has been cancelled!", show_alert=True)
        query.message.delete()
    elif user_id != qbdl.listener().message.from_user.id:
        query.answer(text="Don't waste your time!", show_alert=True)
    elif data[1] == "pin":
        query.answer(text=data[3], show_alert=True)
    elif data[1] == "done":
        query.answer()
        qbdl.client().torrents_resume(torrent_hashes=data[3])
        sendStatusMessage(qbdl.listener().update, qbdl.listener().bot)
        query.message.delete()

def _get_hash_magnet(mgt):
    if mgt.startswith('magnet:'):
        hash_ = search(r'(?<=xt=urn:btih:)[a-zA-Z0-9]+', mgt).group(0)
        return hash_

def _get_hash_file(path):
    with open(path, "rb") as f:
        decodedDict = bdecode(f.read())
    hash_ = sha1(bencode(decodedDict[b'info'])).hexdigest()
    return str(hash_)

def _onDownloadError(err: str, client, ext_hash, listener):
    client.torrents_pause(torrent_hashes=ext_hash)
    sleep(0.3)
    listener.onDownloadError(err)
    client.torrents_delete(torrent_hashes=ext_hash, delete_files=True)
    client.auth_log_out()


qbs_handler = CallbackQueryHandler(get_confirm, pattern="qbs", run_async=True)
dispatcher.add_handler(qbs_handler)
