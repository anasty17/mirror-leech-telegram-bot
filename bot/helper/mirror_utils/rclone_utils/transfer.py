from asyncio import create_subprocess_exec, Event
from asyncio.subprocess import PIPE
from random import SystemRandom
from string import ascii_letters, digits
from re import findall as re_findall
from json import loads
from aiofiles.os import path as aiopath
from aiofiles import open as aiopen
from configparser import ConfigParser

from bot import download_dict, download_dict_lock, config_dict, queue_dict_lock, non_queued_dl, \
non_queued_up, queued_dl, LOGGER, GLOBAL_EXTENSION_FILTER
from bot.helper.ext_utils.bot_utils import cmd_exec, sync_to_async, new_task
from bot.helper.mirror_utils.status_utils.rclone_status import RcloneStatus
from bot.helper.mirror_utils.status_utils.queue_status import QueueStatus
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, update_all_messages
from bot.helper.mirror_utils.upload_utils.gdriveTools import GoogleDriveHelper
from bot.helper.ext_utils.fs_utils import get_base_name, get_mime_type, count_files_and_folders


class RcloneTransferHelper:
    def __init__(self, listener, name='', size=0, gid=''):
        self.__listener = listener
        self.__proc = None
        self.__transferred_size = '0 B'
        self.__eta = '-'
        self.__percentage = '0%'
        self.__speed = '0 B/s'
        self.__is_cancelled = False
        self.__is_download = False
        self.name = name
        self.size = size
        self.gid = gid

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
  
    async def add_download(self, rc_path, config_path, path, name):
        self.__is_download = True
        cmd = ['rclone', 'lsjson', '--stat', '--no-mimetype', '--no-modtime', '--config', config_path, rc_path]
        res, err, code = await cmd_exec(cmd)
        if self.__is_cancelled:
            return
        if code not in [0, -9]:
            await sendMessage(f'Error: While getting rclone stat. Path: {rc_path}. Stderr: {err[:4000]}')
            return
        result = loads(res)
        if result['IsDir']:
            if not name:
                name = await self.__getItemName(rc_path.strip('/'))
            path += name
        else:
            name = await self.__getItemName(rc_path.strip('/'))
        self.name = name
        cmd = ['rclone', 'size', '--fast-list', '--json', '--config', config_path, rc_path]
        res, err, code = await cmd_exec(cmd)
        if self.__is_cancelled:
            return
        if code not in [0, -9]:
            await sendMessage(f'Error: While getting rclone size. Path: {rc_path}. Stderr: {err[:4000]}')
            return
        rdict = loads(res)
        self.size = rdict['bytes']
        if config_dict['STOP_DUPLICATE'] and not self.__listener.isLeech and self.__listener.upPath == 'gd':
            LOGGER.info('Checking File/Folder if already in Drive')
            if self.__listener.isZip:
                rname = f"{name}.zip"
            elif self.__listener.extract:
                try:
                    rname = get_base_name(name)
                except:
                    rname = None
            else:
                rname = name
            if rname is not None:
                smsg, button = await sync_to_async(GoogleDriveHelper().drive_list, rname, True)
                if smsg:
                    msg = "File/Folder is already available in Drive.\nHere are the search results:"
                    await sendMessage(self.__listener.message, msg, button)
                    return
        self.gid = ''.join(SystemRandom().choices(ascii_letters + digits, k=12))
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
                    queued_dl[self.__listener.uid] = event
            if added_to_queue:
                LOGGER.info(f"Added to Queue/Download: {name}")
                async with download_dict_lock:
                    download_dict[self.__listener.uid] = QueueStatus(name, self.size, self.gid, self.__listener, 'Dl')
                await self.__listener.onDownloadStart()
                await sendStatusMessage(self.__listener.message)
                await event.wait()
                async with download_dict_lock:
                    if self.__listener.uid not in download_dict:
                        return
                from_queue = True
        async with download_dict_lock:
            download_dict[self.__listener.uid] = RcloneStatus(self, self.__listener.message, 'dl')
        async with queue_dict_lock:
            non_queued_dl.add(self.__listener.uid)
        if not from_queue:
            await self.__listener.onDownloadStart()
            await sendStatusMessage(self.__listener.message)
            LOGGER.info(f"Download with rclone: {rc_path}")
        else:
            LOGGER.info(f'Start Queued Download with rclone: {rc_path}')
        remote = rc_path.split(':')[0]
        remote_type = await self.__get_remote_type(config_path, remote)
        cmd = await self.__getUpdatedCommand(config_path, rc_path, path)
        if remote_type == 'drive' and not config_dict['RCLONE_FLAGS'] and not self.__listener.rcFlags:
            cmd.append('--drive-acknowledge-abuse')
        self.__proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        self.__progress()
        return_code = await self.__proc.wait()
        if self.__is_cancelled:
            return
        if return_code == 0:
            await self.__listener.onDownloadComplete()
        elif return_code != -9:
            error = (await self.__proc.stderr.read()).decode().strip()
            LOGGER.error(error)
            await self.__listener.onDownloadError(error[:4000])

    async def upload(self, path):
        async with download_dict_lock:
            download_dict[self.__listener.uid] = RcloneStatus(self, self.__listener.message, 'up')
        await update_all_messages()
        rc_path = self.__listener.upPath.strip('/')
        if rc_path == 'rc':
            rc_path = config_dict['RCLONE_PATH']
        if rc_path.startswith('mrcc:'):
            rc_path = rc_path.split('mrcc:', 1)[1]
            config_path = f'rclone/{self.__listener.message.from_user.id}.conf'
        else:
            config_path = 'rclone.conf'
        if await aiopath.isdir(path):
            mime_type = 'Folder'
            rc_path += f"/{self.name}" if rc_path.split(':', 1)[1] else self.name
        else:
            mime_type = 'File'
        remote = rc_path.split(':')[0]
        remote_type = await self.__get_remote_type(config_path, remote)
        cmd = await self.__getUpdatedCommand(config_path, path, rc_path)
        if remote_type == 'drive' and not config_dict['RCLONE_FLAGS'] and not self.__listener.rcFlags:
            cmd.extend(('--drive-chunk-size', '32M', '--drive-upload-cutoff', '32M'))
        self.__proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        self.__progress()
        return_code = await self.__proc.wait()
        if self.__is_cancelled:
            return
        if return_code == -9:
            pass
        elif return_code == 0:
            if mime_type == 'Folder':
                folders, files = await count_files_and_folders(path)
            else:
                mime_type = await sync_to_async(get_mime_type, path)
                folders = 0
                files = 1
            if remote_type == 'drive':
                if mime_type == 'Folder':
                    remote, epath = rc_path.split(':', 1)
                    epath = epath.strip('/').rsplit('/', 1)
                    epath = f'{remote}:{epath[0]}' if len(epath) > 1 else f'{remote}:'
                    destination = rc_path
                elif rc_path.split(':', 1)[1]:
                    epath = f"{rc_path}/{self.name}"
                    destination = epath
                else:
                    epath = f"{rc_path}{self.name}"
                    destination = epath
                cmd = ['rclone', 'lsjson', '--fast-list', '--no-mimetype', '--no-modtime', '--config', config_path, epath]
                res, err, code = await cmd_exec(cmd)
                if self.__is_cancelled:
                    return
                if code == 0:
                    result = loads(res)
                    fid = 'err'
                    for r in result:
                        if r['Path'] == self.name:
                            fid = r['ID']
                    link = f'https://drive.google.com/drive/folders/{fid}' if mime_type == 'Folder' else f'https://drive.google.com/uc?id={fid}&export=download'
                elif code != -9:
                    LOGGER.error(f'while getting drive link. Path: {rc_path}. Stderr: {err}')
                    link = ''
            else:
                if mime_type == 'Folder':
                    epath = rc_path 
                elif rc_path.split(':', 1)[1]:
                    epath = f"{rc_path}/{self.name}"
                else:
                    epath = f"{rc_path}{self.name}"
                cmd = ['rclone', 'link', '--config', config_path, epath]
                res, err, code = await cmd_exec(cmd)
                if self.__is_cancelled:
                    return
                if code == 0:
                    link = res
                elif code != -9:
                    LOGGER.error(f'while getting link. Path: {epath} | Stderr: {err}')
                    link = ''
                destination = epath
            LOGGER.info(f'Upload Done. Path: {epath}')
            await self.__listener.onUploadComplete(link, self.size, files, folders, mime_type, self.name, destination)
        else:
            error = (await self.__proc.stderr.read()).decode().strip()
            LOGGER.error(error)
            await self.__listener.onUploadError(error[:4000])

    @staticmethod
    async def __getItemName(path):
        remote, ipath = path.split(':', 1)
        if not ipath:
            return remote
        pre_name = ipath.rsplit('/', 1)
        return pre_name[1] if len(pre_name) > 1 else pre_name[0]

    async def __getUpdatedCommand(self, config_path, fpath, tpath):
        ext = '*.{' + ','.join(GLOBAL_EXTENSION_FILTER) + '}'
        cmd = ['rclone', 'copy', '--config', config_path, '-P', fpath, tpath, '--exclude', ext, '--ignore-case']
        if rcf := self.__listener.rcFlags or config_dict['RCLONE_FLAGS']:
            rcflags = rcf.split('|')
            for flag in rcflags:
                if ":" in flag:
                    key, value = flag.split(":")
                    cmd.extend((key, value))
                elif len(flag) > 0:
                    cmd.append(flag)
        return cmd
    
    @staticmethod
    async def __get_remote_type(config_path, remote):
        config = ConfigParser()
        async with aiopen(config_path, 'r') as f:
            contents = await f.read()
            config.read_string(contents)
        return config.get(remote, 'type')

    async def cancel_download(self):
        self.__is_cancelled = True
        if self.__proc is not None:
            try:
                self.__proc.kill()
            except:
                pass
        if self.__is_download:
            LOGGER.info(f"Cancelling Download: {self.name}")
            await self.__listener.onDownloadError('Download stopped by user!')
        else:
            LOGGER.info(f"Cancelling Upload: {self.name}")
            await self.__listener.onUploadError('your upload has been stopped!')