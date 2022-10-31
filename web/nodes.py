from anytree import NodeMixin
from re import findall as re_findall
from os import environ

DOWNLOAD_DIR = environ.get('DOWNLOAD_DIR', '')
if len(DOWNLOAD_DIR) == 0:
    DOWNLOAD_DIR = '/usr/src/app/downloads/'
elif not DOWNLOAD_DIR.endswith("/"):
    DOWNLOAD_DIR = f'{DOWNLOAD_DIR}/'


class TorNode(NodeMixin):
    def __init__(self, name, is_folder=False, is_file=False, parent=None, size=None, priority=None, file_id=None, progress=None):
        super().__init__()
        self.name = name
        self.is_folder = is_folder
        self.is_file = is_file

        if parent is not None:
            self.parent = parent
        if size is not None:
            self.size = size
        if priority is not None:
            self.priority = priority
        if file_id is not None:
            self.file_id = file_id
        if progress is not None:
            self.progress = progress


def qb_get_folders(path):
    return path.split("/")

def get_folders(path):
    fs = re_findall(f'{DOWNLOAD_DIR}[0-9]+/(.+)', path)[0]
    return fs.split('/')

def make_tree(res, aria2=False):
    parent = TorNode("Torrent")
    if not aria2:
        for i in res:
            folders = qb_get_folders(i.name)
            if len(folders) > 1:
                previous_node = parent
                for j in range(len(folders)-1):
                    current_node = next((k for k in previous_node.children if k.name == folders[j]), None)
                    if current_node is None:
                        previous_node = TorNode(folders[j], parent=previous_node, is_folder=True)
                    else:
                        previous_node = current_node
                TorNode(folders[-1], is_file=True, parent=previous_node, size=i.size, priority=i.priority, \
                        file_id=i.id, progress=round(i.progress*100, 5))
            else:
                TorNode(folders[-1], is_file=True, parent=parent, size=i.size, priority=i.priority, \
                        file_id=i.id, progress=round(i.progress*100, 5))
    else:
        for i in res:
            folders = get_folders(i['path'])
            priority = 1
            if i['selected'] == 'false':
                priority = 0
            if len(folders) > 1:
                previous_node = parent
                for j in range(len(folders)-1):
                    current_node = next((k for k in previous_node.children if k.name == folders[j]), None)
                    if current_node is None:
                        previous_node = TorNode(folders[j], parent=previous_node, is_folder=True)
                    else:
                        previous_node = current_node
                TorNode(folders[-1], is_file=True, parent=previous_node, size=i['length'], priority=priority, \
                        file_id=i['index'], progress=round((int(i['completedLength'])/int(i['length']))*100, 5))
            else:
                TorNode(folders[-1], is_file=True, parent=parent, size=i['length'], priority=priority, \
                        file_id=i['index'], progress=round((int(i['completedLength'])/int(i['length']))*100, 5))
    return create_list(parent, ["", 0])

"""
def print_tree(parent):
    for pre, _, node in RenderTree(parent):
        treestr = u"%s%s" % (pre, node.name)
        print(treestr.ljust(8), node.is_folder, node.is_file)
"""

def create_list(par, msg):
    if par.name != ".unwanted":
        msg[0] += '<ul>'
    for i in par.children:
        if i.is_folder:
            msg[0] += "<li>"
            if i.name != ".unwanted":
                msg[0] += f'<input type="checkbox" name="foldernode_{msg[1]}"> <label for="{i.name}">{i.name}</label>'
            create_list(i, msg)
            msg[0] += "</li>"
            msg[1] += 1
        else:
            msg[0] += '<li>'
            if i.priority == 0:
                msg[0] += f'<input type="checkbox" name="filenode_{i.file_id}" data-size="{i.size}"> <label data-size="{i.size}" for="filenode_{i.file_id}">{i.name}</label> / {i.progress}%'
            else:
                msg[0] += f'<input type="checkbox" checked name="filenode_{i.file_id}" data-size="{i.size}"> <label data-size="{i.size}" for="filenode_{i.file_id}">{i.name}</label> / {i.progress}%'
            msg[0] += f'<input type="hidden" value="off" name="filenode_{i.file_id}">'
            msg[0] += "</li>"

    if par.name != ".unwanted":
        msg[0] += "</ul>"
    return msg
