from json import dumps, loads, JSONDecodeError
from httpx import AsyncClient, RequestError
from httpx import AsyncHTTPTransport
from functools import wraps

from .exception import (
    MYJDApiException,
    MYJDConnectionException,
    MYJDDecodeException,
)


class System:
    def __init__(self, device):
        self.device = device
        self.url = "/system"

    async def exit_jd(self):
        return await self.device.action(f"{self.url}/exitJD")

    async def restart_jd(self):
        return await self.device.action(f"{self.url}/restartJD")

    async def hibernate_os(self):
        return await self.device.action(f"{self.url}/hibernateOS")

    async def shutdown_os(self, force):
        params = force
        return await self.device.action(f"{self.url}/shutdownOS", params)

    async def standby_os(self):
        return await self.device.action(f"{self.url}/standbyOS")

    async def get_storage_info(self):
        return await self.device.action(f"{self.url}/getStorageInfos?path")


class Jd:
    def __init__(self, device):
        self.device = device
        self.url = "/jd"

    async def get_core_revision(self):
        return await self.device.action(f"{self.url}/getCoreRevision")

    async def version(self):
        return await self.device.action(f"{self.url}/version")


class Config:

    def __init__(self, device):
        self.device = device
        self.url = "/config"

    async def list(self, params=None):
        """
        :return:  List<AdvancedConfigAPIEntry>
        """
        if params is None:
            return await self.device.action(f"{self.url}/list", params)
        else:
            return await self.device.action(f"{self.url}/list")

    async def listEnum(self, type):
        """
        :return:  List<EnumOption>
        """
        return await self.device.action(f"{self.url}/listEnum", params=[type])

    async def get(self, interface_name, storage, key):
        """
        :param interfaceName: a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interface_name, storage, key]
        return await self.device.action(f"{self.url}/get", params)

    async def getDefault(self, interfaceName, storage, key):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interfaceName, storage, key]
        return await self.device.action(f"{self.url}/getDefault", params)

    async def query(self, params=None):
        """
        :param params: A dictionary with options. The default dictionary is
        configured so it returns you all config API entries with all details, but you
        can put your own with your options. All the options available are this
        ones:
        {
        "configInterface"  : "",
        "defaultValues"    : True,
        "description"      : True,
        "enumInfo"         : True,
        "includeExtensions": True,
        "pattern"          : "",
        "values"           : ""
        }
        :type: Dictionary
        :rtype: List of dictionaries of this style, with more or less detail based on your options.
        """
        if params is None:
            params = [
                {
                    "configInterface": "",
                    "defaultValues": True,
                    "description": True,
                    "enumInfo": True,
                    "includeExtensions": True,
                    "pattern": "",
                    "values": True,
                }
            ]
        return await self.device.action(f"{self.url}/query", params)

    async def reset(self, interfaceName, storage, key):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interfaceName, storage, key]
        return await self.device.action(f"{self.url}/reset", params)

    async def set(self, interface_name, storage, key, value):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        :param value: a valid value for the given key (see type value from List<AdvancedConfigAPIEntry>)
        :type: Object:
        """
        params = [interface_name, storage, key, value]
        return await self.device.action(f"{self.url}/set", params)


class DownloadController:

    def __init__(self, device):
        self.device = device
        self.url = "/downloadcontroller"

    async def start_downloads(self):
        return await self.device.action(f"{self.url}/start")

    async def stop_downloads(self):
        return await self.device.action(f"{self.url}/stop")

    async def pause_downloads(self, value):
        params = [value]
        return await self.device.action(f"{self.url}/pause", params)

    async def get_speed_in_bytes(self):
        return await self.device.action(f"{self.url}/getSpeedInBps")

    async def force_download(self, link_ids, package_ids):
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/forceDownload", params)

    async def get_current_state(self):
        return await self.device.action(f"{self.url}/getCurrentState")


class Extension:
    def __init__(self, device):
        self.device = device
        self.url = "/extensions"

    async def list(self, params=None):
        """
        :param params: A dictionary with options. The default dictionary is
        configured so it returns you all available extensions, but you
        can put your own with your options. All the options available are this
        ones:
        {
        "configInterface"  : True,
        "description"      : True,
        "enabled"          : True,
        "iconKey"          : True,
        "name"             : True,
        "pattern"          : "",
        "installed"        : True
        }
        :type: Dictionary
        :rtype: List of dictionaries of this style, with more or less detail based on your options.
        """
        if params is None:
            params = [
                {
                    "configInterface": True,
                    "description": True,
                    "enabled": True,
                    "iconKey": True,
                    "name": True,
                    "pattern": "",
                    "installed": True,
                }
            ]
        return await self.device.action(f"{self.url}/list", params=params)

    async def install(self, id):
        return await self.device.action(f"{self.url}/install", params=[id])

    async def isInstalled(self, id):
        return await self.device.action(f"{self.url}/isInstalled", params=[id])

    async def isEnabled(self, id):
        return await self.device.action(f"{self.url}/isEnabled", params=[id])

    async def setEnabled(self, id, enabled):
        return await self.device.action(f"{self.url}/setEnabled", params=[id, enabled])


class Linkgrabber:

    def __init__(self, device):
        self.device = device
        self.url = "/linkgrabberv2"

    async def clear_list(self):
        return await self.device.action(f"{self.url}/clearList")

    async def move_to_downloadlist(self, link_ids=None, package_ids=None):
        """
        Moves packages and/or links to download list.

        :param package_ids: Package UUID's.
        :type: list of strings.
        :param link_ids: Link UUID's.
        """
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/moveToDownloadlist", params)

    async def query_links(self, params=None):
        """

        Get the links in the linkcollector/linkgrabber

        :param params: A dictionary with options. The default dictionary is
        configured so it returns you all the downloads with all details, but you
        can put your own with your options. All the options available are this
        ones:
        {
        "bytesTotal"    : false,
        "comment"       : false,
        "status"        : false,
        "enabled"       : false,
        "maxResults"    : -1,
        "startAt"       : 0,
        "packageUUIDs"  : null,
        "hosts"         : false,
        "url"           : false,
        "availability"  : false,
        "variantIcon"   : false,
        "variantName"   : false,
        "variantID"     : false,
        "variants"      : false,
        "priority"      : false
        }
        :type: Dictionary
        :rtype: List of dictionaries of this style, with more or less detail based on your options.

        [   {   'availability': 'ONLINE',
            'bytesTotal': 68548274,
            'enabled': True,
            'name': 'The Rick And Morty Theory - The Original        Morty_ - '
                    'Cartoon Conspiracy (Ep. 74) @ChannelFred (192kbit).m4a',
            'packageUUID': 1450430888524,
            'url': 'youtubev2://DEMUX_M4A_192_720P_V4/d1NZf1w2BxQ/',
            'uuid': 1450430889576,
            'variant': {   'id': 'DEMUX_M4A_192_720P_V4',
                        'name': '192kbit/s M4A-Audio'},
            'variants': True
            }, ... ]
        """
        if params is None:
            params = [
                {
                    "bytesTotal": True,
                    "comment": True,
                    "status": True,
                    "enabled": True,
                    "maxResults": -1,
                    "startAt": 0,
                    "hosts": True,
                    "url": True,
                    "availability": True,
                    "variantIcon": True,
                    "variantName": True,
                    "variantID": True,
                    "variants": True,
                    "priority": True,
                }
            ]
        return await self.device.action(f"{self.url}/queryLinks", params)

    async def cleanup(
        self, action, mode, selection_type, link_ids=None, package_ids=None
    ):
        """
        Clean packages and/or links of the linkgrabber list.
        Requires at least a package_ids or link_ids list, or both.

        :param package_ids: Package UUID's.
        :type: list of strings.
        :param link_ids: link UUID's.
        :type: list of strings
        :param action: Action to be done. Actions: DELETE_ALL, DELETE_DISABLED, DELETE_FAILED, DELETE_FINISHED, DELETE_OFFLINE, DELETE_DUPE, DELETE_MODE
        :type: str:
        :param mode: Mode to use. Modes: REMOVE_LINKS_AND_DELETE_FILES, REMOVE_LINKS_AND_RECYCLE_FILES, REMOVE_LINKS_ONLY
        :type: str:
        :param selection_type: Type of selection to use. Types: SELECTED, UNSELECTED, ALL, NONE
        :type: str:
        """
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        params += [action, mode, selection_type]
        return await self.device.action(f"{self.url}/cleanup", params)

    async def add_container(self, type_, content):
        """
        Adds a container to Linkgrabber.

        :param type_: Type of container.
        :type: string.
        :param content: The container.
        :type: string.

        """
        params = [type_, content]
        return await self.device.action(f"{self.url}/addContainer", params)

    async def get_download_urls(self, link_ids, package_ids, url_display_type):
        """
        Gets download urls from Linkgrabber.

        :param package_ids: Package UUID's.
        :type: List of strings.
        :param link_ids: link UUID's.
        :type: List of strings
        :param url_display_type: No clue. Not documented
        :type: Dictionary
        """
        params = [package_ids, link_ids, url_display_type]
        return await self.device.action(f"{self.url}/getDownloadUrls", params)

    async def set_priority(self, priority, link_ids, package_ids):
        """
        Sets the priority of links or packages.

        :param package_ids: Package UUID's.
        :type: list of strings.
        :param link_ids: link UUID's.
        :type: list of strings
        :param priority: Priority to set. Priorities: HIGHEST, HIGHER, HIGH, DEFAULT, LOWER;
        :type: str:
        """
        params = [priority, link_ids, package_ids]
        return await self.device.action(f"{self.url}/setPriority", params)

    async def set_enabled(self, enable, link_ids, package_ids):
        """
        Enable or disable packages.

        :param enable: Enable or disable package.
        :type: boolean
        :param link_ids: Links UUID.
        :type: list of strings
        :param package_ids: Packages UUID.
        :type: list of strings.
        """
        params = [enable, link_ids, package_ids]
        return await self.device.action(f"{self.url}/setEnabled", params)

    async def get_variants(self, params):
        """
        Gets the variants of a url/download (not package), for example a youtube
        link gives you a package with three downloads, the audio, the video and
        a picture, and each of those downloads have different variants (audio
        quality, video quality, and picture quality).

        :param params: List with the UUID of the download you want the variants. Ex: [232434]
        :type: List
        :rtype: Variants in a list with dictionaries like this one: [{'id':
        'M4A_256', 'name': '256kbit/s M4A-Audio'}, {'id': 'AAC_256', 'name':
        '256kbit/s AAC-Audio'},.......]
        """
        return await self.device.action(f"{self.url}/getVariants", params)

    async def add_links(self, params=None):
        """
        Add links to the linkcollector

        {
        "autostart" : false,
        "links" : null,
        "packageName" : null,
        "extractPassword" : null,
        "priority" : "DEFAULT",
        "downloadPassword" : null,
        "destinationFolder" : null
        }
        """
        if params is None:
            params = [
                {
                    "autostart": False,
                    "links": None,
                    "packageName": None,
                    "extractPassword": None,
                    "priority": "DEFAULT",
                    "downloadPassword": None,
                    "destinationFolder": None,
                    "overwritePackagizerRules": False,
                }
            ]
        return await self.device.action(f"{self.url}/addLinks", params)

    async def is_collecting(self):
        """
        Boolean status query about the collecting process
        """
        return await self.device.action(f"{self.url}/isCollecting")

    async def set_download_directory(self, dir: str, package_ids: list):
        params = [dir, package_ids]
        return await self.device.action(f"{self.url}/setDownloadDirectory", params)

    async def move_to_new_package(
        self, name: str, path: str, link_ids: list = None, package_ids: list = None
    ):
        # Requires at least a link_ids or package_ids list, or both.
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids, name, path]
        return await self.device.action(f"{self.url}/movetoNewPackage", params)

    async def remove_links(self, link_ids=None, package_ids=None):
        """
        Remove packages and/or links of the linkgrabber list.
        Requires at least a link_ids or package_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings
        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/removeLinks", params)

    async def rename_link(self, link_id, new_name):
        """
        Renames files related with link_id
        """
        params = [link_id, new_name]
        return await self.device.action(f"{self.url}/renameLink", params)

    async def get_package_count(self):
        return await self.device.action(f"{self.url}/getPackageCount")

    async def rename_package(self, package_id, new_name):
        """
        Rename package name with package_id
        """
        params = [package_id, new_name]
        return await self.device.action(f"{self.url}/renamePackage", params)

    async def query_packages(self, params=None):
        if params is None:
            params = [
                {
                    "availableOfflineCount": True,
                    "availableOnlineCount": True,
                    "availableTempUnknownCount": True,
                    "availableUnknownCount": True,
                    "bytesTotal": True,
                    "childCount": True,
                    "comment": True,
                    "enabled": True,
                    "hosts": True,
                    "maxResults": -1,
                    "packageUUIDs": [],
                    "priority": True,
                    "saveTo": True,
                    "startAt": 0,
                    "status": True,
                }
            ]
        return await self.device.action(f"{self.url}/queryPackages", params)


class Downloads:

    def __init__(self, device):
        self.device = device
        self.url = "/downloadsV2"

    async def query_links(self, params=None):
        """
        Get the links in the download list
        """
        if params is None:
            params = [
                {
                    "addedDate": True,
                    "bytesLoaded": True,
                    "bytesTotal": True,
                    "comment": True,
                    "enabled": True,
                    "eta": True,
                    "extractionStatus": True,
                    "finished": True,
                    "finishedDate": True,
                    "host": True,
                    "jobUUIDs": [],
                    "maxResults": -1,
                    "packageUUIDs": [],
                    "password": True,
                    "priority": True,
                    "running": True,
                    "skipped": True,
                    "speed": True,
                    "startAt": 0,
                    "status": True,
                    "url": True,
                }
            ]
        return await self.device.action(f"{self.url}/queryLinks", params)

    async def query_packages(self, params=None):
        if params is None:
            params = [
                {
                    "bytesLoaded": True,
                    "bytesTotal": True,
                    "childCount": True,
                    "comment": True,
                    "enabled": True,
                    "eta": True,
                    "finished": True,
                    "hosts": True,
                    "maxResults": -1,
                    "packageUUIDs": [],
                    "priority": True,
                    "running": True,
                    "saveTo": True,
                    "speed": True,
                    "startAt": 0,
                    "status": True,
                }
            ]
        return await self.device.action(f"{self.url}/queryPackages", params)

    async def cleanup(
        self, action, mode, selection_type, link_ids=None, package_ids=None
    ):
        """
        Clean packages and/or links of the linkgrabber list.
        Requires at least a package_ids or link_ids list, or both.

        :param package_ids: Package UUID's.
        :type: list of strings.
        :param link_ids: link UUID's.
        :type: list of strings
        :param action: Action to be done. Actions: DELETE_ALL, DELETE_DISABLED, DELETE_FAILED, DELETE_FINISHED, DELETE_OFFLINE, DELETE_DUPE, DELETE_MODE
        :type: str:
        :param mode: Mode to use. Modes: REMOVE_LINKS_AND_DELETE_FILES, REMOVE_LINKS_AND_RECYCLE_FILES, REMOVE_LINKS_ONLY
        :type: str:
        :param selection_type: Type of selection to use. Types: SELECTED, UNSELECTED, ALL, NONE
        :type: str:
        """
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        params += [action, mode, selection_type]
        return await self.device.action(f"{self.url}/cleanup", params)

    async def set_enabled(self, enable, link_ids, package_ids):
        """
        Enable or disable packages.

        :param enable: Enable or disable package.
        :type: boolean
        :param link_ids: Links UUID.
        :type: list of strings
        :param package_ids: Packages UUID.
        :type: list of strings.
        """
        params = [enable, link_ids, package_ids]
        return await self.device.action(f"{self.url}/setEnabled", params)

    async def force_download(self, link_ids=None, package_ids=None):
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/forceDownload", params)

    async def set_dl_location(self, directory, package_ids=None):
        if package_ids is None:
            package_ids = []
        params = [directory, package_ids]
        return await self.device.action(f"{self.url}/setDownloadDirectory", params)

    async def remove_links(self, link_ids=None, package_ids=None):
        """
        Remove packages and/or links of the downloads list.
        NOTE: For more specific removal, like deleting the files etc, use the /cleanup api.
        Requires at least a link_ids or package_ids list, or both.

        :param link_ids: link UUID's.
        :type: list of strings
        :param package_ids: Package UUID's.
        :type: list of strings.
        """
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/removeLinks", params)

    async def reset_links(self, link_ids, package_ids):
        params = [link_ids, package_ids]
        return await self.device.action(f"{self.url}/resetLinks", params)

    async def move_to_new_package(
        self, link_ids, package_ids, new_pkg_name, download_path
    ):
        params = [link_ids, package_ids, new_pkg_name, download_path]
        return await self.device.action(f"{self.url}/movetoNewPackage", params)

    async def rename_link(self, link_id: list, new_name: str):
        params = [link_id, new_name]
        return await self.device.action(f"{self.url}/renameLink", params)


class Captcha:

    def __init__(self, device):
        self.device = device
        self.url = "/captcha"

    async def list(self):
        return await self.device.action(f"{self.url}/list", [])

    async def get(self, captcha_id):
        return await self.device.action(f"{self.url}/get", (captcha_id,))

    async def solve(self, captcha_id, solution):
        return await self.device.action(f"{self.url}/solve", (captcha_id, solution))


class Jddevice:

    def __init__(self, jd):
        """This functions initializates the device instance.
        It uses the provided dictionary to create the device.

        :param device_dict: Device dictionary
        """
        self.myjd = jd
        self.config = Config(self)
        self.linkgrabber = Linkgrabber(self)
        self.captcha = Captcha(self)
        self.downloads = Downloads(self)
        self.downloadcontroller = DownloadController(self)
        self.extensions = Extension(self)
        self.jd = Jd(self)
        self.system = System(self)

    async def ping(self):
        return await self.action("/device/ping")

    async def action(self, path, params=()):
        response = await self.myjd.request_api(path, params)
        if response is None:
            raise (MYJDConnectionException("No connection established\n"))
        return response["data"]


class clientSession(AsyncClient):

    @wraps(AsyncClient.request)
    async def request(self, method: str, url: str, **kwargs):
        kwargs.setdefault("timeout", 3)
        kwargs.setdefault("follow_redirects", True)
        return await super().request(method, url, **kwargs)


class MyJdApi:

    def __init__(self):
        self.__api_url = "http://127.0.0.1:3128"
        self._http_session = None
        self.device = Jddevice(self)

    def _session(self):
        if self._http_session is not None:
            return self._http_session

        transport = AsyncHTTPTransport(retries=10, verify=False)

        self._http_session = clientSession(transport=transport)

        self._http_session.verify = False

        return self._http_session

    async def close(self):
        if self._http_session is not None:
            await self._http_session.aclose()
            self._http_session = None

    async def request_api(self, path, params=None):
        session = self._session()

        # Prepare params_request based on the input params
        params_request = params if params is not None else []

        # Construct the request payload
        params_request = {
            "params": params_request,
        }
        data = dumps(params_request)
        # Removing quotes around null elements.
        data = data.replace('"null"', "null")
        data = data.replace("'null'", "null")
        request_url = self.__api_url + path
        try:
            res = await session.request(
                "POST",
                request_url,
                headers={"Content-Type": "application/json; charset=utf-8"},
                content=data,
            )
            response = res.text
        except RequestError:
            return None
        if res.status_code != 200:
            try:
                error_msg = loads(response)
            except JSONDecodeError as exc:
                raise MYJDDecodeException(
                    "Failed to decode response: {}", response
                ) from exc
            msg = (
                "\n\tSOURCE: "
                + error_msg["src"]
                + "\n\tTYPE: "
                + error_msg["type"]
                + "\n------\nREQUEST_URL: "
                + self.__api_url
                + path
            )
            msg += "\n"
            if data is not None:
                msg += "DATA:\n" + data
            raise (
                MYJDApiException.get_exception(error_msg["src"], error_msg["type"], msg)
            )
        return loads(response)
