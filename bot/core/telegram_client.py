from pytdbot import Client
from asyncio import Lock

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
        cls.bot = Client(
            token=Config.BOT_TOKEN,
            api_id=Config.TELEGRAM_API,
            api_hash=Config.TELEGRAM_HASH,
            default_parse_mode="html",
            files_directory="/mltb/tdlib_bot",
            workers=None,
        )
        await cls.bot.start()
        me = await cls.bot.getMe()
        cls.NAME = me.usernames.editable_username

    @classmethod
    async def start_user(cls):
        if Config.USER_SESSION_STRING:
            LOGGER.info("Creating client from USER_SESSION_STRING")
            try:
                cls.user = Client(
                    api_id=Config.TELEGRAM_API,
                    api_hash=Config.TELEGRAM_HASH,
                    default_parse_mode="html",
                    files_directory="/mltb/tdlib_user",
                    user_bot=True,
                    workers=1,
                )
                await cls.user.start()
                await cls.user.getChats()
                me = await cls.bot.getMe()
                cls.IS_PREMIUM_USER = me.is_premium
                if cls.IS_PREMIUM_USER:
                    cls.MAX_SPLIT_SIZE = 4194304000
            except Exception as e:
                LOGGER.error(f"Failed to start client from USER_SESSION_STRING. {e}")
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
