from pytdbot import Client
from asyncio import Lock, sleep
from aiofiles.os import path

from .. import LOGGER
from .config_manager import Config


class TgManager:
    _lock = Lock()
    bot = None
    user = None
    NAME = ""
    ID = 0
    IS_PREMIUM_USER = False
    MAX_SPLIT_SIZE = 2097152000

    @classmethod
    async def start_clients(cls):
        LOGGER.info("Creating client from BOT_TOKEN")
        cls.ID = Config.BOT_TOKEN.split(":", 1)[0]
        is_amd64 = not (await path.exists("/tdlib"))
        cls.bot = Client(
            token=Config.BOT_TOKEN,
            api_id=Config.TELEGRAM_API,
            api_hash=Config.TELEGRAM_HASH,
            lib_path=None if is_amd64 else "/tdlib/lib/libtdjson.so",
            default_parse_mode="html",
            files_directory="/mltb/tdlib_bot",
            database_encryption_key="mltbmltb",
            use_file_database=False,
            workers=None,
        )
        await cls.bot.start()
        while cls.bot.authorization_state != "authorizationStateReady":
            await sleep(0.5)
        me = await cls.bot.getMe()
        cls.NAME = me.usernames.editable_username
        if not await path.exists("tdlib_user"):
            return
        LOGGER.info("Creating client from USER DATABASE")
        cls.user = Client(
            api_id=Config.TELEGRAM_API,
            api_hash=Config.TELEGRAM_HASH,
            lib_path=None if is_amd64 else "/tdlib/lib/libtdjson.so",
            default_parse_mode="html",
            files_directory="/mltb/tdlib_user",
            database_encryption_key="mltbmltb",
            use_file_database=False,
            workers=1,
            user_bot=True,
        )
        await cls.bot.client_manager.add_client(cls.user, True)
        await cls.user.getChats()
        me = await cls.user.getMe()
        cls.IS_PREMIUM_USER = me.is_premium
        if cls.IS_PREMIUM_USER:
            cls.MAX_SPLIT_SIZE = 4194304000

    @classmethod
    async def stop(cls):
        async with cls._lock:
            if cls.bot:
                await cls.bot.stop()
            if cls.user:
                await cls.user.stop()
            LOGGER.info("Client(s) stopped")
