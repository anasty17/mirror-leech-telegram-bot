from bot import download_list


def get_download(update_id):
    return download_list[update_id].download()


def get_download_status_list():
    return list(download_list.values())


def get_download_index(_list, gid):
    index = 0
    for i in _list:
        if i.download().gid == gid:
            return index
        index += 1


def get_download_str():
    result = ""
    for status in list(download_list.values()):
        result += (status.progress() + status.speed() + status.status())
    return result
