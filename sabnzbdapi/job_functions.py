from sabnzbdapi.bound_methods import SubFunctions


class JobFunctions(SubFunctions):

    async def add_uri(
        self,
        url: str = "",
        file: str = "",
        nzbname: str = "",
        password: str = "",
        cat: str = "*",
        script: list = None,
        priority: int = 0,
        pp: int = 1,
    ):

        'return {"status": True, "nzo_ids": ["SABnzbd_nzo_kyt1f0"]}'

        if file:
            name = file
            mode = "addlocalfile"
        else:
            name = url
            mode = "addurl"

        return await self.call(
            {
                "mode": mode,
                "name": name,
                "nzbname": nzbname,
                "password": password,
                "cat": cat,
                "script": script,
                "priority": priority,
                "pp": pp,
            }
        )

    async def get_downloads(
        self,
        start: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        category: str | list[str] | None = None,
        priority: int | list[str] | None = None,
        status: str | list[str] | None = None,
        nzo_ids: str | list[str] | None = None,
    ):
        """return {
            "queue": {
                "status": "Downloading",
                "speedlimit": "9",
                "speedlimit_abs": "4718592.0",
                "paused": false,
                "noofslots_total": 2,
                "noofslots": 2,
                "limit": 10,
                "start": 0,
                "timeleft": "0:16:44",
                "speed": "1.3 M",
                "kbpersec": "1296.02",
                "size": "1.2 GB",
                "sizeleft": "1.2 GB",
                "mb": "1277.65",
                "mbleft": "1271.58",
                "slots": [
                    {
                        "status": "Downloading",
                        "index": 0,
                        "password": "",
                        "avg_age": "2895d",
                        "script": "None",
                        "direct_unpack": "10/30",
                        "mb": "1277.65",
                        "mbleft": "1271.59",
                        "mbmissing": "0.0",
                        "size": "1.2 GB",
                        "sizeleft": "1.2 GB",
                        "filename": "TV.Show.S04E11.720p.HDTV.x264",
                        "labels": [],
                        "priority": "Normal",
                        "cat": "tv",
                        "timeleft": "0:16:44",
                        "percentage": "0",
                        "nzo_id": "SABnzbd_nzo_p86tgx",
                        "unpackopts": "3"
                    },
                    {
                        "status": "Paused",
                        "index": 1,
                        "password": "",
                        "avg_age": "2895d",
                        "script": "None",
                        "direct_unpack": null,
                        "mb": "1277.76",
                        "mbleft": "1277.76",
                        "mbmissing": "0.0",
                        "size": "1.2 GB",
                        "sizeleft": "1.2 GB",
                        "filename": "TV.Show.S04E12.720p.HDTV.x264",
                        "labels": [
                            "TOO LARGE",
                            "DUPLICATE"
                        ],
                        "priority": "Normal",
                        "cat": "tv",
                        "timeleft": "0:00:00",
                        "percentage": "0",
                        "nzo_id": "SABnzbd_nzo_ksfai6",
                        "unpackopts": "3"
                    }
                ],
                "diskspace1": "161.16",
                "diskspace2": "161.16",
                "diskspacetotal1": "465.21",
                "diskspacetotal2": "465.21",
                "diskspace1_norm": "161.2 G",
                "diskspace2_norm": "161.2 G",
                "have_warnings": "0",
                "pause_int": "0",
                "left_quota": "0 ",
                "version": "3.x.x",
                "finish": 2,
                "cache_art": "16",
                "cache_size": "6 MB",
                "finishaction": null,
                "paused_all": false,
                "quota": "0 ",
                "have_quota": false,
            }
        }"""

        if nzo_ids:
            nzo_ids = nzo_ids if isinstance(nzo_ids, str) else ",".join(nzo_ids)
        if status:
            status = status if isinstance(status, str) else ",".join(status)
        if category:
            category = category if isinstance(category, str) else ",".join(category)
        if priority:
            priority = priority if isinstance(priority, str) else ",".join(priority)

        return await self.call(
            {
                "mode": "queue",
                "start": start,
                "limit": limit,
                "search": search,
                "category": category,
                "priority": priority,
                "status": status,
                "nzo_ids": nzo_ids,
            },
        )

    async def pause_job(self, nzo_id: str):
        """return {"status": True, "nzo_ids": ["all effected ids"]}"""
        return await self.call({"mode": "queue", "name": "pause", "value": nzo_id})

    async def resume_job(self, nzo_id: str):
        """return {"status": True, "nzo_ids": ["all effected ids"]}"""
        return await self.call({"mode": "queue", "name": "resume", "value": nzo_id})

    async def delete_job(self, nzo_id: str | list[str], delete_files: bool = False):
        """return {"status": True, "nzo_ids": ["all effected ids"]}"""
        return await self.call(
            {
                "mode": "queue",
                "name": "delete",
                "value": nzo_id if isinstance(nzo_id, str) else ",".join(nzo_id),
                "del_files": 1 if delete_files else 0,
            }
        )

    async def pause_all(self):
        """return {"status": True}"""
        return await self.call({"mode": "pause"})

    async def resume_all(self):
        """return {"status": True}"""
        return await self.call({"mode": "resume"})

    async def purge_all(self, delete_files: bool = False):
        """return {"status": True, "nzo_ids": ["all effected ids"]}"""
        return await self.call(
            {"mode": "queue", "name": "purge", "del_files": 1 if delete_files else 0}
        )

    async def get_files(self, nzo_id: str):
        """
        return {
            "files": [
                {
                    "status": "finished",
                    "mbleft": "0.00",
                    "mb": "0.05",
                    "age": "25d",
                    "bytes": "52161.00",
                    "filename": "93a4ec7c37752640deab48dabb46b164.par2",
                    "nzf_id": "SABnzbd_nzf_1lk0ij",
                },
                ...,
            ]
        }
        """
        return await self.call({"mode": "get_files", "value": nzo_id})

    async def remove_file(self, nzo_id: str, file_ids: str | list[str]):
        return await self.call(
            {
                "mode": "queue",
                "name": "delete_nzf",
                "value": nzo_id,
                "value2": file_ids if isinstance(file_ids, str) else ",".join(file_ids),
            }
        )  # return nzf_ids of removed file idk how yet

    async def get_history(
        self,
        start: int | None = None,
        limit: int | None = None,
        search: str | None = None,
        category: str | list[str] | None = None,
        archive: int | None = None,
        status: str | list[str] | None = None,
        nzo_ids: str | list[str] | None = None,
        failed_only: bool = False,
        last_history_update: int | None = None,
    ):
        """{
            "history": {
                "noofslots": 220,
                "ppslots": 1,
                "day_size": "1.9 G",
                "week_size": "30.4 G",
                "month_size": "167.3 G",
                "total_size": "678.1 G",
                "last_history_update": 1469210913,
                "slots": [
                    {
                        "action_line": "",
                        "duplicate_key": "TV.Show/4/2",
                        "meta": null,
                        "fail_message": "",
                        "loaded": false,
                        "size": "2.3 GB",
                        "category": "tv",
                        "pp": "D",
                        "retry": 0,
                        "script": "None",
                        "nzb_name": "TV.Show.S04E02.720p.BluRay.x264-xHD.nzb",
                        "download_time": 64,
                        "storage": "C:\\Users\\xxx\\Videos\\Complete\\TV.Show.S04E02.720p.BluRay.x264-xHD",
                        "has_rating": false,
                        "status": "Completed",
                        "script_line": "",
                        "completed": 1469172988,
                        "nzo_id": "SABnzbd_nzo_sdkoun",
                        "downloaded": 2436906376,
                        "report": "",
                        "password": "",
                        "path": "\\\\?\\C:\\SABnzbd\\TV.Show.S04E02.720p.BluRay.x264-xHD",
                        "postproc_time": 40,
                        "name": "TV.Show.S04E02.720p.BluRay.x264-xHD",
                        "url": "TV.Show.S04E02.720p.BluRay.x264-xHD.nzb",
                        "md5sum": "d2c16aeecbc1b1921d04422850e93013",
                        "archive": false,
                        "bytes": 2436906376,
                        "url_info": "",
                        "stage_log": [
                            {
                                "name": "Source",
                                "actions": [
                                    "TV.Show.S04E02.720p.BluRay.x264-xHD.nzb"
                                ]
                            },
                            {
                                "name": "Download",
                                "actions": [
                                    "Downloaded in 1 min 4 seconds at an average of 36.2 MB/s<br/>Age: 550d<br/>10 articles were malformed"
                                ]
                            },
                            {
                                "name": "Servers",
                                "actions": [
                                    "Frugal=2.3 GB"
                                ]
                            },
                            {
                                "name": "Repair",
                                "actions": [
                                    "[pA72r5Ac6lW3bmpd20T7Hj1Zg2bymUsINBB50skrI] Repaired in 19 seconds"
                                ]
                            },
                            {
                                "name": "Unpack",
                                "actions": [
                                    "[pA72r5Ac6lW3bmpd20T7Hj1Zg2bymUsINBB50skrI] Unpacked 1 files/folders in 6 seconds"
                                ]
                            }
                        ]
                    },
                    {
                        "action_line": "",
                        "duplicate_key": "TV.Show/4/13",
                        "meta": null,
                        "fail_message": "",
                        "loaded": false,
                        "size": "2.3 GB",
                        "category": "tv",
                        "pp": "D",
                        "retry": 0,
                        "script": "None",
                        "nzb_name": "TV.Show.S04E13.720p.BluRay.x264-xHD.nzb",
                        "download_time": 60,
                        "storage": "C:\\Users\\xxx\\Videos\\Complete\\TV.Show.S04E13.720p.BluRay.x264-xHD",
                        "has_rating": false,
                        "status": "Completed",
                        "script_line": "",
                        "completed": 1469172947,
                        "nzo_id": "SABnzbd_nzo_gqhp63",
                        "downloaded": 2491255137,
                        "report": "",
                        "password": "",
                        "path": "\\\\?\\C:\\SABnzbd\\TV.Show.S04E13.720p.BluRay.x264-xHD",
                        "postproc_time": 82,
                        "name": "TV.Show.S04E13.720p.BluRay.x264-xHD",
                        "url": "TV.Show.S04E13.720p.BluRay.x264-xHD.nzb",
                        "md5sum": "85baf55ec0de0dc732c2af6537c5c01b",
                        "archive": true,
                        "bytes": 2491255137,
                        "url_info": "",
                        "stage_log": [
                            {
                                "name": "Source",
                                "actions": [
                                    "TV.Show.S04E13.720p.BluRay.x264-xHD.nzb"
                                ]
                            },
                            {
                                "name": "Download",
                                "actions": [
                                    "Downloaded in 1 min at an average of 39.4 MB/s<br/>Age: 558d<br/>15 articles were malformed"
                                ]
                            },
                            {
                                "name": "Servers",
                                "actions": [
                                    "Frugal=2.3 GB"
                                ]
                            },
                            {
                                "name": "Repair",
                                "actions": [
                                    "[m0vklMEMKIT5L5XH9z5YTmuquoitCQ3F5LISTLFjT] Repaired in 47 seconds"
                                ]
                            },
                            {
                                "name": "Unpack",
                                "actions": [
                                    "[m0vklMEMKIT5L5XH9z5YTmuquoitCQ3F5LISTLFjT] Unpacked 1 files/folders in 6 seconds"
                                ]
                            }
                        ]
                    }
                ]
            }
        }"""

        if nzo_ids:
            nzo_ids = nzo_ids if isinstance(nzo_ids, str) else ",".join(nzo_ids)
        if status:
            status = status if isinstance(status, str) else ",".join(status)
        if category:
            category = category if isinstance(category, str) else ",".join(category)

        return await self.call(
            {
                "mode": "history",
                "start": start,
                "limit": limit,
                "archive": archive,
                "search": search,
                "category": category,
                "status": status,
                "nzo_ids": nzo_ids,
                "failed_only": failed_only,
                "last_history_update": last_history_update,
            },
        )

    async def retry_item(self, nzo_id: str, password: str = ""):
        """return {"status": True}"""
        return await self.call({"mode": "retry", "value": nzo_id, "password": password})

    async def retry_all(self):
        """return {"status": True}"""
        return await self.call({"mode": "retry_all"})

    async def delete_history(
        self, nzo_ids: str | list[str], archive: int = 0, delete_files: bool = False
    ):
        """return {"status": True}"""
        return await self.call(
            {
                "mode": "history",
                "name": "delete",
                "value": nzo_ids if isinstance(nzo_ids, str) else ",".join(nzo_ids),
                "archive": archive,
                "del_files": 1 if delete_files else 0,
            }
        )

    async def change_job_pp(self, nzo_id: str, pp: int):
        """return {"status": True}"""
        return await self.call({"mode": "change_opts", "value": nzo_id, "value2": pp})

    async def set_speedlimit(self, limit: str | int):
        """return {"status": True}"""
        return await self.call({"mode": "config", "name": "speedlimit", "value": limit})

    async def delete_config(self, section: str, keyword: str):
        """return {"status": True}"""
        return await self.call(
            {"mode": "del_config", "section": section, "keyword": keyword}
        )

    async def set_config_default(self, keyword: str | list[str]):
        """return {"status": True}"""
        return await self.call({"mode": "set_config_default", "keyword": keyword})

    async def get_config(self, section: str = None, keyword: str = None):
        """return config as dic"""
        return await self.call(
            {"mode": "get_config", "section": section, "keyword": keyword}
        )

    async def set_config(self, section: str, keyword: str, value: str):
        """Returns the new setting when saved successfully"""
        return await self.call(
            {
                "mode": "set_config",
                "section": section,
                "keyword": keyword,
                "value": value,
            }
        )

    async def set_special_config(self, section: str, items: dict):
        """Returns the new setting when saved successfully"""
        return await self.call(
            {
                "mode": "set_config",
                "section": section,
                **items,
            }
        )

    async def server_stats(self):
        """return {
            "day": 2352634799,
            "week": 32934490677,
            "month": 179983557488,
            "total": 728426161290,
            "servers": {
                "eunews.server.com": {
                    "week": 19783288936,
                    "total": 163741252273,
                    "day": 2352634799,
                    "month": 90478917031,
                    "daily": {
                        "2017-01-28": 1234,
                        "2017-01-29": 4567
                    },
                    "articles_tried": 929299,
                    "articles_success": 8299
                },
                "News.server.net": {
                    "week": 13151201741,
                    "total": 165783396295,
                    "day": 0,
                    "month": 89499300889,
                    "daily": {
                        "2017-01-28": 1234,
                        "2017-01-29": 4567
                    },
                    "articles_tried": 520400,
                    "articles_success": 78881
                }
            }
        }"""
        return await self.call({"mode": "server_stats"})

    async def version(self):
        """return {'version': '4.2.2'}"""
        return await self.call({"mode": "version"})

    async def restart(self):
        """return {"status": True}"""
        return await self.call({"mode": "restart"})

    async def restart_repair(self):
        """return {"status": True}"""
        return await self.call({"mode": "restart_repair"})

    async def shutdown(self):
        """return {"status": True}"""
        return await self.call({"mode": "shutdown"})
