from pytdbot import Client, ClientManager
from pytdbot.types import AutoDownloadSettings, NetworkTypeOther
from asyncio import Lock, sleep
from aiofiles.os import path

from .. import LOGGER
from .config_manager import Config


class TgManager:
    _lock = Lock()
    bot = None
    user = None
    client_manager = None
    NAME = ""
    ID = 0
    IS_PREMIUM_USER = False
    MAX_SPLIT_SIZE = 2097152000

    @classmethod
    async def start_clients(cls):
        LOGGER.info("Creating client from BOT_TOKEN")
        cls.ID = Config.BOT_TOKEN.split(":", 1)[0]
        is_armv7 = await path.exists("/tdlib")
        cls.bot = Client(
            token=Config.BOT_TOKEN,
            api_id=Config.TELEGRAM_API,
            api_hash=Config.TELEGRAM_HASH,
            lib_path="/tdlib/lib/libtdjson.so" if is_armv7 else None,
            default_parse_mode="html",
            files_directory="/mltb/tdlib_bot",
            database_encryption_key="mltbmltb",
            use_file_database=False,
            workers=None,
            td_verbosity=1,
        )
        if await path.exists("tdlib_user"):
            LOGGER.info("Creating client from USER DATABASE")
            cls.user = Client(
                api_id=Config.TELEGRAM_API,
                api_hash=Config.TELEGRAM_HASH,
                lib_path="/tdlib/lib/libtdjson.so" if is_armv7 else None,
                default_parse_mode="html",
                files_directory="/mltb/tdlib_user",
                database_encryption_key="mltbmltb",
                use_file_database=False,
                workers=None,
                td_verbosity=1,
                user_bot=True,
            )
        clients = [cls.bot]
        if cls.user:
            clients.append(cls.user)
        cls.client_manager = ClientManager(
            clients,
            lib_path="/tdlib/lib/libtdjson.so" if is_armv7 else None,
            verbosity=1,
        )
        await cls.client_manager.start()
        while cls.bot.authorization_state != "authorizationStateReady":
            await sleep(0.5)
        await cls.bot.setAutoDownloadSettings(
            AutoDownloadSettings(), NetworkTypeOther()
        )
        me = await cls.bot.getMe()
        cls.NAME = me.usernames.editable_username
        if cls.user:
            await cls.user.getChats()
            me = await cls.user.getMe()
            cls.IS_PREMIUM_USER = me.is_premium
            if cls.IS_PREMIUM_USER:
                cls.MAX_SPLIT_SIZE = 4194304000
            await cls.user.setAutoDownloadSettings(
                AutoDownloadSettings(), NetworkTypeOther()
            )

    @classmethod
    async def stop(cls):
        async with cls._lock:
            await cls.bot.stop()
            if cls.user:
                await cls.user.stop()
            await cls.client_manager.close()
            LOGGER.info("Client(s) stopped")
