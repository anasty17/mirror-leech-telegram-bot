from ast import literal_eval
from aiofiles.os import path as aiopath, remove, makedirs
from aiofiles import open as aiopen
from aioshutil import rmtree
from asyncio import create_subprocess_exec, sleep
from importlib import import_module
from os import chmod

from .. import (
    aria2_options,
    qbit_options,
    nzb_options,
    drives_ids,
    drives_names,
    index_urls,
    user_data,
    excluded_extensions,
    included_extensions,
    LOGGER,
    rss_dict,
    sabnzbd_client,
    auth_chats,
    sudo_users,
)
from ..helper.ext_utils.db_handler import database
from .config_manager import Config
from .telegram_manager import TgClient
from .torrent_manager import TorrentManager


def _normalize_clone_dump_chats(value):
    if not value:
        return {}
    if isinstance(value, (int, list, tuple, dict)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            parsed = literal_eval(stripped)
            if not isinstance(parsed, (list, tuple)):
                raise ValueError("CLONE_DUMP_CHATS list syntax must produce a list/tuple")
            return list(parsed)
        return stripped
    raise ValueError("Unsupported CLONE_DUMP_CHATS value")


async def update_qb_options():
    LOGGER.info("Get qBittorrent options from server")
    if not qbit_options:
        opt = await TorrentManager.qbittorrent.app.preferences()
        qbit_options.update(opt)
        qbit_options.pop("listen_port", None)
        for k in list(qbit_options.keys()):
            if k.startswith("rss"):
                del qbit_options[k]
        # Preserve qBittorrent's own credential state. Do not install a
        # predictable repository-wide WebUI password.
        qbit_options.pop("web_ui_password", None)
    else:
        safe_options = dict(qbit_options)
        safe_options.pop("web_ui_password", None)
        await TorrentManager.qbittorrent.app.set_preferences(safe_options)


async def update_aria2_options():
    LOGGER.info("Get aria2 options from server")
    if not aria2_options:
        op = await TorrentManager.aria2.getGlobalOption()
        aria2_options.update(op)
    else:
        await TorrentManager.aria2.changeGlobalOption(aria2_options)


async def update_nzb_options(max_attempts=20, retry_delay=0.5):
    LOGGER.info("Get SABnzbd options from server")
    last_error = None
    for attempt in range(1, max_attempts + 1):
        try:
            no = (await sabnzbd_client.get_config())["config"]["misc"]
            nzb_options.update(no)
            return
        except Exception as exc:
            last_error = exc
            if attempt < max_attempts:
                await sleep(retry_delay)
    raise RuntimeError(
        f"Unable to load SABnzbd options after {max_attempts} attempts: {last_error}"
    ) from last_error


async def load_settings():
    if not Config.DATABASE_URL:
        return

    for p in ["thumbnails", "tokens", "rclone"]:
        if await aiopath.exists(p):
            await rmtree(p, ignore_errors=True)

    await database.connect()
    if database.db is None:
        return

    bot_id = Config.BOT_TOKEN.split(":", 1)[0]

    try:
        settings = import_module("config")
        config_file = {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
    except ModuleNotFoundError:
        config_file = {}

    old_config = await database.db.settings.deployConfig.find_one(
        {"_id": bot_id}, {"_id": 0}
    )
    if old_config is None and config_file:
        await database.db.settings.deployConfig.replace_one(
            {"_id": bot_id}, config_file, upsert=True
        )
    elif old_config and config_file and old_config != config_file:
        LOGGER.info("Replacing existing deploy config in Database")
        await database.db.settings.deployConfig.replace_one(
            {"_id": bot_id}, config_file, upsert=True
        )
    else:
        config_dict = await database.db.settings.config.find_one(
            {"_id": bot_id}, {"_id": 0}
        )
        if config_dict:
            Config.load_dict(config_dict)

    if pf_dict := await database.db.settings.files.find_one(
        {"_id": bot_id}, {"_id": 0}
    ):
        for key, value in pf_dict.items():
            if value:
                file_ = key.replace("__", ".")
                async with aiopen(file_, "wb+") as f:
                    await f.write(value)

    if a2c_options := await database.db.settings.aria2c.find_one(
        {"_id": bot_id}, {"_id": 0}
    ):
        aria2_options.update(a2c_options)

    if qbit_opt := await database.db.settings.qbittorrent.find_one(
        {"_id": bot_id}, {"_id": 0}
    ):
        qbit_opt.pop("web_ui_password", None)
        qbit_options.update(qbit_opt)

    if nzb_opt := await database.db.settings.nzb.find_one({"_id": bot_id}, {"_id": 0}):
        if await aiopath.exists("sabnzbd/SABnzbd.ini.bak"):
            await remove("sabnzbd/SABnzbd.ini.bak")
        ((key, value),) = nzb_opt.items()
        file_ = key.replace("__", ".")
        async with aiopen(f"sabnzbd/{file_}", "wb+") as f:
            await f.write(value)

    if await database.db.users.find_one():
        for p in ["thumbnails", "tokens", "rclone"]:
            if not await aiopath.exists(p):
                await makedirs(p)
            chmod(p, 0o700)
        rows = database.db.users.find({})
        async for row in rows:
            uid = row["_id"]
            del row["_id"]
            if "CLONE_DUMP_CHATS" in row:
                try:
                    row["CLONE_DUMP_CHATS"] = _normalize_clone_dump_chats(
                        row["CLONE_DUMP_CHATS"]
                    )
                except (ValueError, SyntaxError) as exc:
                    LOGGER.warning(
                        f"Ignoring invalid CLONE_DUMP_CHATS for user {uid}: {exc}"
                    )
                    row["CLONE_DUMP_CHATS"] = {}
            thumb_path = f"thumbnails/{uid}.jpg"
            rclone_config_path = f"rclone/{uid}.conf"
            token_path = f"tokens/{uid}.pickle"
            if row.get("THUMBNAIL"):
                async with aiopen(thumb_path, "wb+") as f:
                    await f.write(row["THUMBNAIL"])
                row["THUMBNAIL"] = thumb_path
            if row.get("RCLONE_CONFIG"):
                async with aiopen(rclone_config_path, "wb+") as f:
                    await f.write(row["RCLONE_CONFIG"])
                chmod(rclone_config_path, 0o600)
                row["RCLONE_CONFIG"] = rclone_config_path
            if row.get("TOKEN_PICKLE"):
                async with aiopen(token_path, "wb+") as f:
                    await f.write(row["TOKEN_PICKLE"])
                chmod(token_path, 0o600)
                row["TOKEN_PICKLE"] = token_path
            user_data[uid] = row
        LOGGER.info("Users data has been imported from Database")

    if await database.db.rss[bot_id].find_one():
        rows = database.db.rss[bot_id].find({})
        async for row in rows:
            user_id = row["_id"]
            del row["_id"]
            rss_dict[user_id] = row
        LOGGER.info("Rss data has been imported from Database.")


async def save_settings():
    if database.db is None:
        return
    config_dict = Config.get_all()
    await database.db.settings.config.replace_one(
        {"_id": TgClient.ID}, config_dict, upsert=True
    )
    if await database.db.settings.aria2c.find_one({"_id": TgClient.ID}) is None:
        await database.db.settings.aria2c.update_one(
            {"_id": TgClient.ID}, {"$set": aria2_options}, upsert=True
        )
    if await database.db.settings.qbittorrent.find_one({"_id": TgClient.ID}) is None:
        await database.save_qbit_settings()
    if await database.db.settings.nzb.find_one({"_id": TgClient.ID}) is None:
        async with aiopen("sabnzbd/SABnzbd.ini", "rb+") as pf:
            nzb_conf = await pf.read()
        await database.db.settings.nzb.update_one(
            {"_id": TgClient.ID}, {"$set": {"SABnzbd__ini": nzb_conf}}, upsert=True
        )


async def update_variables():
    if (
        Config.LEECH_SPLIT_SIZE > TgClient.MAX_SPLIT_SIZE
        or Config.LEECH_SPLIT_SIZE == 2097152000
        or not Config.LEECH_SPLIT_SIZE
    ):
        Config.LEECH_SPLIT_SIZE = TgClient.MAX_SPLIT_SIZE

    Config.HYBRID_LEECH = bool(Config.HYBRID_LEECH and TgClient.IS_PREMIUM_USER)

    try:
        Config.CLONE_DUMP_CHATS = _normalize_clone_dump_chats(Config.CLONE_DUMP_CHATS)
    except (ValueError, SyntaxError) as exc:
        LOGGER.warning(f"Ignoring invalid CLONE_DUMP_CHATS config: {exc}")
        Config.CLONE_DUMP_CHATS = {}

    auth_chats.clear()
    sudo_users.clear()
    excluded_extensions.clear()
    included_extensions.clear()
    drives_names.clear()
    drives_ids.clear()
    index_urls.clear()

    if Config.AUTHORIZED_CHATS:
        for id_ in Config.AUTHORIZED_CHATS.split():
            chat_id, *thread_ids = id_.split("|")
            chat_id = int(chat_id.strip())
            auth_chats[chat_id] = [int(x.strip()) for x in thread_ids] if thread_ids else []

    if Config.SUDO_USERS:
        for id_ in Config.SUDO_USERS.split():
            sudo_users.append(int(id_.strip()))

    if Config.EXCLUDED_EXTENSIONS:
        for x in Config.EXCLUDED_EXTENSIONS.split():
            excluded_extensions.append(x.lstrip(".").strip().lower())

    if Config.INCLUDED_EXTENSIONS:
        for x in Config.INCLUDED_EXTENSIONS.split():
            included_extensions.append(x.lstrip(".").strip().lower())

    if Config.GDRIVE_ID:
        drives_names.append("Main")
        drives_ids.append(Config.GDRIVE_ID)
        index_urls.append(Config.INDEX_URL)

    if await aiopath.exists("list_drives.txt"):
        async with aiopen("list_drives.txt", "r+") as f:
            lines = await f.readlines()
            for line_no, line in enumerate(lines, start=1):
                stripped = line.strip()
                if not stripped or stripped.startswith("#"):
                    continue
                temp = stripped.split()
                if len(temp) < 2:
                    LOGGER.warning(
                        f"Skipping malformed list_drives.txt line {line_no}: {stripped}"
                    )
                    continue
                drives_ids.append(temp[1])
                drives_names.append(temp[0].replace("_", " "))
                index_urls.append(temp[2] if len(temp) > 2 else "")


async def load_configurations():
    if not await aiopath.exists(".netrc"):
        async with aiopen(".netrc", "w"):
            pass
    chmod(".netrc", 0o600)
    await (await create_subprocess_exec("cp", ".netrc", "/root/.netrc")).wait()
    chmod("/root/.netrc", 0o600)
    await (await create_subprocess_exec("chmod", "+x", "aria-nox-nzb.sh")).wait()
    aria_proc = await create_subprocess_exec("bash", "aria-nox-nzb.sh")
    aria_code = await aria_proc.wait()
    if aria_code != 0:
        raise RuntimeError(f"aria-nox-nzb.sh failed with exit code {aria_code}")

    if Config.BASE_URL:
        await create_subprocess_exec(
            "gunicorn",
            "-k",
            "uvicorn.workers.UvicornWorker",
            "-w",
            "1",
            "web.wserver:app",
            "--bind",
            f"0.0.0.0:{Config.BASE_URL_PORT}",
        )

    if await aiopath.exists("cfg.zip"):
        if await aiopath.exists("/JDownloader/cfg"):
            await rmtree("/JDownloader/cfg", ignore_errors=True)
        code = await (
            await create_subprocess_exec("7z", "x", "cfg.zip", "-o/JDownloader")
        ).wait()
        if code != 0:
            raise RuntimeError(f"Failed to extract cfg.zip (exit {code})")

    if await aiopath.exists("accounts.zip"):
        if await aiopath.exists("accounts"):
            await rmtree("accounts")
        code = await (
            await create_subprocess_exec(
                "7z", "x", "-o.", "-aoa", "accounts.zip", "accounts/*.json"
            )
        ).wait()
        if code != 0:
            raise RuntimeError(f"Failed to extract accounts.zip (exit {code})")
        await (await create_subprocess_exec("chmod", "-R", "700", "accounts")).wait()
        await remove("accounts.zip")

    if not await aiopath.exists("accounts"):
        Config.USE_SERVICE_ACCOUNTS = False
