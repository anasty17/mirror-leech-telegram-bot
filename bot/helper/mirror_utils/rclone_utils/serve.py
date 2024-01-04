from asyncio import create_subprocess_exec
from aiofiles.os import path as aiopath
from aiofiles import open as aiopen
from configparser import ConfigParser

from bot import config_dict

RcloneServe = []


async def rclone_serve_booter():
    if not config_dict["RCLONE_SERVE_URL"] or not await aiopath.exists("rclone.conf"):
        if RcloneServe:
            try:
                RcloneServe[0].kill()
                RcloneServe.clear()
            except:
                pass
        return
    config = ConfigParser()
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
        f":{config_dict['RCLONE_SERVE_PORT']}",
        "--vfs-cache-mode",
        "full",
        "--vfs-cache-max-age",
        "1m0s",
        "--buffer-size",
        "64M",
    ]
    if (user := config_dict["RCLONE_SERVE_USER"]) and (
        pswd := config_dict["RCLONE_SERVE_PASS"]
    ):
        cmd.extend(("--user", user, "--pass", pswd))
    rcs = await create_subprocess_exec(*cmd)
    RcloneServe.append(rcs)
