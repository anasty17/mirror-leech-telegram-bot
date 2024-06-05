from aiofiles import open as aiopen
from aiofiles.os import path as aiopath, makedirs
from dotenv import dotenv_values
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.server_api import ServerApi
from pymongo.errors import PyMongoError

from bot import (
    DATABASE_URL,
    user_data,
    rss_dict,
    LOGGER,
    bot_id,
    config_dict,
    aria2_options,
    qbit_options,
)


class DbManager:
    def __init__(self):
        self._err = False
        self._db = None
        self._conn = None
        self._connect()

    def _connect(self):
        try:
            self._conn = AsyncIOMotorClient(DATABASE_URL, server_api=ServerApi("1"))
            self._db = self._conn.mltb
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self._err = True

    async def db_load(self):
        if self._err:
            return
        # Save bot settings
        try:
            await self._db.settings.config.replace_one(
                {"_id": bot_id}, config_dict, upsert=True
            )
        except Exception as e:
            LOGGER.error(f"DataBase Collection Error: {e}")
            self._conn.close
            return
        # Save Aria2c options
        if await self._db.settings.aria2c.find_one({"_id": bot_id}) is None:
            await self._db.settings.aria2c.update_one(
                {"_id": bot_id}, {"$set": aria2_options}, upsert=True
            )
        # Save qbittorrent options
        if await self._db.settings.qbittorrent.find_one({"_id": bot_id}) is None:
            await self.save_qbit_settings()
        # Save nzb config
        if await self._db.settings.nzb.find_one({"_id": bot_id}) is None:
            async with aiopen("sabnzbd/SABnzbd.ini", "rb+") as pf:
                nzb_conf = await pf.read()
            await self._db.settings.nzb.update_one(
                {"_id": bot_id}, {"$set": {"SABnzbd__ini": nzb_conf}}, upsert=True
            )
        # User Data
        if await self._db.users.find_one():
            rows = self._db.users.find({})
            # return a dict ==> {_id, is_sudo, is_auth, as_doc, thumb, yt_opt, media_group, equal_splits, split_size, rclone, rclone_path, token_pickle, gdrive_id, leech_dest, lperfix, lprefix, excluded_extensions, user_transmission, index_url, default_upload}
            async for row in rows:
                uid = row["_id"]
                del row["_id"]
                thumb_path = f"Thumbnails/{uid}.jpg"
                rclone_config_path = f"rclone/{uid}.conf"
                token_path = f"tokens/{uid}.pickle"
                if row.get("thumb"):
                    if not await aiopath.exists("Thumbnails"):
                        await makedirs("Thumbnails")
                    async with aiopen(thumb_path, "wb+") as f:
                        await f.write(row["thumb"])
                    row["thumb"] = thumb_path
                if row.get("rclone_config"):
                    if not await aiopath.exists("rclone"):
                        await makedirs("rclone")
                    async with aiopen(rclone_config_path, "wb+") as f:
                        await f.write(row["rclone_config"])
                    row["rclone_config"] = rclone_config_path
                if row.get("token_pickle"):
                    if not await aiopath.exists("tokens"):
                        await makedirs("tokens")
                    async with aiopen(token_path, "wb+") as f:
                        await f.write(row["token_pickle"])
                    row["token_pickle"] = token_path
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")
        # Rss Data
        if await self._db.rss[bot_id].find_one():
            # return a dict ==> {_id, title: {link, last_feed, last_name, inf, exf, command, paused}
            rows = self._db.rss[bot_id].find({})
            async for row in rows:
                user_id = row["_id"]
                del row["_id"]
                rss_dict[user_id] = row
            LOGGER.info("Rss data has been imported from Database.")
        self._conn.close

    async def update_deploy_config(self):
        if self._err:
            return
        current_config = dict(dotenv_values("config.env"))
        await self._db.settings.deployConfig.replace_one(
            {"_id": bot_id}, current_config, upsert=True
        )
        self._conn.close

    async def update_config(self, dict_):
        if self._err:
            return
        await self._db.settings.config.update_one(
            {"_id": bot_id}, {"$set": dict_}, upsert=True
        )
        self._conn.close

    async def update_aria2(self, key, value):
        if self._err:
            return
        await self._db.settings.aria2c.update_one(
            {"_id": bot_id}, {"$set": {key: value}}, upsert=True
        )
        self._conn.close

    async def update_qbittorrent(self, key, value):
        if self._err:
            return
        await self._db.settings.qbittorrent.update_one(
            {"_id": bot_id}, {"$set": {key: value}}, upsert=True
        )
        self._conn.close

    async def save_qbit_settings(self):
        if self._err:
            return
        await self._db.settings.qbittorrent.replace_one(
            {"_id": bot_id}, qbit_options, upsert=True
        )
        self._conn.close

    async def update_private_file(self, path):
        if self._err:
            return
        if await aiopath.exists(path):
            async with aiopen(path, "rb+") as pf:
                pf_bin = await pf.read()
        else:
            pf_bin = ""
        path = path.replace(".", "__")
        await self._db.settings.files.update_one(
            {"_id": bot_id}, {"$set": {path: pf_bin}}, upsert=True
        )
        if path == "config.env":
            await self.update_deploy_config()
        else:
            self._conn.close

    async def update_nzb_config(self):
        async with aiopen("sabnzbd/SABnzbd.ini", "rb+") as pf:
            nzb_conf = await pf.read()
        await self._db.settings.nzb.replace_one(
            {"_id": bot_id}, {"SABnzbd__ini": nzb_conf}, upsert=True
        )

    async def update_user_data(self, user_id):
        if self._err:
            return
        data = user_data.get(user_id, {})
        if data.get("thumb"):
            del data["thumb"]
        if data.get("rclone_config"):
            del data["rclone_config"]
        if data.get("token_pickle"):
            del data["token_pickle"]
        await self._db.users.replace_one({"_id": user_id}, data, upsert=True)
        self._conn.close

    async def update_user_doc(self, user_id, key, path=""):
        if self._err:
            return
        if path:
            async with aiopen(path, "rb+") as doc:
                doc_bin = await doc.read()
        else:
            doc_bin = ""
        await self._db.users.update_one(
            {"_id": user_id}, {"$set": {key: doc_bin}}, upsert=True
        )
        self._conn.close

    async def rss_update_all(self):
        if self._err:
            return
        for user_id in list(rss_dict.keys()):
            await self._db.rss[bot_id].replace_one(
                {"_id": user_id}, rss_dict[user_id], upsert=True
            )
        self._conn.close

    async def rss_update(self, user_id):
        if self._err:
            return
        await self._db.rss[bot_id].replace_one(
            {"_id": user_id}, rss_dict[user_id], upsert=True
        )
        self._conn.close

    async def rss_delete(self, user_id):
        if self._err:
            return
        await self._db.rss[bot_id].delete_one({"_id": user_id})
        self._conn.close

    async def add_incomplete_task(self, cid, link, tag):
        if self._err:
            return
        await self._db.tasks[bot_id].insert_one({"_id": link, "cid": cid, "tag": tag})
        self._conn.close

    async def rm_complete_task(self, link):
        if self._err:
            return
        await self._db.tasks[bot_id].delete_one({"_id": link})
        self._conn.close

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self._err:
            return notifier_dict
        if await self._db.tasks[bot_id].find_one():
            # return a dict ==> {_id, cid, tag}
            rows = self._db.tasks[bot_id].find({})
            async for row in rows:
                if row["cid"] in list(notifier_dict.keys()):
                    if row["tag"] in list(notifier_dict[row["cid"]]):
                        notifier_dict[row["cid"]][row["tag"]].append(row["_id"])
                    else:
                        notifier_dict[row["cid"]][row["tag"]] = [row["_id"]]
                else:
                    notifier_dict[row["cid"]] = {row["tag"]: [row["_id"]]}
        await self._db.tasks[bot_id].drop()
        self._conn.close
        return notifier_dict  # return a dict ==> {cid: {tag: [_id, _id, ...]}}

    async def trunc_table(self, name):
        if self._err:
            return
        await self._db[name][bot_id].drop()
        self._conn.close
