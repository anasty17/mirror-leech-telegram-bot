from asyncio import create_subprocess_exec
from asyncio.subprocess import PIPE
from random import SystemRandom
from string import ascii_letters, digits
from re import findall as re_findall
from json import loads

from bot import download_dict, download_dict_lock, config_dict, queue_dict_lock, non_queued_dl, \
non_queued_up, queued_dl, LOGGER, GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.bot_utils import cmd_exec, sync_to_async, new_task
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.fs_utils import get_base_name


class RcloneDownloadHelper:
    def __init__(self, listener):
        self.__listener = listener
        self.__proc = None
        self.__transferred_size = '0 B'
        self.__eta = '-'
        self.__percentage = '0%'
        self.__speed = '0 B/s'
        self.__is_cancelled = False
        self.name = ''
        self.size = 0
        self.gid = ''

    @property
    def transferred_size(self):
        return self.__transferred_size
    
    @property
    def percentage(self):
        return self.__percentage
    
    @property
    def speed(self):
        return self.__speed
    
    @property
    def eta(self):
        return self.__eta

    @new_task
    async def __progress(self):
        while not (self.__proc is None or self.__is_cancelled):
            data = (await self.__proc.stdout.readline()).decode()
            if not data:
                break
            if data := re_findall(r'Transferred:\s+([\d.]+\s*\w+)\s+/\s+([\d.]+\s*\w+),\s+([\d.]+%)\s*,\s+([\d.]+\s*\w+/s),\s+ETA\s+([\dwdhms]+)', data):
                self.__transferred_size, _, self.__percentage, self.__speed, self.__eta = data[0]
  
    async def add_download(self, link, config_path, path, name, from_queue=False):
        if not name:
            pre_name = link.rsplit('/', 1)
            name = pre_name[1] if len(pre_name) > 1 else link.split(':', 1)[1]
        if not name:
            name = link.strip(':')
        self.name = name
        path += name
        cmd = ['rclone', 'size', '--json', f'--config={config_path}', link]
        res = (await cmd_exec(cmd))[0]
        try:
            rdict = loads(res)
        except:
            await self.__listener.onDownloadError('Invalid Path!')
            return
        self.size = rdict['bytes']
        if config_dict['STOP_DUPLICATE'] and not self.__listener.isLeech:
            LOGGER.info('Checking File/Folder if already in Drive')
            if self.__listener.isZip:
                rname = f"{rname}.zip"
            elif self.__listener.extract:
                try:
                    rname = get_base_name(rname)
                except:
                    rname = None
            if rname is not None:
                smsg, button = await sync_to_async(GoogleDriveHelper().drive_list, rname, True)
                if smsg:
                    msg = "File/Folder is already available in Drive.\nHere are the search results:"
                    await sendMessage(self.__listener.message, msg, button)
                    return
        self.gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
        all_limit = config_dict['QUEUE_ALL']
        dl_limit = config_dict['QUEUE_DOWNLOAD']
        if all_limit or dl_limit:
            added_to_queue = False
            async with queue_dict_lock:
                dl = len(non_queued_dl)
                up = len(non_queued_up)
                if (all_limit and dl + up >= all_limit and (not dl_limit or dl >= dl_limit)) or (dl_limit and dl >= dl_limit):
                    added_to_queue = True
                    queued_dl[self.__listener.uid] = ['rcd', link, config_path, path, name, self.__listener]
            if added_to_queue:
                LOGGER.info(f"Added to Queue/Download: {name}")
                async with download_dict_lock:
                    download_dict[self.__listener.uid] = QueueStatus(name, self.size, self.gid, self.__listener.message, 'Dl')
                await self.__listener.onDownloadStart()
                await sendStatusMessage(self.__listener.message)
                return
        async with download_dict_lock:
            download_dict[self.__listener.uid] = RcloneStatus(self, self.__listener.message, 'dl')
        async with queue_dict_lock:
            non_queued_dl.add(self.__listener.uid)
        if not from_queue:
            await self.__listener.onDownloadStart()
            await sendStatusMessage(self.__listener.message)
            LOGGER.info(f"Download with rclone: {link}")
        else:
            LOGGER.info(f'Start Queued Download with rclone: {link}')
        ext = ','.join([f'*.{ext}' for ext in GLOBAL_EXTENSION_FILTER])
        cmd = ['rclone', 'copy', f'--config={config_path}', '-P', link, path, '--exclude', ext]
        self.__proc = await create_subprocess_exec(*cmd, stdout=PIPE)
        self.__progress()
        await self.__proc.wait()
        if self.__is_cancelled:
            return
        return_code = self.__proc.returncode
        if return_code == 0:
            await self.__listener.onDownloadComplete()
        elif return_code != -9:
            await self.__listener.onDownloadError('Internal Error, Report..!')

    async def cancel_download(self):
        self.__is_cancelled = True
        self.__proc.kill()
        await self.__listener.onDownloadError('Download stopped by user!')