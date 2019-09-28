
from bot import download_dict


def get_download(message_id):
    return download_dict[message_id].download()


def get_download_status_list():
    return list(download_dict.values())


def get_download_index(_list, gid):
    index = 0
    for i in _list:
        if i.download().gid == gid:
            return index
        index += 1


def get_download_str():
    result = ""
    for status in list(download_dict.values()):
        result += (status.progress() + status.speed() + status.status())
    return result


def get_readable_message(progress_list: list = download_dict.values()):
    msg = ""
    for status in progress_list:
        msg += f'<b>Name:</b> {status.name()}\n' \
               f'<b>status:</b> {status.status()}\n' \
               f'<b>Downloaded:</b> {status.progress()} of {status.size()}\n' \
               f'<b>Speed:</b> {status.speed()}\n' \
               f'<b>ETA:</b> {status.eta()}\n\n'
    return msg


# Custom Exception class for killing thread as soon as they aren't needed
class KillThreadException(Exception):
    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error
