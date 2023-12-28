from myjdapi import Myjdapi
from myjdapi.exception import (
    MYJDException,
    MYJDAuthFailedException,
    MYJDEmailForbiddenException,
    MYJDEmailInvalidException,
    MYJDErrorEmailNotConfirmedException,
)
from json import dump
from time import sleep
from random import randint
from aiofiles.os import listdir

from bot import config_dict, LOGGER
from bot.helper.ext_utils.bot_utils import cmd_exec, new_task


class JDownloader:
    def __init__(self):
        self.myjd = Myjdapi()
        self._username = ""
        self._password = ""
        self._device_name = ""
        self.device = None
        self.myjd.set_app_key("mltb")

    async def intiate(self):
        self.boot()

    @new_task
    async def boot(self):
        await cmd_exec(["pkill", "-9", "java"])
        self.device = None
        if config_dict["JD_EMAIL"]:
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
                await self.intiate()

    def connect(self):
        LOGGER.info(f"Connecting to JDownloader...")
        try:
            self.myjd.connect(config_dict["JD_EMAIL"], config_dict["JD_PASS"])
            sleep(0.5)
            self.device = self.myjd.get_device(f"{self._device_name}")
            self.device.enable_direct_connection()
            self.device.linkgrabber.query_packages()
        except (
            MYJDAuthFailedException,
            MYJDEmailForbiddenException,
            MYJDEmailInvalidException,
            MYJDErrorEmailNotConfirmedException,
        ) as err:
            LOGGER.info(f"Failed to connect with jdownloader!ERROR: {err}".strip())
            self.device = None
            raise err
        except MYJDException as e:
            LOGGER.info(
                f"Failed to connect with jdownloader! Retrying... ERROR: {e}".strip()
            )
            sleep(10)
            return self.connect()


jdownloader = JDownloader()
