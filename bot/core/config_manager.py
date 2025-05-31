import os
from importlib import import_module
from ast import literal_eval

HEROKU_ENV = os.environ.get('HEROKU_ENV', '').lower() == 'true'

class Config:
    # Define all possible config variables with their defaults
    # These defaults will be used if not set in config.py (non-heroku)
    # or if not set as env vars and no default specified in heroku_config.py get_config
    AS_DOCUMENT = False
    AUTHORIZED_CHATS = ""
    BASE_URL = ""
    BASE_URL_PORT = 80
    BOT_TOKEN = ""
    CMD_SUFFIX = ""
    DATABASE_URL = ""
    DEFAULT_UPLOAD = "rc"
    EQUAL_SPLITS = False
    EXCLUDED_EXTENSIONS = ""
    FFMPEG_CMDS = {}
    FILELION_API = ""
    GDRIVE_ID = ""
    INCOMPLETE_TASK_NOTIFIER = False
    INDEX_URL = ""
    IS_TEAM_DRIVE = False
    JD_EMAIL = ""
    JD_PASS = ""
    LEECH_DUMP_CHAT = ""
    LEECH_FILENAME_PREFIX = ""
    LEECH_SPLIT_SIZE = 2097152000
    MEDIA_GROUP = False
    HYBRID_LEECH = False
    HYDRA_IP = ""
    HYDRA_API_KEY = ""
    NAME_SUBSTITUTE = ""
    OWNER_ID = 0
    QUEUE_ALL = 0
    QUEUE_DOWNLOAD = 0
    QUEUE_UPLOAD = 0
    RCLONE_FLAGS = ""
    RCLONE_PATH = ""
    RCLONE_SERVE_URL = ""
    RCLONE_SERVE_USER = ""
    RCLONE_SERVE_PASS = ""
    RCLONE_SERVE_PORT = 8080
    RSS_CHAT = ""
    RSS_DELAY = 600
    RSS_SIZE_LIMIT = 0
    SEARCH_API_LINK = ""
    SEARCH_LIMIT = 0
    SEARCH_PLUGINS = []
    STATUS_LIMIT = 4
    STATUS_UPDATE_INTERVAL = 15
    STOP_DUPLICATE = False
    STREAMWISH_API = ""
    SUDO_USERS = ""
    TELEGRAM_API = 0
    TELEGRAM_HASH = ""
    TG_PROXY = {}
    THUMBNAIL_LAYOUT = ""
    TORRENT_TIMEOUT = 0
    UPLOAD_PATHS = {}
    UPSTREAM_REPO = ""
    UPSTREAM_BRANCH = "master"
    USENET_SERVERS = []
    USER_SESSION_STRING = ""
    USER_TRANSMISSION = False
    USE_SERVICE_ACCOUNTS = False
    WEB_PINCODE = False
    YT_DLP_OPTIONS = {}
    PORT = None # Added for Heroku


    @classmethod
    def _convert(cls, key, value):
        # Ensure key exists to get expected_type, otherwise default to type of value if not None else str
        if hasattr(cls, key):
            expected_type = type(getattr(cls, key))
        elif value is not None:
            expected_type = type(value)
        else:
            expected_type = str # Default assumption

        if value is None:
            return None
        if isinstance(value, expected_type):
            return value

        if expected_type == bool:
            return str(value).strip().lower() in {"true", "1", "yes"}

        if expected_type in [list, dict]:
            if not isinstance(value, str):
                raise TypeError(
                    f"{key} should be {expected_type.__name__}, got {type(value).__name__}"
                )

            try:
                evaluated = literal_eval(value)
                if isinstance(evaluated, expected_type):
                    return evaluated
                else:
                    raise TypeError
            except (ValueError, SyntaxError, TypeError) as e:
                raise TypeError(
                    f"{key} should be {expected_type.__name__}, got invalid string: {value}"
                ) from e
        try:
            return expected_type(value)
        except (ValueError, TypeError) as exc:
            raise TypeError(
                f"Invalid type for {key}: expected {expected_type}, got {type(value)}"
            ) from exc

    @classmethod
    def get(cls, key):
        return getattr(cls, key) if hasattr(cls, key) else None

    @classmethod
    def set(cls, key, value):
        if hasattr(cls, key):
            value = cls._convert(key, value)
            setattr(cls, key, value)
        else:
            raise KeyError(f"{key} is not a valid configuration key.")

    @classmethod
    def get_all(cls):
        return {
            key: getattr(cls, key)
            for key in cls.__dict__.keys()
            if not key.startswith("__") and not callable(getattr(cls, key))
        }

    @classmethod
    def load(cls):
        if HEROKU_ENV:
            from bot.heroku_config import (
                BOT_TOKEN, OWNER_ID, TELEGRAM_API, TELEGRAM_HASH, USER_SESSION_STRING,
                DATABASE_URL, CMD_SUFFIX, AUTHORIZED_CHATS, SUDO_USERS,
                DEFAULT_UPLOAD, STATUS_UPDATE_INTERVAL, STATUS_LIMIT,
                INCOMPLETE_TASK_NOTIFIER, NAME_SUBSTITUTE, EXCLUDED_EXTENSIONS,
                FILELION_API, STREAMWISH_API, GDRIVE_ID, IS_TEAM_DRIVE,
                USE_SERVICE_ACCOUNTS, STOP_DUPLICATE, INDEX_URL, RCLONE_PATH,
                RCLONE_FLAGS, RCLONE_SERVE_URL, RCLONE_SERVE_PORT,
                RCLONE_SERVE_USER, RCLONE_SERVE_PASS, JD_EMAIL, JD_PASS,
                HYDRA_IP, HYDRA_API_KEY, UPSTREAM_REPO, UPSTREAM_BRANCH,
                LEECH_SPLIT_SIZE, AS_DOCUMENT, EQUAL_SPLITS, MEDIA_GROUP,
                USER_TRANSMISSION, HYBRID_LEECH, LEECH_FILENAME_PREFIX,
                LEECH_DUMP_CHAT, THUMBNAIL_LAYOUT, TORRENT_TIMEOUT, BASE_URL,
                BASE_URL_PORT, WEB_PINCODE, TG_PROXY, YT_DLP_OPTIONS, FFMPEG_CMDS,
                UPLOAD_PATHS, USENET_SERVERS, QUEUE_ALL, QUEUE_DOWNLOAD,
                QUEUE_UPLOAD, RSS_DELAY, RSS_CHAT, RSS_SIZE_LIMIT,
                SEARCH_API_LINK, SEARCH_LIMIT, SEARCH_PLUGINS, PORT
            )

            heroku_configs = {
                "BOT_TOKEN": BOT_TOKEN, "OWNER_ID": OWNER_ID, "TELEGRAM_API": TELEGRAM_API,
                "TELEGRAM_HASH": TELEGRAM_HASH, "USER_SESSION_STRING": USER_SESSION_STRING,
                "DATABASE_URL": DATABASE_URL, "CMD_SUFFIX": CMD_SUFFIX,
                "AUTHORIZED_CHATS": AUTHORIZED_CHATS, "SUDO_USERS": SUDO_USERS,
                "DEFAULT_UPLOAD": DEFAULT_UPLOAD, "STATUS_UPDATE_INTERVAL": STATUS_UPDATE_INTERVAL,
                "STATUS_LIMIT": STATUS_LIMIT, "INCOMPLETE_TASK_NOTIFIER": INCOMPLETE_TASK_NOTIFIER,
                "NAME_SUBSTITUTE": NAME_SUBSTITUTE, "EXCLUDED_EXTENSIONS": EXCLUDED_EXTENSIONS,
                "FILELION_API": FILELION_API, "STREAMWISH_API": STREAMWISH_API,
                "GDRIVE_ID": GDRIVE_ID, "IS_TEAM_DRIVE": IS_TEAM_DRIVE,
                "USE_SERVICE_ACCOUNTS": USE_SERVICE_ACCOUNTS, "STOP_DUPLICATE": STOP_DUPLICATE,
                "INDEX_URL": INDEX_URL, "RCLONE_PATH": RCLONE_PATH, "RCLONE_FLAGS": RCLONE_FLAGS,
                "RCLONE_SERVE_URL": RCLONE_SERVE_URL, "RCLONE_SERVE_PORT": RCLONE_SERVE_PORT,
                "RCLONE_SERVE_USER": RCLONE_SERVE_USER, "RCLONE_SERVE_PASS": RCLONE_SERVE_PASS,
                "JD_EMAIL": JD_EMAIL, "JD_PASS": JD_PASS, "HYDRA_IP": HYDRA_IP,
                "HYDRA_API_KEY": HYDRA_API_KEY, "UPSTREAM_REPO": UPSTREAM_REPO,
                "UPSTREAM_BRANCH": UPSTREAM_BRANCH, "LEECH_SPLIT_SIZE": LEECH_SPLIT_SIZE,
                "AS_DOCUMENT": AS_DOCUMENT, "EQUAL_SPLITS": EQUAL_SPLITS,
                "MEDIA_GROUP": MEDIA_GROUP, "USER_TRANSMISSION": USER_TRANSMISSION,
                "HYBRID_LEECH": HYBRID_LEECH, "LEECH_FILENAME_PREFIX": LEECH_FILENAME_PREFIX,
                "LEECH_DUMP_CHAT": LEECH_DUMP_CHAT, "THUMBNAIL_LAYOUT": THUMBNAIL_LAYOUT,
                "TORRENT_TIMEOUT": TORRENT_TIMEOUT, "BASE_URL": BASE_URL,
                "BASE_URL_PORT": BASE_URL_PORT, "WEB_PINCODE": WEB_PINCODE,
                "TG_PROXY": TG_PROXY, "YT_DLP_OPTIONS": YT_DLP_OPTIONS,
                "FFMPEG_CMDS": FFMPEG_CMDS, "UPLOAD_PATHS": UPLOAD_PATHS,
                "USENET_SERVERS": USENET_SERVERS, "QUEUE_ALL": QUEUE_ALL,
                "QUEUE_DOWNLOAD": QUEUE_DOWNLOAD, "QUEUE_UPLOAD": QUEUE_UPLOAD,
                "RSS_DELAY": RSS_DELAY, "RSS_CHAT": RSS_CHAT, "RSS_SIZE_LIMIT": RSS_SIZE_LIMIT,
                "SEARCH_API_LINK": SEARCH_API_LINK, "SEARCH_LIMIT": SEARCH_LIMIT,
                "SEARCH_PLUGINS": SEARCH_PLUGINS, "PORT": PORT
            }

            for key, value in heroku_configs.items():
                if hasattr(cls, key):
                    # Use _convert for type consistency if value is not None
                    # If value is None, it means it wasn't set in env and no default in heroku_config's get_config
                    # In this case, the class default attribute should prevail.
                    if value is not None:
                        converted_value = cls._convert(key, value)
                        setattr(cls, key, converted_value)
                    # If value is None from heroku_config, we keep the class default (e.g. PORT = None)
                    # unless heroku_config provided a specific default like `default=0` for an int.
                    # The heroku_config.get_config handles providing defaults if env var is missing.
                    # So, if 'value' here is None, it means it was truly not set and had no default in get_config.
        else:
            # Original logic for non-Heroku environments
            try:
                settings = import_module("config")
                for attr in dir(settings):
                    if (
                        not attr.startswith("__")
                        and not callable(getattr(settings, attr))
                        and hasattr(cls, attr)
                    ):
                        value = getattr(settings, attr)
                        # if not value and value != False and value != 0: # Original check: `if not value:`
                        # The original check `if not value:` would skip False, 0, empty strings/lists/dicts.
                        # This should be fine as _convert handles types.
                        # Let's refine to only skip if value is None, to allow False/0/empty collections from config.py
                        if value is None:
                            continue

                        value = cls._convert(attr, value)
                        if isinstance(value, str):
                            value = value.strip()

                        # Specific value adjustments from original logic
                        if attr == "DEFAULT_UPLOAD" and value != "gd":
                            value = "rc"
                        elif attr in [
                            "BASE_URL", "RCLONE_SERVE_URL", "INDEX_URL", "SEARCH_API_LINK",
                        ] and value: # Ensure value is not None before stripping
                            value = value.strip("/")
                        elif attr == "USENET_SERVERS":
                            try:
                                if not value or not value[0].get("host"): # Check if list is empty or first host is missing
                                    value = [] # Set to empty list if invalid
                            except:
                                value = [] # Set to empty list on error
                        setattr(cls, attr, value)
            except ImportError:
                print("Warning: 'config.py' not found. Using default values defined in Config class.")
                # Defaults defined in Config class will be used.
                # Essential vars check below will still apply.

        # Common validation for essential variables for both Heroku and local
        for key in ["BOT_TOKEN", "OWNER_ID", "TELEGRAM_API", "TELEGRAM_HASH"]:
            value = getattr(cls, key)
            is_missing_str = isinstance(value, str) and not value.strip()
            is_missing_int = isinstance(value, int) and value == 0 # Assuming 0 is invalid for ID/API
            if value is None or is_missing_str or (key in ["OWNER_ID", "TELEGRAM_API"] and is_missing_int):
                raise ValueError(f"{key} variable is missing or invalid!")

                raise ValueError(f"{key} variable is missing or invalid!")

    @classmethod
    def load_dict(cls, config_dict):
        for key, value in config_dict.items():
            if hasattr(cls, key):
                value = cls._convert(key, value)
                if key == "DEFAULT_UPLOAD" and value != "gd":
                    value = "rc"
                elif key in [
                    "BASE_URL",
                    "RCLONE_SERVE_URL",
                    "INDEX_URL",
                    "SEARCH_API_LINK",
                ]:
                    if value:
                        value = value.strip("/")
                elif key == "USENET_SERVERS":
                    try:
                        if not value[0].get("host"):
                            value = []
                    except:
                        value = []
                setattr(cls, key, value)
        for key in ["BOT_TOKEN", "OWNER_ID", "TELEGRAM_API", "TELEGRAM_HASH"]:
            value = getattr(cls, key)
            if isinstance(value, str):
                value = value.strip()
            if not value:
                raise ValueError(f"{key} variable is missing!")
