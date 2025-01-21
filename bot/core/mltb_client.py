from pyrogram import Client, enums
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
        cls.bot = Client(
            "bot",
            Config.TELEGRAM_API,
            Config.TELEGRAM_HASH,
            bot_token=Config.BOT_TOKEN,
            parse_mode=enums.ParseMode.HTML,
            max_concurrent_transmissions=10,
        )
        await cls.bot.start()
        cls.NAME = cls.bot.me.username
        cls.ID = Config.BOT_TOKEN.split(":", 1)[0]

    @classmethod
    async def start_user(cls):
        if Config.USER_SESSION_STRING:
            LOGGER.info("Creating client from USER_SESSION_STRING")
            try:
                cls.user = Client(
                    "user",
                    Config.TELEGRAM_API,
                    Config.TELEGRAM_HASH,
                    session_string=Config.USER_SESSION_STRING,
                    parse_mode=enums.ParseMode.HTML,
                    sleep_threshold=60,
                    max_concurrent_transmissions=10,
                )
                await cls.user.start()
                cls.IS_PREMIUM_USER = cls.user.me.is_premium
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

    @classmethod
    async def reload(cls):
        async with cls._lock:
            await cls.bot.restart()
            if cls.user:
                await cls.user.restart()
            LOGGER.info("Client(s) restarted")
