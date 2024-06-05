from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, makedirs, listdir
from asyncio import create_subprocess_exec, gather
from asyncio.subprocess import PIPE
from configparser import ConfigParser
from json import loads
from logging import getLogger
from random import randrange
from re import findall as re_findall

from bot import config_dict
from bot.helper.ext_utils.bot_utils import cmd_exec, sync_to_async
from bot.helper.ext_utils.files_utils import (
    get_mime_type,
    count_files_and_folders,
    clean_unwanted,
)

LOGGER = getLogger(__name__)


class RcloneTransferHelper:
    def __init__(self, listener):
        self._listener = listener
        self._proc = None
        self._transferred_size = "0 B"
        self._eta = "-"
        self._percentage = "0%"
        self._speed = "0 B/s"
        self._size = "0 B"
        self._is_download = False
        self._is_upload = False
        self._sa_count = 1
        self._sa_index = 0
        self._sa_number = 0
        self._use_service_accounts = config_dict["USE_SERVICE_ACCOUNTS"]

    @property
    def transferred_size(self):
        return self._transferred_size

    @property
    def percentage(self):
        return self._percentage

    @property
    def speed(self):
        return self._speed

    @property
    def eta(self):
        return self._eta

    @property
    def size(self):
        return self._size

    async def _progress(self):
        while not (self._proc is None or self._listener.isCancelled):
            try:
                data = (await self._proc.stdout.readline()).decode()
            except:
                continue
            if not data:
                break
            if data := re_findall(
                r"Transferred:\s+([\d.]+\s*\w+)\s+/\s+([\d.]+\s*\w+),\s+([\d.]+%)\s*,\s+([\d.]+\s*\w+/s),\s+ETA\s+([\dwdhms]+)",
                data,
            ):
                (
                    self._transferred_size,
                    self._size,
                    self._percentage,
                    self._speed,
                    self._eta,
                ) = data[0]

    def _switchServiceAccount(self):
        if self._sa_index == self._sa_number - 1:
            self._sa_index = 0
        else:
            self._sa_index += 1
        self._sa_count += 1
        remote = f"sa{self._sa_index:03}"
        LOGGER.info(f"Switching to {remote} remote")
        return remote

    async def _create_rc_sa(self, remote, remote_opts):
        sa_conf_dir = "rclone_sa"
        sa_conf_file = f"{sa_conf_dir}/{remote}.conf"
        if await aiopath.isfile(sa_conf_file):
            return sa_conf_file
        await makedirs(sa_conf_dir, exist_ok=True)

        if gd_id := remote_opts.get("team_drive"):
            option = "team_drive"
        elif gd_id := remote_opts.get("root_folder_id"):
            option = "root_folder_id"
        else:
            self._use_service_accounts = False
            return "rclone.conf"

        files = await listdir("accounts")
        text = "".join(
            f"[sa{i:03}]\ntype = drive\nscope = drive\nservice_account_file = accounts/{sa}\n{option} = {gd_id}\n\n"
            for i, sa in enumerate(files)
        )

        async with aiopen(sa_conf_file, "w") as f:
            await f.write(text)
        return sa_conf_file

    async def _start_download(self, cmd, remote_type):
        self._proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        _, return_code = await gather(self._progress(), self._proc.wait())

        if self._listener.isCancelled:
            return

        if return_code == 0:
            await self._listener.onDownloadComplete()
        elif return_code != -9:
            error = (await self._proc.stderr.read()).decode().strip()
            if not error and remote_type == "drive" and self._use_service_accounts:
                error = "Mostly your service accounts don't have access to this drive!"
            elif not error:
                error = "Use <code>/shell cat rlog.txt</code> to see more information"
            LOGGER.error(error)

            if (
                self._sa_number != 0
                and remote_type == "drive"
                and "RATE_LIMIT_EXCEEDED" in error
                and self._use_service_accounts
            ):
                if self._sa_count < self._sa_number:
                    remote = self._switchServiceAccount()
                    cmd[6] = f"{remote}:{cmd[6].split(':', 1)[1]}"
                    if self._listener.isCancelled:
                        return
                    return await self._start_download(cmd, remote_type)
                else:
                    LOGGER.info(
                        f"Reached maximum number of service accounts switching, which is {self._sa_count}"
                    )

            await self._listener.onDownloadError(error[:4000])

    async def download(self, remote, config_path, path):
        self._is_download = True
        try:
            remote_opts = await self._get_remote_options(config_path, remote)
        except Exception as err:
            await self._listener.onDownloadError(str(err))
            return
        remote_type = remote_opts["type"]

        if (
            remote_type == "drive"
            and self._use_service_accounts
            and config_path == "rclone.conf"
            and await aiopath.isdir("accounts")
            and not remote_opts.get("service_account_file")
        ):
            config_path = await self._create_rc_sa(remote, remote_opts)
            if config_path != "rclone.conf":
                sa_files = await listdir("accounts")
                self._sa_number = len(sa_files)
                self._sa_index = randrange(self._sa_number)
                remote = f"sa{self._sa_index:03}"
                LOGGER.info(f"Download with service account {remote}")

        cmd = self._getUpdatedCommand(
            config_path, f"{remote}:{self._listener.link}", path, "copy"
        )

        if (
            remote_type == "drive"
            and not config_dict["RCLONE_FLAGS"]
            and not self._listener.rcFlags
        ):
            cmd.append("--drive-acknowledge-abuse")
        elif remote_type != "drive":
            cmd.extend(("--retries-sleep", "3s"))

        await self._start_download(cmd, remote_type)

    async def _get_gdrive_link(self, config_path, remote, rc_path, mime_type):
        if mime_type == "Folder":
            epath = rc_path.strip("/").rsplit("/", 1)
            epath = f"{remote}:{epath[0]}" if len(epath) > 1 else f"{remote}:"
            destination = f"{remote}:{rc_path}"
        elif rc_path:
            epath = f"{remote}:{rc_path}/{self._listener.name}"
            destination = epath
        else:
            epath = f"{remote}:{rc_path}{self._listener.name}"
            destination = epath

        cmd = [
            "rclone",
            "lsjson",
            "--fast-list",
            "--no-mimetype",
            "--no-modtime",
            "--config",
            config_path,
            epath,
        ]
        res, err, code = await cmd_exec(cmd)

        if code == 0:
            result = loads(res)
            fid = next(
                (r["ID"] for r in result if r["Path"] == self._listener.name), "err"
            )
            link = (
                f"https://drive.google.com/drive/folders/{fid}"
                if mime_type == "Folder"
                else f"https://drive.google.com/uc?id={fid}&export=download"
            )
        elif code != -9:
            if not err:
                err = "Use <code>/shell cat rlog.txt</code> to see more information"
            LOGGER.error(
                f"while getting drive link. Path: {destination}. Stderr: {err}"
            )
            link = ""
        return link, destination

    async def _start_upload(self, cmd, remote_type):
        self._proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        _, return_code = await gather(self._progress(), self._proc.wait())

        if self._listener.isCancelled:
            return False

        if return_code == -9:
            return False
        elif return_code != 0:
            error = (await self._proc.stderr.read()).decode().strip()
            if not error and remote_type == "drive" and self._use_service_accounts:
                error = "Mostly your service accounts don't have access to this drive or RATE_LIMIT_EXCEEDED"
            elif not error:
                error = "Use <code>/shell cat rlog.txt</code> to see more information"
            LOGGER.error(error)
            if (
                self._sa_number != 0
                and remote_type == "drive"
                and "RATE_LIMIT_EXCEEDED" in error
                and self._use_service_accounts
            ):
                if self._sa_count < self._sa_number:
                    remote = self._switchServiceAccount()
                    cmd[7] = f"{remote}:{cmd[7].split(':', 1)[1]}"
                    return (
                        False
                        if self._listener.isCancelled
                        else await self._start_upload(cmd, remote_type)
                    )
                else:
                    LOGGER.info(
                        f"Reached maximum number of service accounts switching, which is {self._sa_count}"
                    )
            await self._listener.onUploadError(error[:4000])
            return False
        else:
            return True

    async def upload(self, path, unwanted_files, ft_delete):
        self._is_upload = True
        rc_path = self._listener.upDest.strip("/")
        if rc_path.startswith("mrcc:"):
            rc_path = rc_path.split("mrcc:", 1)[1]
            oconfig_path = f"rclone/{self._listener.userId}.conf"
        else:
            oconfig_path = "rclone.conf"

        oremote, rc_path = rc_path.split(":", 1)

        if await aiopath.isdir(path):
            mime_type = "Folder"
            folders, files = await count_files_and_folders(
                path, self._listener.extensionFilter, unwanted_files
            )
            rc_path += f"/{self._listener.name}" if rc_path else self._listener.name
        else:
            if path.lower().endswith(tuple(self._listener.extensionFilter)):
                await self._listener.onUploadError(
                    "This file extension is excluded by extension filter!"
                )
                return
            mime_type = await sync_to_async(get_mime_type, path)
            folders = 0
            files = 1

        try:
            remote_opts = await self._get_remote_options(oconfig_path, oremote)
        except Exception as err:
            await self._listener.onUploadError(str(err))
            return
        remote_type = remote_opts["type"]

        fremote = oremote
        fconfig_path = oconfig_path
        if (
            remote_type == "drive"
            and self._use_service_accounts
            and fconfig_path == "rclone.conf"
            and await aiopath.isdir("accounts")
            and not remote_opts.get("service_account_file")
        ):
            fconfig_path = await self._create_rc_sa(oremote, remote_opts)
            if fconfig_path != "rclone.conf":
                sa_files = await listdir("accounts")
                self._sa_number = len(sa_files)
                self._sa_index = randrange(self._sa_number)
                fremote = f"sa{self._sa_index:03}"
                LOGGER.info(f"Upload with service account {fremote}")

        method = "move" if not self._listener.seed or self._listener.newDir else "copy"
        cmd = self._getUpdatedCommand(
            fconfig_path, path, f"{fremote}:{rc_path}", method, unwanted_files
        )
        if (
            remote_type == "drive"
            and not config_dict["RCLONE_FLAGS"]
            and not self._listener.rcFlags
        ):
            cmd.extend(("--drive-chunk-size", "128M", "--drive-upload-cutoff", "128M"))

        result = await self._start_upload(cmd, remote_type)
        if not result:
            return

        if remote_type == "drive":
            link, destination = await self._get_gdrive_link(
                oconfig_path, oremote, rc_path, mime_type
            )
        else:
            if mime_type == "Folder":
                destination = f"{oremote}:{rc_path}"
            elif rc_path:
                destination = f"{oremote}:{rc_path}/{self._listener.name}"
            else:
                destination = f"{oremote}:{self._listener.name}"

            cmd = ["rclone", "link", "--config", oconfig_path, destination]
            res, err, code = await cmd_exec(cmd)

            if code == 0:
                link = res
            elif code != -9:
                if not err:
                    err = "Use <code>/shell cat rlog.txt</code> to see more information"
                LOGGER.error(f"while getting link. Path: {destination} | Stderr: {err}")
                link = ""
        if self._listener.isCancelled:
            return
        LOGGER.info(f"Upload Done. Path: {destination}")
        if self._listener.seed and not self._listener.newDir:
            await clean_unwanted(path, ft_delete)
        await self._listener.onUploadComplete(
            link, files, folders, mime_type, destination
        )

    async def clone(self, config_path, src_remote, src_path, mime_type, method):
        destination = self._listener.upDest
        dst_remote, dst_path = destination.split(":", 1)

        try:
            src_remote_opts, dst_remote_opt = await gather(
                self._get_remote_options(config_path, src_remote),
                self._get_remote_options(config_path, dst_remote),
            )
        except Exception as err:
            await self._listener.onUploadError(str(err))
            return None, None

        src_remote_type, dst_remote_type = (
            src_remote_opts["type"],
            dst_remote_opt["type"],
        )

        cmd = self._getUpdatedCommand(
            config_path, f"{src_remote}:{src_path}", destination, method
        )
        if not self._listener.rcFlags and not config_dict["RCLONE_FLAGS"]:
            if src_remote_type == "drive" and dst_remote_type != "drive":
                cmd.append("--drive-acknowledge-abuse")
            elif src_remote_type == "drive":
                cmd.extend(("--tpslimit", "3", "--transfers", "3"))

        self._proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        _, return_code = await gather(self._progress(), self._proc.wait())

        if self._listener.isCancelled:
            return None, None

        if return_code == -9:
            return None, None
        elif return_code != 0:
            error = (
                (await self._proc.stderr.read()).decode().strip()
                or "Use <code>/shell cat rlog.txt</code> to see more information"
            )
            LOGGER.error(error)
            await self._listener.onUploadError(error[:4000])
            return None, None
        else:
            if dst_remote_type == "drive":
                link, destination = await self._get_gdrive_link(
                    config_path, dst_remote, dst_path, mime_type
                )
                return (
                    (None, None) if self._listener.isCancelled else (link, destination)
                )
            else:
                if mime_type != "Folder":
                    destination += (
                        f"/{self._listener.name}" if dst_path else self._listener.name
                    )

                cmd = ["rclone", "link", "--config", config_path, destination]
                res, err, code = await cmd_exec(cmd)

                if self._listener.isCancelled:
                    return None, None

                if code == 0:
                    return res, destination
                elif code != -9:
                    if not err:
                        err = "Use <code>/shell cat rlog.txt</code> to see more information"
                    LOGGER.error(
                        f"while getting link. Path: {destination} | Stderr: {err}"
                    )
                    return None, destination

    def _getUpdatedCommand(
        self, config_path, source, destination, method, unwanted_files=None
    ):
        if unwanted_files is None:
            unwanted_files = []
        ext = "*.{" + ",".join(self._listener.extensionFilter) + "}"
        cmd = [
            "rclone",
            method,
            "--fast-list",
            "--config",
            config_path,
            "-P",
            source,
            destination,
            "--exclude",
            ext,
            "--retries-sleep",
            "3s",
            "--ignore-case",
            "--low-level-retries",
            "1",
            "-M",
            "--log-file",
            "rlog.txt",
            "--log-level",
            "DEBUG",
        ]
        if rcflags := self._listener.rcFlags or config_dict["RCLONE_FLAGS"]:
            rcflags = rcflags.split("|")
            for flag in rcflags:
                if ":" in flag:
                    key, value = map(str.strip, flag.split(":", 1))
                    cmd.extend((key, value))
                elif len(flag) > 0:
                    cmd.append(flag.strip())
        if unwanted_files:
            for f in unwanted_files:
                cmd.extend(("--exclude", f.rsplit("/", 1)[1]))
        return cmd

    @staticmethod
    async def _get_remote_options(config_path, remote):
        config = ConfigParser()
        async with aiopen(config_path, "r") as f:
            contents = await f.read()
            config.read_string(contents)
        options = config.options(remote)
        return {opt: config.get(remote, opt) for opt in options}

    async def cancel_task(self):
        self._listener.isCancelled = True
        if self._proc is not None:
            try:
                self._proc.kill()
            except:
                pass
        if self._is_download:
            LOGGER.info(f"Cancelling Download: {self._listener.name}")
            await self._listener.onDownloadError("Download stopped by user!")
        elif self._is_upload:
            LOGGER.info(f"Cancelling Upload: {self._listener.name}")
            await self._listener.onUploadError("your upload has been stopped!")
        else:
            LOGGER.info(f"Cancelling Clone: {self._listener.name}")
            await self._listener.onUploadError("your clone has been stopped!")
