#!/usr/bin/env python3
from aiofiles.os import path as aiopath, makedirs
from aiofiles import open as aiopen
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError
from dotenv import dotenv_values

from bot import DATABASE_URL, user_data, rss_dict, LOGGER, bot_id, config_dict, aria2_options, qbit_options, bot_loop


class DbManger:
    def __init__(self):
        self.__err = False
        self.__db = None
        self.__conn = None
        self.__connect()

    def __connect(self):
        try:
            self.__conn = AsyncIOMotorClient(DATABASE_URL)
            self.__db = self.__conn.mltb
        except PyMongoError as e:
            LOGGER.error(f"Error in DB connection: {e}")
            self.__err = True

    async def db_load(self):
        if self.__err:
            return
        # Save bot settings
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': config_dict}, upsert=True)
        # Save Aria2c options
        if await self.__db.settings.aria2c.find_one({'_id': bot_id}) is None:
            await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': aria2_options}, upsert=True)
        # Save qbittorrent options
        if await self.__db.settings.qbittorrent.find_one({'_id': bot_id}) is None:
            await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': qbit_options}, upsert=True)
        # User Data
        if await self.__db.users.find_one():
            rows = self.__db.users.find({})
            # return a dict ==> {_id, is_sudo, is_auth, as_doc, thumb, yt_opt, media_group, equal_splits, split_size, rclone}
            async for row in rows:
                uid = row['_id']
                del row['_id']
                thumb_path = f'Thumbnails/{uid}.jpg'
                rclone_path = f'rclone/{uid}.conf'
                if row.get('thumb'):
                    if not await aiopath.exists('Thumbnails'):
                        await makedirs('Thumbnails')
                    async with aiopen(thumb_path, 'wb+') as f:
                        await f.write(row['thumb'])
                    row['thumb'] = thumb_path
                if row.get('rclone'):
                    if not await aiopath.exists('rclone'):
                        await makedirs('rclone')
                    async with aiopen(rclone_path, 'wb+') as f:
                        await f.write(row['rclone'])
                    row['rclone'] = rclone_path
                user_data[uid] = row
            LOGGER.info("Users data has been imported from Database")
        # Rss Data
        if await self.__db.rss[bot_id].find_one():
            # return a dict ==> {_id, title: {link, last_feed, last_name, inf, exf, command, paused}
            rows = self.__db.rss[bot_id].find({})
            async for row in rows:
                user_id = row['_id']
                del row['_id']
                rss_dict[user_id] = row
            LOGGER.info("Rss data has been imported from Database.")
        self.__conn.close

    async def update_deploy_config(self):
        if self.__err:
            return
        current_config = dict(dotenv_values('config.env'))
        await self.__db.settings.deployConfig.replace_one({'_id': bot_id}, current_config, upsert=True)
        self.__conn.close

    async def update_config(self, dict_):
        if self.__err:
            return
        await self.__db.settings.config.update_one({'_id': bot_id}, {'$set': dict_}, upsert=True)
        self.__conn.close

    async def update_aria2(self, key, value):
        if self.__err:
            return
        await self.__db.settings.aria2c.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_qbittorrent(self, key, value):
        if self.__err:
            return
        await self.__db.settings.qbittorrent.update_one({'_id': bot_id}, {'$set': {key: value}}, upsert=True)
        self.__conn.close

    async def update_private_file(self, path):
        if self.__err:
            return
        if await aiopath.exists(path):
            async with aiopen(path, 'rb+') as pf:
                pf_bin = await pf.read()
        else:
            pf_bin = ''
        path = path.replace('.', '__')
        await self.__db.settings.files.update_one({'_id': bot_id}, {'$set': {path: pf_bin}}, upsert=True)
        if path == 'config.env':
            await self.update_deploy_config()
        else:
            self.__conn.close

    async def update_user_data(self, user_id):
        if self.__err:
            return
        data = user_data[user_id]
        if data.get('thumb'):
            del data['thumb']
        if data.get('rclone'):
            del data['rclone']
        await self.__db.users.replace_one({'_id': user_id}, data, upsert=True)
        self.__conn.close

    async def update_user_doc(self, user_id, key, path=''):
        if self.__err:
            return
        if path:
            async with aiopen(path, 'rb+') as doc:
                doc_bin = await doc.read()
        else:
            doc_bin = ''
        await self.__db.users.update_one({'_id': user_id}, {'$set': {key: doc_bin}}, upsert=True)
        self.__conn.close

    async def rss_update_all(self):
        if self.__err:
            return
        for user_id in list(rss_dict.keys()):
            await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def rss_update(self, user_id):
        if self.__err:
            return
        await self.__db.rss[bot_id].replace_one({'_id': user_id}, rss_dict[user_id], upsert=True)
        self.__conn.close

    async def rss_delete(self, user_id):
        if self.__err:
            return
        await self.__db.rss[bot_id].delete_one({'_id': user_id})
        self.__conn.close

    async def add_incomplete_task(self, cid, link, tag):
        if self.__err:
            return
        await self.__db.tasks[bot_id].insert_one({'_id': link, 'cid': cid, 'tag': tag})
        self.__conn.close

    async def rm_complete_task(self, link):
        if self.__err:
            return
        await self.__db.tasks[bot_id].delete_one({'_id': link})
        self.__conn.close

    async def get_incomplete_tasks(self):
        notifier_dict = {}
        if self.__err:
            return notifier_dict
        if await self.__db.tasks[bot_id].find_one():
            # return a dict ==> {_id, cid, tag}
            rows = self.__db.tasks[bot_id].find({})
            async for row in rows:
                if row['cid'] in list(notifier_dict.keys()):
                    if row['tag'] in list(notifier_dict[row['cid']]):
                        notifier_dict[row['cid']][row['tag']].append(
                            row['_id'])
                    else:
                        notifier_dict[row['cid']][row['tag']] = [row['_id']]
                else:
                    notifier_dict[row['cid']] = {row['tag']: [row['_id']]}
        await self.__db.tasks[bot_id].drop()
        self.__conn.close
        return notifier_dict  # return a dict ==> {cid: {tag: [_id, _id, ...]}}

    async def trunc_table(self, name):
        if self.__err:
            return
        await self.__db[name][bot_id].drop()
        self.__conn.close


if DATABASE_URL:
    bot_loop.run_until_complete(DbManger().db_load())
