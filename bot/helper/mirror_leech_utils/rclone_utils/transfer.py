from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, makedirs, listdir
from asyncio import create_subprocess_exec, gather, sleep, wait_for
from asyncio.subprocess import PIPE
from configparser import RawConfigParser
from json import loads
from logging import getLogger
from random import randrange
from re import findall as re_findall

from ....core.config_manager import Config
from ...ext_utils.bot_utils import cmd_exec, sync_to_async
from ...ext_utils.files_utils import (
    get_mime_type,
    count_files_and_folders,
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
        self._use_service_accounts = Config.USE_SERVICE_ACCOUNTS
        self._rclone_select = False

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
        while not (
            self._proc.returncode is not None
            or self._proc.stdout.at_eof()
            or self._listener.is_cancelled
        ):
            try:
                data = await wait_for(self._proc.stdout.readline(), 60)
            except:
                break
            if not data:
                break
            data = data.decode().strip()
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
            await sleep(0.05)

    def _switch_service_account(self):
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
        await self._progress()
        _, stderr = await self._proc.communicate()
        return_code = self._proc.returncode
        if self._listener.is_cancelled:
            return

        if return_code == 0:
            await self._listener.on_download_complete()
        elif return_code != -9:
            error = stderr.decode().strip()
            if not error and remote_type == "drive" and self._use_service_accounts:
                error = "Mostly your service accounts don't have access to this drive!"
            LOGGER.error(error)

            if (
                self._sa_number != 0
                and remote_type == "drive"
                and "RATE_LIMIT_EXCEEDED" in error
                and self._use_service_accounts
            ):
                if self._sa_count < self._sa_number:
                    remote = self._switch_service_account()
                    cmd[6] = f"{remote}:{cmd[6].split(':', 1)[1]}"
                    if self._listener.is_cancelled:
                        return
                    return await self._start_download(cmd, remote_type)
                else:
                    LOGGER.info(
                        f"Reached maximum number of service accounts switching, which is {self._sa_count}"
                    )

            await self._listener.on_download_error(error[:4000])
            return

    async def download(self, remote, config_path, path):
        self._is_download = True
        try:
            remote_opts = await self._get_remote_options(config_path, remote)
        except Exception as err:
            await self._listener.on_download_error(str(err))
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

        cmd = self._get_updated_command(
            config_path, f"{remote}:{self._listener.link}", path, "copy"
        )

        if remote_type == "drive" and not self._listener.rc_flags:
            cmd.extend(
                (
                    "--drive-acknowledge-abuse",
                    "--drive-chunk-size",
                    "128M",
                    "--tpslimit",
                    "1",
                    "--tpslimit-burst",
                    "1",
                    "--transfers",
                    "1",
                )
            )

        await self._start_download(cmd, remote_type)

    async def _get_gdrive_link(self, config_path, destination, mime_type):
        epath = destination.rsplit("/", 1)[0] if mime_type == "Folder" else destination
        cmd = [
            "rclone",
            "lsjson",
            "--fast-list",
            "--no-mimetype",
            "--no-modtime",
            "--config",
            config_path,
            epath,
            "-v",
            "--log-systemd",
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
            LOGGER.error(
                f"while getting drive link. Path: {destination}. Stderr: {err}"
            )
            link = ""
        return link

    async def _start_upload(self, cmd, remote_type):
        self._proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        await self._progress()
        _, stderr = await self._proc.communicate()
        return_code = self._proc.returncode

        if self._listener.is_cancelled:
            return False
        if return_code == -9:
            return False
        elif return_code == 0:
            return True
        else:
            error = stderr.decode().strip()
            LOGGER.error(error)
            if (
                self._sa_number != 0
                and remote_type == "drive"
                and "RATE_LIMIT_EXCEEDED" in error
                and self._use_service_accounts
            ):
                if self._sa_count < self._sa_number:
                    remote = self._switch_service_account()
                    cmd[7] = f"{remote}:{cmd[7].split(':', 1)[1]}"
                    return (
                        False
                        if self._listener.is_cancelled
                        else await self._start_upload(cmd, remote_type)
                    )
                else:
                    LOGGER.info(
                        f"Reached maximum number of service accounts switching, which is {self._sa_count}"
                    )
            await self._listener.on_upload_error(error[:4000])
            return False

    async def upload(self, path):
        self._is_upload = True
        rc_path = self._listener.up_dest
        if rc_path.startswith("mrcc:"):
            rc_path = rc_path.split("mrcc:", 1)[1]
            oconfig_path = f"rclone/{self._listener.user_id}.conf"
        else:
            oconfig_path = "rclone.conf"

        oremote, rc_path = rc_path.split(":", 1)

        if await aiopath.isdir(path):
            mime_type = "Folder"
            folders, files = await count_files_and_folders(path)
            rc_path += f"/{self._listener.name}" if rc_path else self._listener.name
        else:
            mime_type = await sync_to_async(get_mime_type, path)
            folders = 0
            files = 1

        try:
            remote_opts = await self._get_remote_options(oconfig_path, oremote)
        except Exception as err:
            await self._listener.on_upload_error(str(err))
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

        method = "move"
        cmd = self._get_updated_command(
            fconfig_path, path, f"{fremote}:{rc_path}", method
        )
        if remote_type == "drive" and not self._listener.rc_flags:
            cmd.extend(
                (
                    "--drive-chunk-size",
                    "128M",
                    "--drive-upload-cutoff",
                    "128M",
                    "--tpslimit",
                    "1",
                    "--tpslimit-burst",
                    "1",
                    "--transfers",
                    "1",
                )
            )

        result = await self._start_upload(cmd, remote_type)
        if not result:
            return

        if mime_type == "Folder":
            destination = f"{oremote}:{rc_path}"
        elif rc_path:
            destination = f"{oremote}:{rc_path}/{self._listener.name}"
        else:
            destination = f"{oremote}:{self._listener.name}"

        if remote_type == "drive":
            link = await self._get_gdrive_link(oconfig_path, destination, mime_type)
        else:
            cmd = [
                "rclone",
                "link",
                "--config",
                oconfig_path,
                destination,
                "-v",
                "--log-systemd",
            ]
            res, err, code = await cmd_exec(cmd)

            if code == 0:
                link = res
            elif code != -9:
                LOGGER.error(f"while getting link. Path: {destination} | Stderr: {err}")
                link = ""
        if self._listener.is_cancelled:
            return
        LOGGER.info(f"Upload Done. Path: {destination}")
        await self._listener.on_upload_complete(
            link, files, folders, mime_type, destination
        )
        return

    async def clone(self, config_path, src_remote, src_path, mime_type, method):
        destination = self._listener.up_dest
        dst_remote, dst_path = destination.split(":", 1)

        try:
            src_remote_opts, dst_remote_opt = await gather(
                self._get_remote_options(config_path, src_remote),
                self._get_remote_options(config_path, dst_remote),
            )
        except Exception as err:
            await self._listener.on_upload_error(str(err))
            return None, None

        src_remote_type, dst_remote_type = (
            src_remote_opts["type"],
            dst_remote_opt["type"],
        )

        cmd = self._get_updated_command(
            config_path, f"{src_remote}:{src_path}", destination, method
        )
        if not self._listener.rc_flags and src_remote_type == "drive":
            cmd.extend(
                (
                    "--drive-acknowledge-abuse",
                    "--tpslimit",
                    "3",
                    "--tpslimit-burst",
                    "1",
                    "--transfers",
                    "3",
                )
            )

        self._proc = await create_subprocess_exec(*cmd, stdout=PIPE, stderr=PIPE)
        await self._progress()
        _, stderr = await self._proc.communicate()
        return_code = self._proc.returncode

        if self._listener.is_cancelled:
            return None, None

        if return_code == -9:
            return None, None
        elif return_code == 0:
            if mime_type != "Folder":
                destination += (
                    f"/{self._listener.name}" if dst_path else self._listener.name
                )
            if dst_remote_type == "drive":
                link = await self._get_gdrive_link(config_path, destination, mime_type)
                return (
                    (None, None) if self._listener.is_cancelled else (link, destination)
                )
            else:
                cmd = [
                    "rclone",
                    "link",
                    "--config",
                    config_path,
                    destination,
                    "-v",
                    "--log-systemd",
                ]
                res, err, code = await cmd_exec(cmd)

                if self._listener.is_cancelled:
                    return None, None

                if code == 0:
                    return res, destination
                elif code != -9:
                    LOGGER.error(
                        f"while getting link. Path: {destination} | Stderr: {err}"
                    )
                    return None, destination

        else:
            error = stderr.decode().strip()
            LOGGER.error(error)
            await self._listener.on_upload_error(error[:4000])
            return None, None

    def _get_updated_command(
        self,
        config_path,
        source,
        destination,
        method,
    ):
        if source.split(":")[-1].startswith("rclone_select"):
            source = f"{source.split(":")[0]}:"
            self._rclone_select = True
        else:
            ext = "*.{" + ",".join(self._listener.excluded_extensions) + "}"
        cmd = [
            "rclone",
            method,
            "--fast-list",
            "--config",
            config_path,
            "-P",
            source,
            destination,
            "-L",
            "--retries-sleep",
            "3s",
            "--ignore-case",
            "--low-level-retries",
            "1",
            "-M",
            "-v",
            "--log-systemd",
        ]
        if self._rclone_select:
            cmd.extend(("--files-from", self._listener.link))
        else:
            cmd.extend(("--exclude", ext))
        if rcflags := self._listener.rc_flags:
            rcflags = rcflags.split("|")
            for flag in rcflags:
                if ":" in flag:
                    key, value = map(str.strip, flag.split(":", 1))
                    cmd.extend((key, value))
                elif len(flag) > 0:
                    cmd.append(flag.strip())
        return cmd

    @staticmethod
    async def _get_remote_options(config_path, remote):
        config = RawConfigParser()
        async with aiopen(config_path, "r") as f:
            contents = await f.read()
            config.read_string(contents)
        options = config.options(remote)
        return {opt: config.get(remote, opt) for opt in options}

    async def cancel_task(self):
        self._listener.is_cancelled = True
        if self._proc is not None:
            try:
                self._proc.kill()
            except:
                pass
        if self._is_download:
            LOGGER.info(f"Cancelling Download: {self._listener.name}")
            await self._listener.on_download_error("Stopped by user!")
        elif self._is_upload:
            LOGGER.info(f"Cancelling Upload: {self._listener.name}")
            await self._listener.on_upload_error("your upload has been stopped!")
        else:
            LOGGER.info(f"Cancelling Clone: {self._listener.name}")
            await self._listener.on_upload_error("your clone has been stopped!")
