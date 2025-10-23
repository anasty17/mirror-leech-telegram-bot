from pytdbot import Client
from asyncio import Lock
from aiofiles.os import path

from .. import LOGGER
from .config_manager import Config


class TgClient:
    _lock = Lock()
    bot = None
    user = None
    NAME = ""
    ID = 0
    IS_PREMIUM_USER = False
    MAX_SPLIT_SIZE = 2097152000

    @classmethod
    async def start_bot(cls):
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
            database_encryption_key = "mltbmltb",
            use_file_database=False,
            workers=None,
        )
        await cls.bot.start()
        me = await cls.bot.getMe()
        cls.NAME = me.usernames.editable_username

    @classmethod
    async def start_user(cls):
        if not await path.exists("tdlib_user"):
            return
        LOGGER.info("Creating client from USER DATABASE")
        is_amd64 = not (await path.exists("/tdlib"))
        try:
            cls.user = Client(
                api_id=Config.TELEGRAM_API,
                api_hash=Config.TELEGRAM_HASH,
                lib_path=None if is_amd64 else "/tdlib/lib/libtdjson.so",
                default_parse_mode="html",
                files_directory="/mltb/tdlib_user",
                use_file_database=False,
            )
            await cls.user.start()
            await cls.user.getChats()
            me = await cls.bot.getMe()
            cls.IS_PREMIUM_USER = me.is_premium
            if cls.IS_PREMIUM_USER:
                cls.MAX_SPLIT_SIZE = 4194304000
        except Exception as e:
            LOGGER.error(f"Failed to start client from USER DATABASE. {e}")
            cls.IS_PREMIUM_USER = False
            cls.user = None

    @classmethod
    async def stop(cls):
        async with cls._lock:
            if cls.bot:
                await cls.bot.stop()
            if cls.user:
                await cls.user.stop()
            LOGGER.info("Client(s) stopped")
