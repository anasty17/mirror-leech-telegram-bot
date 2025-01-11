from aiofiles import open as aiopen
from aiofiles.os import path as aiopath
from asyncio import create_subprocess_exec
from configparser import RawConfigParser

from ....core.config_manager import Config

RcloneServe = []


async def rclone_serve_booter():
    if not Config.RCLONE_SERVE_URL or not await aiopath.exists("rclone.conf"):
        if RcloneServe:
            try:
                RcloneServe[0].kill()
                RcloneServe.clear()
            except:
                pass
        return
    config = RawConfigParser()
    async with aiopen("rclone.conf", "r") as f:
        contents = await f.read()
        config.read_string(contents)
    if not config.has_section("combine"):
        upstreams = " ".join(f"{remote}={remote}:" for remote in config.sections())
        config.add_section("combine")
        config.set("combine", "type", "combine")
        config.set("combine", "upstreams", upstreams)
        with open("rclone.conf", "w") as f:
            config.write(f, space_around_delimiters=False)
    if RcloneServe:
        try:
            RcloneServe[0].kill()
            RcloneServe.clear()
        except:
            pass
    cmd = [
        "rclone",
        "serve",
        "http",
        "--config",
        "rclone.conf",
        "--no-modtime",
        "combine:",
        "--addr",
        f":{Config.RCLONE_SERVE_PORT}",
        "--vfs-cache-mode",
        "full",
        "--vfs-cache-max-age",
        "1m0s",
        "--buffer-size",
        "64M",
        "-v",
        "--log-systemd",
        "--log-file",
        "rlog.txt",
    ]
    if (user := Config.RCLONE_SERVE_USER) and (pswd := Config.RCLONE_SERVE_PASS):
        cmd.extend(("--user", user, "--pass", pswd))
    rcs = await create_subprocess_exec(*cmd)
    RcloneServe.append(rcs)
