from importlib import import_module
from ast import literal_eval
from typing import Any, Dict, List, Optional
import os


class Config:
    AS_DOCUMENT: bool = False
    AUTHORIZED_CHATS: str = ""
    BASE_URL: str = ""
    BASE_URL_PORT: int = 80
    BOT_TOKEN: str = ""
    CMD_SUFFIX: str = ""
    DATABASE_URL: str = ""
    DEFAULT_UPLOAD: str = "rc"
    EQUAL_SPLITS: bool = False
    EXCLUDED_EXTENSIONS: str = ""
    FFMPEG_CMDS: Dict[str, Any] = {}
    FILELION_API: str = ""
    GDRIVE_ID: str = ""
    INCOMPLETE_TASK_NOTIFIER: bool = False
    INDEX_URL: str = ""
    IS_TEAM_DRIVE: bool = False
    JD_EMAIL: str = ""
    JD_PASS: str = ""
    LEECH_DUMP_CHAT: str = ""
    LEECH_FILENAME_PREFIX: str = ""
    LEECH_SPLIT_SIZE: int = 2097152000
    MEDIA_GROUP: bool = False
    HYBRID_LEECH: bool = False
    HYDRA_IP: str = ""
    HYDRA_API_KEY: str = ""
    NAME_SUBSTITUTE: str = ""
    OWNER_ID: int = 0
    QUEUE_ALL: int = 0
    QUEUE_DOWNLOAD: int = 0
    QUEUE_UPLOAD: int = 0
    RCLONE_FLAGS: str = ""
    RCLONE_PATH: str = ""
    RCLONE_SERVE_URL: str = ""
    RCLONE_SERVE_USER: str = ""
    RCLONE_SERVE_PASS: str = ""
    RCLONE_SERVE_PORT: int = 8080
    RSS_CHAT: str = ""
    RSS_DELAY: int = 600
    RSS_SIZE_LIMIT: int = 0
    SEARCH_API_LINK: str = ""
    SEARCH_LIMIT: int = 0
    SEARCH_PLUGINS: List[str] = []
    STATUS_LIMIT: int = 4
    STATUS_UPDATE_INTERVAL: int = 15
    STOP_DUPLICATE: bool = False
    STREAMWISH_API: str = ""
    SUDO_USERS: str = ""
    TELEGRAM_API: int = 0
    TELEGRAM_HASH: str = ""
    TG_PROXY: Dict[str, Any] = {}
    THUMBNAIL_LAYOUT: str = ""
    TORRENT_TIMEOUT: int = 0
    UPLOAD_PATHS: Dict[str, str] = {}
    UPSTREAM_REPO: str = ""
    UPSTREAM_BRANCH: str = "master"
    USENET_SERVERS: List[Dict[str, Any]] = []
    USER_SESSION_STRING: str = ""
    USER_TRANSMISSION: bool = False
    USE_SERVICE_ACCOUNTS: bool = False
    WEB_PINCODE: bool = False
    YT_DLP_OPTIONS: Dict[str, Any] = {}

    @classmethod
    def _convert(cls, key: str, value: Any) -> Any:
        """Convert value to the expected type for the given key."""
        if not hasattr(cls, key):
            raise KeyError(f"{key} is not a valid configuration key.")

        expected_type = type(getattr(cls, key))

        if value is None:
            return None

        if isinstance(value, expected_type):
            return value

        if expected_type is bool:
            return str(value).strip().lower() in {"true", "1", "yes"}

        if expected_type in [list, dict]:
            if not isinstance(value, str):
                raise TypeError(f"{key} should be {expected_type.__name__}, got {type(value).__name__}")

            if not value:
                return expected_type()

            try:
                evaluated = literal_eval(value)
                if not isinstance(evaluated, expected_type):
                    raise TypeError(f"Expected {expected_type.__name__}, got {type(evaluated).__name__}")
                return evaluated
            except (ValueError, SyntaxError, TypeError) as e:
                raise TypeError(f"{key} should be {expected_type.__name__}, got invalid string: {value}") from e

        try:
            return expected_type(value)
        except (ValueError, TypeError) as exc:
            raise TypeError(f"Invalid type for {key}: expected {expected_type}, got {type(value)}") from exc

    @classmethod
    def get(cls, key: str) -> Any:
        """Get configuration value by key."""
        return getattr(cls, key, None)

    @classmethod
    def set(cls, key: str, value: Any) -> None:
        """Set configuration value by key."""
        if not hasattr(cls, key):
            raise KeyError(f"{key} is not a valid configuration key.")

        converted_value = cls._convert(key, value)
        setattr(cls, key, converted_value)

    @classmethod
    def get_all(cls) -> Dict[str, Any]:
        """Get all configuration values."""
        return {key: getattr(cls, key) for key in cls.__dict__.keys() if not key.startswith("__") and not callable(getattr(cls, key))}

    @classmethod
    def _is_valid_config_attr(cls, attr: str) -> bool:
        """Check if attribute is a valid config attribute."""
        if attr.startswith("__") or callable(getattr(cls, attr, None)):
            return False
        return hasattr(cls, attr)

    @classmethod
    def _process_config_value(cls, attr: str, value: Any) -> Optional[Any]:
        """Process and validate a config value."""
        if not value:
            return None

        converted_value = cls._convert(attr, value)

        if isinstance(converted_value, str):
            converted_value = converted_value.strip()

        # Apply specific transformations
        if attr == "DEFAULT_UPLOAD" and converted_value != "gd":
            return "rc"

        if attr in ["BASE_URL", "RCLONE_SERVE_URL", "INDEX_URL", "SEARCH_API_LINK"]:
            return converted_value.strip("/") if converted_value else ""

        if attr == "USENET_SERVERS":
            if not converted_value or not converted_value[0].get("host"):
                return None

        return converted_value

    @classmethod
    def _load_from_module(cls) -> bool:
        """Load configuration from config module. Returns True if successful."""
        try:
            settings = import_module("config")
        except ModuleNotFoundError:
            return False

        for attr in dir(settings):
            if not cls._is_valid_config_attr(attr):
                continue

            raw_value = getattr(settings, attr)
            processed_value = cls._process_config_value(attr, raw_value)

            if processed_value is not None:
                setattr(cls, attr, processed_value)

        return True

    @classmethod
    def _load_from_env(cls) -> None:
        """Load configuration from environment variables."""
        for attr in dir(cls):
            if not cls._is_valid_config_attr(attr):
                continue

            env_value = os.getenv(attr)
            if env_value is None:
                continue

            processed_value = cls._process_config_value(attr, env_value)
            if processed_value is not None:
                setattr(cls, attr, processed_value)

    @classmethod
    def _validate_required_config(cls) -> None:
        """Validate that all required configuration is present."""
        required_keys = ["BOT_TOKEN", "OWNER_ID", "TELEGRAM_API", "TELEGRAM_HASH"]

        for key in required_keys:
            value = getattr(cls, key)
            if isinstance(value, str):
                value = value.strip()
            if not value:
                raise ValueError(f"{key} variable is missing!")

    @classmethod
    def load(cls) -> None:
        """Load configuration from config module or environment variables."""
        if not cls._load_from_module():
            print("Config module not found, loading from environment variables...")
            cls._load_from_env()

        cls._validate_required_config()

    @classmethod
    def load_dict(cls, config_dict: Dict[str, Any]) -> None:
        """Load configuration from dictionary."""
        for key, value in config_dict.items():
            if not hasattr(cls, key):
                continue

            processed_value = cls._process_config_value(key, value)

            # Special handling for USENET_SERVERS in dict loading
            if key == "USENET_SERVERS" and processed_value is None:
                processed_value = []

            if processed_value is not None:
                setattr(cls, key, processed_value)

        cls._validate_required_config()
