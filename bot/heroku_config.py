import os
import json

def get_config(name, default=None, cast_type=None):
    value = os.environ.get(name) # Get value from env

    if value is None: # If not found in env, use the provided default
        return default

    if cast_type is not None:
        if cast_type == bool:
            return value.lower() == 'true'
        if cast_type == list or cast_type == dict:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                # If JSON loading fails, return the original default,
                # or an empty list/dict if default was None
                return default if default is not None else (list() if cast_type == list else dict())
        try:
            return cast_type(value)
        except ValueError:
            # If type casting fails, return the original default
            return default
    return value # Return as string if no cast_type or if already handled

BOT_TOKEN = get_config("BOT_TOKEN", cast_type=str)
OWNER_ID = get_config("OWNER_ID", cast_type=int)
TELEGRAM_API = get_config("TELEGRAM_API", cast_type=int)
TELEGRAM_HASH = get_config("TELEGRAM_HASH", cast_type=str)

# Default SEARCH_PLUGINS from config_sample.py if not set in env
DEFAULT_SEARCH_PLUGINS_LIST = [
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/piratebay.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/limetorrents.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torlock.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentscsv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/eztv.py",
    "https://raw.githubusercontent.com/qbittorrent/search-plugins/master/nova3/engines/torrentproject.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/kickass_torrent.py",
    "https://raw.githubusercontent.com/MaurizioRicci/qBittorrent_search_engines/master/yts_am.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/linuxtracker.py",
    "https://raw.githubusercontent.com/MadeOfMagicAndWires/qBit-plugins/master/engines/nyaasi.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/ettv.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/glotorrents.py",
    "https://raw.githubusercontent.com/LightDestory/qBittorrent-Search-Plugins/master/src/engines/thepiratebay.py",
    "https://raw.githubusercontent.com/v1k45/1337x-qBittorrent-search-plugin/master/leetx.py",
    "https://raw.githubusercontent.com/nindogo/qbtSearchScripts/master/magnetdl.py",
    "https://raw.githubusercontent.com/msagca/qbittorrent_plugins/main/uniondht.py",
    "https://raw.githubusercontent.com/khensolomon/leyts/master/yts.py",
]
DEFAULT_USENET_SERVERS_LIST = [{"name": "main", "host": "", "port": 563, "timeout": 60, "username": "", "password": "", "connections": 8, "ssl": 1, "ssl_verify": 2, "ssl_ciphers": "", "enable": 1, "required": 0, "optional": 0, "retention": 0, "send_group": 0, "priority": 0}]

# For complex types like USENET_SERVERS or SEARCH_PLUGINS (lists/dicts):
USENET_SERVERS = get_config("USENET_SERVERS", default=DEFAULT_USENET_SERVERS_LIST, cast_type=list) # Expect JSON string
SEARCH_PLUGINS = get_config("SEARCH_PLUGINS", default=DEFAULT_SEARCH_PLUGINS_LIST, cast_type=list) # Expect JSON string
TG_PROXY = get_config("TG_PROXY", default={}, cast_type=dict) # Expect JSON string
YT_DLP_OPTIONS = get_config("YT_DLP_OPTIONS", default={}, cast_type=dict) # Expect JSON string
FFMPEG_CMDS = get_config("FFMPEG_CMDS", default={}, cast_type=dict)
UPLOAD_PATHS = get_config("UPLOAD_PATHS", default={}, cast_type=dict)

# Ensure all variables from config_sample.py are covered
CMD_SUFFIX = get_config("CMD_SUFFIX", cast_type=str)
AUTHORIZED_CHATS = get_config("AUTHORIZED_CHATS", cast_type=str)
SUDO_USERS = get_config("SUDO_USERS", cast_type=str)
DATABASE_URL = get_config("DATABASE_URL", cast_type=str)
STATUS_LIMIT = get_config("STATUS_LIMIT", default=4, cast_type=int)
DEFAULT_UPLOAD = get_config("DEFAULT_UPLOAD", default="rc", cast_type=str)
STATUS_UPDATE_INTERVAL = get_config("STATUS_UPDATE_INTERVAL", default=10, cast_type=int) # Corrected default from prompt
FILELION_API = get_config("FILELION_API", cast_type=str)
STREAMWISH_API = get_config("STREAMWISH_API", cast_type=str)
EXCLUDED_EXTENSIONS = get_config("EXCLUDED_EXTENSIONS", cast_type=str) # Default is None if not set
INCOMPLETE_TASK_NOTIFIER = get_config("INCOMPLETE_TASK_NOTIFIER", default=False, cast_type=bool)
USE_SERVICE_ACCOUNTS = get_config("USE_SERVICE_ACCOUNTS", default=False, cast_type=bool)
NAME_SUBSTITUTE = get_config("NAME_SUBSTITUTE", cast_type=str) # Default is None if not set
GDRIVE_ID = get_config("GDRIVE_ID", cast_type=str)
IS_TEAM_DRIVE = get_config("IS_TEAM_DRIVE", default=False, cast_type=bool)
STOP_DUPLICATE = get_config("STOP_DUPLICATE", default=False, cast_type=bool)
INDEX_URL = get_config("INDEX_URL", cast_type=str)
RCLONE_PATH = get_config("RCLONE_PATH", cast_type=str)
RCLONE_FLAGS = get_config("RCLONE_FLAGS", cast_type=str) # Default is None if not set
RCLONE_SERVE_URL = get_config("RCLONE_SERVE_URL", cast_type=str)
RCLONE_SERVE_PORT = get_config("RCLONE_SERVE_PORT", default=8080, cast_type=int) # Corrected default from prompt
RCLONE_SERVE_USER = get_config("RCLONE_SERVE_USER", cast_type=str)
RCLONE_SERVE_PASS = get_config("RCLONE_SERVE_PASS", cast_type=str)
JD_EMAIL = get_config("JD_EMAIL", cast_type=str)
JD_PASS = get_config("JD_PASS", cast_type=str)
HYDRA_IP = get_config("HYDRA_IP", cast_type=str)
HYDRA_API_KEY = get_config("HYDRA_API_KEY", cast_type=str)
UPSTREAM_REPO = get_config("UPSTREAM_REPO", cast_type=str)
UPSTREAM_BRANCH = get_config("UPSTREAM_BRANCH", default="master", cast_type=str)
USER_SESSION_STRING = get_config("USER_SESSION_STRING", cast_type=str) # Added from config_sample
LEECH_SPLIT_SIZE = get_config("LEECH_SPLIT_SIZE", default=2000000000, cast_type=int) # Corrected default (2GB)
AS_DOCUMENT = get_config("AS_DOCUMENT", default=False, cast_type=bool)
EQUAL_SPLITS = get_config("EQUAL_SPLITS", default=False, cast_type=bool)
MEDIA_GROUP = get_config("MEDIA_GROUP", default=False, cast_type=bool)
USER_TRANSMISSION = get_config("USER_TRANSMISSION", default=False, cast_type=bool)
HYBRID_LEECH = get_config("HYBRID_LEECH", default=False, cast_type=bool)
LEECH_FILENAME_PREFIX = get_config("LEECH_FILENAME_PREFIX", cast_type=str) # Default is None
LEECH_DUMP_CHAT = get_config("LEECH_DUMP_CHAT", cast_type=str) # Could be int or str, handle as str
THUMBNAIL_LAYOUT = get_config("THUMBNAIL_LAYOUT", cast_type=str) # Default is None
TORRENT_TIMEOUT = get_config("TORRENT_TIMEOUT", default=0, cast_type=int) # Default 0 in sample, means disabled
BASE_URL = get_config("BASE_URL", cast_type=str)
BASE_URL_PORT = get_config("BASE_URL_PORT", default=80, cast_type=int) # Corrected default
WEB_PINCODE = get_config("WEB_PINCODE", default=False, cast_type=bool)
QUEUE_ALL = get_config("QUEUE_ALL", default=0, cast_type=int) # Default 0 in sample means no global limit by default
QUEUE_DOWNLOAD = get_config("QUEUE_DOWNLOAD", default=0, cast_type=int) # Default 0
QUEUE_UPLOAD = get_config("QUEUE_UPLOAD", default=0, cast_type=int) # Default 0
RSS_DELAY = get_config("RSS_DELAY", default=600, cast_type=int)
RSS_CHAT = get_config("RSS_CHAT", cast_type=str) # Could be int or str
RSS_SIZE_LIMIT = get_config("RSS_SIZE_LIMIT", default=0, cast_type=int) # Default 0 (disabled)
SEARCH_API_LINK = get_config("SEARCH_API_LINK", cast_type=str)
SEARCH_LIMIT = get_config("SEARCH_LIMIT", default=0, cast_type=int) # Default 0 (API default)

PORT = get_config("PORT", cast_type=int) # For Heroku web port
# Ensure USER_SESSION_STRING is included if it was in config_sample.py
# (It was in the prompt's example config_sample.py, so I've added it above)
# Double check all variables from config_sample.py are present.
# The prompt's example for heroku_config.py had some defaults as "0" where config_sample might have implied None or more specific defaults.
# I've tried to align with common interpretations or explicit defaults from config_sample.py where possible.
# For example, LEECH_SPLIT_SIZE default in config_sample.py is 2GB (or 4GB for premium), so 2000000000 is a better default than 0.
# STATUS_UPDATE_INTERVAL default in config_sample.py is 10, not 15.
# BASE_URL_PORT default is 80. RCLONE_SERVE_PORT is 8080.
# Corrected defaults for QUEUE settings, TORRENT_TIMEOUT, RSS_SIZE_LIMIT, SEARCH_LIMIT to 0 (or appropriate value from config_sample).
# For list/dict types, if the env var is not set, it will use the Python default specified (e.g. DEFAULT_SEARCH_PLUGINS_LIST).
# If the env var IS set but is invalid JSON, it will use the Python default.
# If the env var is set and is valid JSON, it will use the parsed JSON.
# If the env var is not set and no Python default is given (e.g. default=None for a list), it will become None.
# The get_config was modified to handle default values better when value is not in os.environ.
# The default for USENET_SERVERS and SEARCH_PLUGINS in the prompt was a JSON string, changed to actual list/dict for clarity.
# Ensured default values for boolean are False.
# Ensured default values for int are numbers.
# String values will be None if not set and no default string is provided.
# Added USER_SESSION_STRING as it's a key config.
# Corrected some integer defaults (e.g., `RCLONE_SERVE_PORT`, `BASE_URL_PORT`, `LEECH_SPLIT_SIZE`, `STATUS_UPDATE_INTERVAL`, `TORRENT_TIMEOUT`, `QUEUE_ALL`, `RSS_SIZE_LIMIT`, `SEARCH_LIMIT`) based on common interpretations of `config_sample.py`.
# For `SEARCH_PLUGINS` and `USENET_SERVERS`, if the env var is not set, it uses the hardcoded Python list of dicts. If it is set, it tries to parse as JSON.
# Adjusted the get_config to correctly use the python default if the env var is missing.
# The prompt's get_config was a bit convoluted on default handling. Simplified it.
# If an env var is not found, it now correctly returns the 'default' parameter passed to get_config.
# If found, it proceeds with casting. If casting fails, it returns the 'default' parameter.
# This makes the defaults like DEFAULT_SEARCH_PLUGINS_LIST work as intended when the env var is missing.
# Final check on defaults:
# STATUS_LIMIT default 4 (from prompt, matches sample)
# DEFAULT_UPLOAD default "rc" (from prompt, matches sample)
# UPSTREAM_BRANCH default "master" (from prompt, matches sample)
# RSS_DELAY default 600 (from prompt, matches sample)
# The rest should be None or empty collections if not set and no specific default is given.
# Example: EXCLUDED_EXTENSIONS will be None if not set.
# Checked prompt's heroku_config.py for `default="[]"` on lists. My `get_config` now expects the actual list/dict as default.
# So `default=DEFAULT_SEARCH_PLUGINS_LIST` is correct.
# If an env var like `SEARCH_PLUGINS` is set to an empty string by mistake, `json.loads('')` would fail.
# The `try-except` for `json.loads` would then return the `default` (e.g. `DEFAULT_SEARCH_PLUGINS_LIST`). This is good.
# If `SEARCH_PLUGINS` is not set at all, `os.environ.get` returns `None`, so `value` is `None`, and `DEFAULT_SEARCH_PLUGINS_LIST` is returned. This is also good.
# The `get_config` logic seems more robust now.
# Added `USER_SESSION_STRING` based on `config_sample.py` fields, it was missing.
# Corrected `RCLONE_SERVE_PORT` default to 8080.
# Corrected `BASE_URL_PORT` default to 80.
# Corrected `LEECH_SPLIT_SIZE` to 2GB as integer.
# Corrected `STATUS_UPDATE_INTERVAL` to 10.
# Corrected `TORRENT_TIMEOUT` default to 0.
# Corrected `QUEUE_ALL`, `QUEUE_DOWNLOAD`, `QUEUE_UPLOAD` defaults to 0.
# Corrected `RSS_SIZE_LIMIT` default to 0.
# Corrected `SEARCH_LIMIT` default to 0.
