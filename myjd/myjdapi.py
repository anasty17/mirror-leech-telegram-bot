# -*- encoding: utf-8 -*-
from hashlib import sha256
from hmac import new
from json import dumps, loads, JSONDecodeError
from time import time
from urllib.parse import quote
from base64 import b64encode, b64decode
from requests import get, post
from requests.exceptions import RequestException
from Crypto.Cipher import AES

from .exception import (
    MYJDException,
    MYJDApiException,
    MYJDConnectionException,
    MYJDDecodeException,
    MYJDDeviceNotFoundException,
)

BS = 16


def PAD(s):
    return s + ((BS - len(s) % BS) * chr(BS - len(s) % BS)).encode()


def UNPAD(s):
    return s[: -s[-1]]


class System:
    """
    Class that represents the system-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/system"

    def exit_jd(self):
        return self.device.action(f"{self.url}/exitJD")

    def restart_jd(self):
        return self.device.action(f"{self.url}/restartJD")

    def hibernate_os(self):
        return self.device.action(f"{self.url}/hibernateOS")

    def shutdown_os(self, force):
        """

        :param force:  Force Shutdown of OS
        :return:
        """
        params = force
        return self.device.action(f"{self.url}/shutdownOS", params)

    def standby_os(self):
        """

        :return:
        """
        return self.device.action(f"{self.url}/standbyOS")

    def get_storage_info(self):
        """

        :return:
        """
        return self.device.action(f"{self.url}/getStorageInfos?path")


class Jd:
    """
    Class that represents the jd-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/jd"

    def get_core_revision(self):
        """

        :return:
        """
        return self.device.action(f"{self.url}/getCoreRevision")


class Update:
    """
    Class that represents the update-functionality of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/update"

    def restart_and_update(self):
        """

        :return:
        """
        return self.device.action(f"{self.url}/restartAndUpdate")

    def run_update_check(self):
        return self.device.action(f"{self.url}/runUpdateCheck")

    def is_update_available(self):
        return self.device.action(f"{self.url}/isUpdateAvailable")

    def update_available(self):
        self.run_update_check()
        return self.is_update_available()


class Config:
    """
    Class that represents the Config of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/config"

    def list(self, params=None):
        """
        :return:  List<AdvancedConfigAPIEntry>
        """
        if params is None:
            return self.device.action(f"{self.url}/list", params)
        else:
            return self.device.action(f"{self.url}/list")

    def listEnum(self, type):
        """
        :return:  List<EnumOption>
        """
        return self.device.action(f"{self.url}/listEnum", params=[type])

    def get(self, interface_name, storage, key):
        """
        :param interfaceName: a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interface_name, storage, key]
        return self.device.action(f"{self.url}/get", params)

    def getDefault(self, interfaceName, storage, key):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interfaceName, storage, key]
        return self.device.action(f"{self.url}/getDefault", params)

    def query(self, params=None):
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
        return self.device.action(f"{self.url}/query", params)

    def reset(self, interfaceName, storage, key):
        """
        :param interfaceName:  a valid interface name from List<AdvancedConfigAPIEntry>
        :type: str:
        :param storage: 'null' to use default or 'cfg/' + interfaceName
        :type: str:
        :param key: a valid key from from List<AdvancedConfigAPIEntry>
        :type: str:
        """
        params = [interfaceName, storage, key]
        return self.device.action(f"{self.url}/reset", params)

    def set(self, interface_name, storage, key, value):
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
        return self.device.action(f"{self.url}/set", params)


class DownloadController:
    """
    Class that represents the download-controller of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/downloadcontroller"

    def start_downloads(self):
        return self.device.action(f"{self.url}/start")

    def stop_downloads(self):
        return self.device.action(f"{self.url}/stop")

    def pause_downloads(self, value):
        """

        :param value:
        :return:
        """
        params = [value]
        return self.device.action(f"{self.url}/pause", params)

    def get_speed_in_bytes(self):
        return self.device.action(f"{self.url}/getSpeedInBps")

    def force_download(self, link_ids, package_ids):
        """
        :param link_ids:
        :param package_ids:
        :return:
        """
        params = [link_ids, package_ids]
        return self.device.action(f"{self.url}/forceDownload", params)

    def get_current_state(self):
        return self.device.action(f"{self.url}/getCurrentState")


class Extension:
    def __init__(self, device):
        self.device = device
        self.url = "/extensions"

    def list(self, params=None):
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
        return self.device.action(f"{self.url}/list", params=params)

    def install(self, id):
        return self.device.action(f"{self.url}/install", params=[id])

    def isInstalled(self, id):
        return self.device.action(f"{self.url}/isInstalled", params=[id])

    def isEnabled(self, id):
        return self.device.action(f"{self.url}/isEnabled", params=[id])

    def setEnabled(self, id, enabled):
        return self.device.action(f"{self.url}/setEnabled", params=[id, enabled])


class Linkgrabber:
    """
    Class that represents the linkgrabber of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/linkgrabberv2"

    def clear_list(self):
        """
        Clears Linkgrabbers list
        """
        return self.device.action(f"{self.url}/clearList", http_action="POST")

    def move_to_downloadlist(self, link_ids=None, package_ids=None):
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
        return self.device.action(f"{self.url}/moveToDownloadlist", params)

    def query_links(self, params=None):
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
        return self.device.action(f"{self.url}/queryLinks", params)

    def cleanup(self, action, mode, selection_type, link_ids=None, package_ids=None):
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
        return self.device.action(f"{self.url}/cleanup", params)

    def add_container(self, type_, content):
        """
        Adds a container to Linkgrabber.

        :param type_: Type of container.
        :type: string.
        :param content: The container.
        :type: string.

        """
        params = [type_, content]
        return self.device.action(f"{self.url}/addContainer", params)

    def get_download_urls(self, link_ids, package_ids, url_display_type):
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
        return self.device.action(f"{self.url}/getDownloadUrls", params)

    def set_priority(self, priority, link_ids, package_ids):
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
        return self.device.action(f"{self.url}/setPriority", params)

    def set_enabled(self, enable, link_ids, package_ids):
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
        return self.device.action(f"{self.url}/setEnabled", params)

    def get_variants(self, params):
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
        return self.device.action(f"{self.url}/getVariants", params)

    def add_links(self, params=None):
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
        return self.device.action(f"{self.url}/addLinks", params)

    def is_collecting(self):
        """
        Boolean status query about the collecting process
        """
        return self.device.action(f"{self.url}/isCollecting")

    def set_download_directory(self, dir: str, package_ids: list):
        params = [dir, package_ids]
        return self.device.action(f"{self.url}/setDownloadDirectory", params)

    def remove_links(self, link_ids=None, package_ids=None):
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
        return self.device.action(f"{self.url}/removeLinks", params)

    def rename_link(self, link_id, new_name):
        """
        Renames files related with link_id
        """
        params = [link_id, new_name]
        return self.device.action(f"{self.url}/renameLink", params)

    def move_to_new_package(self, link_ids, package_ids, new_pkg_name, download_path):
        params = link_ids, package_ids, new_pkg_name, download_path
        return self.device.action(f"{self.url}/movetoNewPackage", params)

    def get_package_count(self):
        return self.device.action(f"{self.url}/getPackageCount")

    def rename_package(self, package_id, new_name):
        """
        Rename package name with package_id
        """
        params = [package_id, new_name]
        return self.device.action(f"{self.url}/renamePackage", params)

    def query_packages(self, params=None):
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
        return self.device.action(f"{self.url}/queryPackages", params)


class Downloads:
    """
    Class that represents the downloads list of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/downloadsV2"

    def query_links(self, params=None):
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
        return self.device.action(f"{self.url}/queryLinks", params)

    def query_packages(self, params=None):
        """
        Get the packages in the download list
        """
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
        return self.device.action(f"{self.url}/queryPackages", params)

    def cleanup(self, action, mode, selection_type, link_ids=None, package_ids=None):
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
        return self.device.action(f"{self.url}/cleanup", params)

    def set_enabled(self, enable, link_ids, package_ids):
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
        return self.device.action(f"{self.url}/setEnabled", params)

    def force_download(self, link_ids=None, package_ids=None):
        if link_ids is None:
            link_ids = []
        if package_ids is None:
            package_ids = []
        params = [link_ids, package_ids]
        return self.device.action(f"{self.url}/forceDownload", params)

    def set_dl_location(self, directory, package_ids=None):
        if package_ids is None:
            package_ids = []
        params = [directory, package_ids]
        return self.device.action(f"{self.url}/setDownloadDirectory", params)

    def remove_links(self, link_ids=None, package_ids=None):
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
        return self.device.action(f"{self.url}/removeLinks", params)

    def reset_links(self, link_ids, package_ids):
        params = [link_ids, package_ids]
        return self.device.action(f"{self.url}/resetLinks", params)

    def move_to_new_package(self, link_ids, package_ids, new_pkg_name, download_path):
        params = link_ids, package_ids, new_pkg_name, download_path
        return self.device.action(f"{self.url}/movetoNewPackage", params)


class Captcha:
    """
    Class that represents the captcha interface of a Device
    """

    def __init__(self, device):
        self.device = device
        self.url = "/captcha"

    """
    Get the waiting captchas
    """

    def list(self):
        return self.device.action(f"{self.url}/list", [])

    """
    Get the base64 captcha image
    """

    def get(self, captcha_id):
        return self.device.action(f"{self.url}/get", (captcha_id,))

    """
    Solve a captcha
    """

    def solve(self, captcha_id, solution):
        return self.device.action(f"{self.url}/solve", (captcha_id, solution))


class Jddevice:
    """
    Class that represents a JDownloader device and it's functions
    """

    def __init__(self, jd, device_dict):
        """This functions initializates the device instance.
        It uses the provided dictionary to create the device.

        :param device_dict: Device dictionary
        """
        self.name = device_dict["name"]
        self.device_id = device_dict["id"]
        self.device_type = device_dict["type"]
        self.myjd = jd
        self.config = Config(self)
        self.linkgrabber = Linkgrabber(self)
        self.captcha = Captcha(self)
        self.downloads = Downloads(self)
        self.downloadcontroller = DownloadController(self)
        self.extensions = Extension(self)
        self.update = Update(self)
        self.jd = Jd(self)
        self.system = System(self)
        self.__direct_connection_info = None
        self.__refresh_direct_connections()
        self.__direct_connection_enabled = True
        self.__direct_connection_cooldown = 0
        self.__direct_connection_consecutive_failures = 0

    def __refresh_direct_connections(self):
        response = self.myjd.request_api(
            "/device/getDirectConnectionInfos", "POST", None, self.__action_url()
        )
        if (
            response is not None
            and "data" in response
            and "infos" in response["data"]
            and len(response["data"]["infos"]) != 0
        ):
            self.__update_direct_connections(response["data"]["infos"])

    def __update_direct_connections(self, direct_info):
        """
        Updates the direct_connections info keeping the order.
        """
        tmp = []
        if self.__direct_connection_info is None:
            tmp.extend({"conn": conn, "cooldown": 0} for conn in direct_info)
            self.__direct_connection_info = tmp
            return
        #  We remove old connections not available anymore.
        for i in self.__direct_connection_info:
            if i["conn"] not in direct_info:
                tmp.remove(i)
            else:
                direct_info.remove(i["conn"])
        # We add new connections
        tmp.extend({"conn": conn, "cooldown": 0} for conn in direct_info)
        self.__direct_connection_info = tmp

    def enable_direct_connection(self):
        self.__direct_connection_enabled = True
        self.__refresh_direct_connections()

    def disable_direct_connection(self):
        self.__direct_connection_enabled = False
        self.__direct_connection_info = None

    def action(self, path, params=(), http_action="POST"):
        action_url = self.__action_url()
        if (
            self.__direct_connection_enabled
            and self.__direct_connection_info is not None
            and time() >= self.__direct_connection_cooldown
        ):
            return self.__direct_connect(path, http_action, params, action_url)
        response = self.myjd.request_api(path, http_action, params, action_url)
        if response is None:
            raise (MYJDConnectionException("No connection established\n"))
        if (
            self.__direct_connection_enabled
            and time() >= self.__direct_connection_cooldown
        ):
            self.__refresh_direct_connections()
        return response["data"]

    def __direct_connect(self, path, http_action, params, action_url):
        for conn in self.__direct_connection_info:
            if time() > conn["cooldown"]:
                connection = conn["conn"]
                api = "http://" + connection["ip"] + ":" + str(connection["port"])
                response = self.myjd.request_api(
                    path, http_action, params, action_url, api
                )
                if response is not None:
                    self.__direct_connection_info.remove(conn)
                    self.__direct_connection_info.insert(0, conn)
                    self.__direct_connection_consecutive_failures = 0
                    return response["data"]
                else:
                    conn["cooldown"] = time() + 60
        self.__direct_connection_consecutive_failures += 1
        self.__direct_connection_cooldown = time() + (
            60 * self.__direct_connection_consecutive_failures
        )
        response = self.myjd.request_api(path, http_action, params, action_url)
        if response is None:
            raise (MYJDConnectionException("No connection established\n"))
        self.__refresh_direct_connections()
        return response["data"]

    def __action_url(self):
        return f"/t_{self.myjd.get_session_token()}_{self.device_id}"


class Myjdapi:
    """
    Main class for connecting to JD API.

    """

    def __init__(self):
        """
        This functions initializates the myjdapi object.

        """
        self.__request_id = int(time() * 1000)
        self.__api_url = "https://api.jdownloader.org"
        self.__app_key = "http://git.io/vmcsk"
        self.__api_version = 1
        self.__devices = None
        self.__login_secret = None
        self.__device_secret = None
        self.__session_token = None
        self.__regain_token = None
        self.__server_encryption_token = None
        self.__device_encryption_token = None
        self.__connected = False

    def get_session_token(self):
        return self.__session_token

    def is_connected(self):
        """
        Indicates if there is a connection established.
        """
        return self.__connected

    def set_app_key(self, app_key):
        """
        Sets the APP Key.
        """
        self.__app_key = app_key

    def __secret_create(self, email, password, domain):
        """
        Calculates the login_secret and device_secret

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :param domain: The domain , if is for Server (login_secret) or Device (device_secret)
        :return: secret hash

        """
        secret_hash = sha256()
        secret_hash.update(
            email.lower().encode("utf-8")
            + password.encode("utf-8")
            + domain.lower().encode("utf-8")
        )
        return secret_hash.digest()

    def __update_encryption_tokens(self):
        """
        Updates the server_encryption_token and device_encryption_token

        """
        if self.__server_encryption_token is None:
            old_token = self.__login_secret
        else:
            old_token = self.__server_encryption_token
        new_token = sha256()
        new_token.update(old_token + bytearray.fromhex(self.__session_token))
        self.__server_encryption_token = new_token.digest()
        new_token = sha256()
        new_token.update(self.__device_secret + bytearray.fromhex(self.__session_token))
        self.__device_encryption_token = new_token.digest()

    def __signature_create(self, key, data):
        """
        Calculates the signature for the data given a key.

        :param key:
        :param data:
        """
        signature = new(key, data.encode("utf-8"), sha256)
        return signature.hexdigest()

    def __decrypt(self, secret_token, data):
        """
        Decrypts the data from the server using the provided token

        :param secret_token:
        :param data:
        """
        init_vector = secret_token[: len(secret_token) // 2]
        key = secret_token[len(secret_token) // 2 :]
        decryptor = AES.new(key, AES.MODE_CBC, init_vector)
        return UNPAD(decryptor.decrypt(b64decode(data)))

    def __encrypt(self, secret_token, data):
        """
        Encrypts the data from the server using the provided token

        :param secret_token:
        :param data:
        """
        data = PAD(data.encode("utf-8"))
        init_vector = secret_token[: len(secret_token) // 2]
        key = secret_token[len(secret_token) // 2 :]
        encryptor = AES.new(key, AES.MODE_CBC, init_vector)
        encrypted_data = b64encode(encryptor.encrypt(data))
        return encrypted_data.decode("utf-8")

    def update_request_id(self):
        """
        Updates Request_Id
        """
        self.__request_id = int(time())

    def connect(self, email, password):
        """Establish connection to api

        :param email: My.Jdownloader User email
        :param password: My.Jdownloader User password
        :returns: boolean -- True if succesful, False if there was any error.

        """
        self.__clean_resources()
        self.__login_secret = self.__secret_create(email, password, "server")
        self.__device_secret = self.__secret_create(email, password, "device")
        response = self.request_api(
            "/my/connect", "GET", [("email", email), ("appkey", self.__app_key)]
        )
        self.__connected = True
        self.update_request_id()
        self.__session_token = response["sessiontoken"]
        self.__regain_token = response["regaintoken"]
        self.__update_encryption_tokens()
        self.update_devices()
        return response

    def reconnect(self):
        """
        Reestablish connection to API.

        :returns: boolean -- True if successful, False if there was any error.

        """
        response = self.request_api(
            "/my/reconnect",
            "GET",
            [
                ("sessiontoken", self.__session_token),
                ("regaintoken", self.__regain_token),
            ],
        )
        self.update_request_id()
        self.__session_token = response["sessiontoken"]
        self.__regain_token = response["regaintoken"]
        self.__update_encryption_tokens()
        return response

    def disconnect(self):
        """
        Disconnects from  API

        :returns: boolean -- True if successful, False if there was any error.

        """
        response = self.request_api(
            "/my/disconnect", "GET", [("sessiontoken", self.__session_token)]
        )
        self.__clean_resources()
        return response

    def __clean_resources(self):
        self.update_request_id()
        self.__login_secret = None
        self.__device_secret = None
        self.__session_token = None
        self.__regain_token = None
        self.__server_encryption_token = None
        self.__device_encryption_token = None
        self.__devices = None
        self.__connected = False

    def update_devices(self):
        """
        Updates available devices. Use list_devices() to get the devices list.

        :returns: boolean -- True if successful, False if there was any error.
        """
        response = self.request_api(
            "/my/listdevices", "GET", [("sessiontoken", self.__session_token)]
        )
        self.update_request_id()
        self.__devices = response["list"]

    def list_devices(self):
        """
        Returns available devices. Use getDevices() to update the devices list.
        Each device in the list is a dictionary like this example:

        {
            'name': 'Device',
            'id': 'af9d03a21ddb917492dc1af8a6427f11',
            'type': 'jd'
        }

        :returns: list -- list of devices.
        """
        return self.__devices

    def get_device(self, device_name=None, device_id=None):
        """
        Returns a jddevice instance of the device

        :param deviceid:
        """
        if not self.is_connected():
            raise (MYJDConnectionException("No connection established\n"))
        if device_id is not None:
            for device in self.__devices:
                if device["id"] == device_id:
                    return Jddevice(self, device)
        elif device_name is not None:
            for device in self.__devices:
                if device["name"] == device_name:
                    return Jddevice(self, device)
        raise (MYJDDeviceNotFoundException("Device not found\n"))

    def request_api(self, path, http_method="GET", params=None, action=None, api=None):
        """
        Makes a request to the API to the 'path' using the 'http_method' with parameters,'params'.
        Ex:
        http_method=GET
        params={"test":"test"}
        post_params={"test2":"test2"}
        action=True
        This would make a request to "https://api.jdownloader.org"
        """
        if not api:
            api = self.__api_url
        data = None
        if not self.is_connected() and path != "/my/connect":
            raise (MYJDConnectionException("No connection established\n"))
        if http_method == "GET":
            query = [f"{path}?"]
            if params is not None:
                for param in params:
                    if param[0] != "encryptedLoginSecret":
                        query += [f"{param[0]}={quote(param[1])}"]
                    else:
                        query += [f"&{param[0]}={param[1]}"]
            query += [f"rid={str(self.__request_id)}"]
            if self.__server_encryption_token is None:
                query += [
                    "signature="
                    + str(
                        self.__signature_create(
                            self.__login_secret, query[0] + "&".join(query[1:])
                        )
                    )
                ]
            else:
                query += [
                    "signature="
                    + str(
                        self.__signature_create(
                            self.__server_encryption_token,
                            query[0] + "&".join(query[1:]),
                        )
                    )
                ]
            query = query[0] + "&".join(query[1:])
            encrypted_response = get(api + query, timeout=3, verify=False)
        else:
            params_request = []
            if params is not None:
                for param in params:
                    if isinstance(param, (str, list)):
                        params_request += [param]
                    elif isinstance(param, (dict, bool)):
                        params_request += [dumps(param)]
                    else:
                        params_request += [str(param)]
            params_request = {
                "apiVer": self.__api_version,
                "url": path,
                "params": params_request,
                "rid": self.__request_id,
            }
            data = dumps(params_request)
            # Removing quotes around null elements.
            data = data.replace('"null"', "null")
            data = data.replace("'null'", "null")
            encrypted_data = self.__encrypt(self.__device_encryption_token, data)
            request_url = api + action + path if action is not None else api + path
            try:
                encrypted_response = post(
                    request_url,
                    headers={"Content-Type": "application/aesjson-jd; charset=utf-8"},
                    data=encrypted_data,
                    timeout=3,
                    verify=False,
                )
            except RequestException as e:
                return None
        if encrypted_response.status_code != 200:
            try:
                error_msg = loads(encrypted_response.text)
            except JSONDecodeError:
                try:
                    error_msg = loads(
                        self.__decrypt(
                            self.__device_encryption_token, encrypted_response.text
                        )
                    )
                except JSONDecodeError as exc:
                    raise MYJDDecodeException(
                        "Failed to decode response: {}", encrypted_response.text
                    ) from exc
            msg = (
                "\n\tSOURCE: "
                + error_msg["src"]
                + "\n\tTYPE: "
                + error_msg["type"]
                + "\n------\nREQUEST_URL: "
                + api
                + path
            )
            if http_method == "GET":
                msg += query
            msg += "\n"
            if data is not None:
                msg += "DATA:\n" + data
            raise (
                MYJDApiException.get_exception(error_msg["src"], error_msg["type"], msg)
            )
        if action is None:
            if not self.__server_encryption_token:
                response = self.__decrypt(self.__login_secret, encrypted_response.text)
            else:
                response = self.__decrypt(
                    self.__server_encryption_token, encrypted_response.text
                )
        else:
            response = self.__decrypt(
                self.__device_encryption_token, encrypted_response.text
            )
        jsondata = loads(response.decode("utf-8"))
        if jsondata["rid"] != self.__request_id:
            self.update_request_id()
            return None
        self.update_request_id()
        return jsondata
