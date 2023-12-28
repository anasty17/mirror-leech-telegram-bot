from myjdapi import Myjdapi
from json import dump
from time import sleep
from asyncio import sleep as aiosleep
from random import randint
from aiofiles.os import listdir
from myjdapi.exception import (
    MYJDException,
    MYJDAuthFailedException,
    MYJDEmailForbiddenException,
    MYJDEmailInvalidException,
    MYJDErrorEmailNotConfirmedException,
)

from bot import config_dict, LOGGER, jd_lock, Intervals
from bot.helper.ext_utils.bot_utils import (
    cmd_exec,
    new_task,
    sync_to_async,
)


class JDownloader:
    def __init__(self):
        self.myjd = Myjdapi()
        self._username = ""
        self._password = ""
        self._device_name = ""
        self.error = "JDownloader Credentials not provided!"
        self.device = None
        self.myjd.set_app_key("mltb")

    @new_task
    async def initiate(self):
        self.boot()
        await aiosleep(10)
        await self.start()

    async def start(self):
        async with jd_lock:
            await sync_to_async(self.connect)
        if self.device is not None:
            await self.keepJdAlive()

    @new_task
    async def boot(self):
        await cmd_exec(["pkill", "-9", "java"])
        self.device = None
        if config_dict["JD_EMAIL"] and config_dict["JD_PASS"]:
            self.error = "Connecting... Try agin after couple of seconds"
            self._device_name = f"{randint(0, 1000)}"
            logs = await listdir("/JDownloader/logs")
            if len(logs) > 2:
                LOGGER.info("Starting JDownloader... This might take up to 5 sec")
            else:
                LOGGER.info(
                    "Starting JDownloader... This might take up to 15 sec and might restart once after build!"
                )
            jdata = {
                "autoconnectenabledv2": True,
                "password": config_dict["JD_PASS"],
                "devicename": f"{self._device_name}",
                "email": config_dict["JD_EMAIL"],
            }
            with open(
                "/JDownloader/cfg/org.jdownloader.api.myjdownloader.MyJDownloaderSettings.json",
                "w",
            ) as sf:
                sf.truncate(0)
                dump(jdata, sf)
            cmd = "java -Dsun.jnu.encoding=UTF-8 -Dfile.encoding=UTF-8 -Djava.awt.headless=true -jar /JDownloader/JDownloader.jar"
            _, __, code = await cmd_exec(cmd, shell=True)
            if code != -9:
                self.boot()

    def connect(self):
        LOGGER.info(f"Connecting to JDownloader...")
        try:
            self.myjd.connect(config_dict["JD_EMAIL"], config_dict["JD_PASS"])
            while True:
                self.myjd.update_devices()
                devices = self.myjd.list_devices()
                if devices:
                    for device in devices:
                        if self._device_name == device["name"]:
                            break
                    else:
                        continue
                else:
                    continue
                break
            self.device = self.myjd.get_device(f"{self._device_name}")
            self.device.enable_direct_connection()
            self.device.action("/device/ping")
            LOGGER.info(f"JDownloader is Connected!")
        except (
            MYJDAuthFailedException,
            MYJDEmailForbiddenException,
            MYJDEmailInvalidException,
            MYJDErrorEmailNotConfirmedException,
        ) as err:
            self.error = f"{err}".strip()
            LOGGER.info(f"Failed to connect with jdownloader! ERROR: {self.error}")
            self.device = None
            return
        except MYJDException as e:
            self.error = f"{e}".strip()
            LOGGER.info(
                f"Failed to connect with jdownloader! Retrying... ERROR: {self.error}"
            )
            sleep(10)
            return self.connect()

    @new_task
    async def keepJdAlive(self):
        while True:
            await aiosleep(30)
            if self.device is not None:
                break
            if not Intervals["jd"]:
                try:
                    await sync_to_async(self.device.action, "/device/ping")
                except:
                    pass


jdownloader = JDownloader()
