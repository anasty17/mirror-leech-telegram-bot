from sys import exit
from importlib import import_module
from logging import (
    FileHandler,
    StreamHandler,
    INFO,
    basicConfig,
    error as log_error,
    info as log_info,
    getLogger,
    ERROR,
)
from os import path, remove, getenv
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from subprocess import run as srun
from typing import Dict, Any

getLogger("pymongo").setLevel(ERROR)

if path.exists("log.txt"):
    with open("log.txt", "r+") as f:
        f.truncate(0)

if path.exists("rlog.txt"):
    remove("rlog.txt")

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)


def load_config() -> Dict[str, Any]:
    """Load configuration from config module or environment variables."""
    try:
        settings = import_module("config")
        return {
            key: value.strip() if isinstance(value, str) else value
            for key, value in vars(settings).items()
            if not key.startswith("__")
        }
    except ModuleNotFoundError:
        log_info("Config module not found, loading from environment variables...")
        return {
            "BOT_TOKEN": getenv("BOT_TOKEN", ""),
            "DATABASE_URL": getenv("DATABASE_URL", ""),
            "DATABASE_NAME": getenv("DATABASE_NAME", "mltb"),
            "UPSTREAM_REPO": getenv("UPSTREAM_REPO", ""),
            "UPSTREAM_BRANCH": getenv("UPSTREAM_BRANCH", "master"),
        }


def _run_git(*args: str):
    """Run git without a shell so config values cannot become shell commands."""
    return srun(["git", *args], check=False)


config_file = load_config()

BOT_TOKEN = config_file.get("BOT_TOKEN", "")
if not BOT_TOKEN:
    log_error("BOT_TOKEN variable is missing! Exiting now")
    exit(1)

BOT_ID = BOT_TOKEN.split(":", 1)[0]
DATABASE_NAME = config_file.get("DATABASE_NAME", "mltb")

if DATABASE_URL := config_file.get("DATABASE_URL", "").strip():
    try:
        conn = MongoClient(DATABASE_URL, server_api=ServerApi("1"))
        db = conn[DATABASE_NAME]
        old_config = db.settings.deployConfig.find_one({"_id": BOT_ID}, {"_id": 0})
        config_dict = db.settings.config.find_one({"_id": BOT_ID})
        if (
            (old_config is not None and old_config == config_file or old_config is None)
            and config_dict is not None
        ):
            config_file["UPSTREAM_REPO"] = config_dict.get(
                "UPSTREAM_REPO", config_file.get("UPSTREAM_REPO", "")
            )
            config_file["UPSTREAM_BRANCH"] = config_dict.get(
                "UPSTREAM_BRANCH", config_file.get("UPSTREAM_BRANCH", "master")
            )
        conn.close()
    except Exception as e:
        log_error(f"Database ERROR: {e}")

UPSTREAM_REPO = str(config_file.get("UPSTREAM_REPO", "") or "").strip()
UPSTREAM_BRANCH = str(config_file.get("UPSTREAM_BRANCH", "") or "").strip() or "master"

if UPSTREAM_REPO:
    try:
        if path.exists(".git"):
            srun(["rm", "-rf", ".git"], check=False)

        commands = [
            ("init", "-q"),
            ("config", "user.email", "filehub@localhost"),
            ("config", "user.name", "FileHub"),
            ("add", "."),
            ("commit", "-m", "update", "-q"),
            ("remote", "add", "origin", UPSTREAM_REPO),
            ("fetch", "origin", "--depth=1", UPSTREAM_BRANCH, "-q"),
            ("reset", "--hard", "FETCH_HEAD", "-q"),
        ]

        update_ok = True
        for command in commands:
            if _run_git(*command).returncode != 0:
                update_ok = False
                break

        if update_ok:
            log_info("Successfully updated with latest commit from UPSTREAM_REPO")
        else:
            log_error(
                "Something went wrong while updating; check UPSTREAM_REPO and UPSTREAM_BRANCH."
            )
    except Exception as e:
        log_error(f"Updater ERROR: {e}")
