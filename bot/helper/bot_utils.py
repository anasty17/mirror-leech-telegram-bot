
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
        msg += "<b>Name:</b> {}\n" \
               "<b>status:</b> {}\n" \
               "<b>Downloaded:</b> {} of {}\n" \
               "<b>Speed:</b> {}\n" \
               "<b>ETA:</b> {}\n\n".format(status.name(), status.status(),
                                           status.progress(), status.size(),
                                           status.speed(), status.eta())
    return msg


# Custom Exception class for killing thread as soon as they aren't needed
class KillThreadException(Exception):
    def __init__(self, message, error=None):
        super().__init__(message)
        self.error = error
