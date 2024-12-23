from aria2p import API as ariaAPI, Client as ariaClient
from flask import Flask, request, render_template, jsonify
from logging import getLogger, FileHandler, StreamHandler, INFO, basicConfig
from qbittorrentapi import NotFound404Error, Client as qbClient
from time import sleep

from web.nodes import extract_file_ids, make_tree

app = Flask(__name__)


qbittorrent_client = qbClient(
    host="localhost",
    port=8090,
    VERIFY_WEBUI_CERTIFICATE=False,
    REQUESTS_ARGS={"timeout": (30, 60)},
    HTTPADAPTER_ARGS={"pool_maxsize": 200, "pool_block": True},
)

aria2 = ariaAPI(ariaClient(host="http://localhost", port=6800, secret=""))

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)


def re_verify(paused, resumed, hash_id):
    paused = paused.strip()
    resumed = resumed.strip()
    if paused:
        paused = paused.split("|")
    if resumed:
        resumed = resumed.split("|")

    k = 0
    while True:
        res = qbittorrent_client.torrents_files(torrent_hash=hash_id)
        verify = True
        for i in res:
            if str(i.id) in paused and i.priority != 0:
                verify = False
                break
            if str(i.id) in resumed and i.priority == 0:
                verify = False
                break
        if verify:
            break
        LOGGER.info("Reverification Failed! Correcting stuff...")
        sleep(1)
        try:
            qbittorrent_client.torrents_file_priority(
                torrent_hash=hash_id, file_ids=paused, priority=0
            )
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification paused!")
        try:
            qbittorrent_client.torrents_file_priority(
                torrent_hash=hash_id, file_ids=resumed, priority=1
            )
        except NotFound404Error as e:
            raise NotFound404Error from e
        except Exception as e:
            LOGGER.error(f"{e} Errored in reverification resumed!")
        k += 1
        if k > 5:
            return False
    LOGGER.info(f"Verified! Hash: {hash_id}")
    return True


@app.route("/app/files")
def files():
    return render_template("page.html")


@app.route("/app/files/torrent", methods=["GET", "POST"])
def handle_torrent():
    if not (gid := request.args.get("gid")):
        return jsonify(
            {
                "files": [],
                "engine": "",
                "error": "GID is missing",
                "message": "GID not specified",
            }
        )

    if not (pin := request.args.get("pin")):
        return jsonify(
            {
                "files": [],
                "engine": "",
                "error": "Pin is missing",
                "message": "PIN not specified",
            }
        )

    code = ""
    for nbr in gid:
        if nbr.isdigit():
            code += str(nbr)
        if len(code) == 4:
            break
    if code != pin:
        return jsonify(
            {
                "files": [],
                "engine": "",
                "error": "Invalid pin",
                "message": "The PIN you entered is incorrect",
            }
        )
    if request.method == "POST":
        if not (mode := request.args.get("mode")):
            return jsonify(
                {
                    "files": [],
                    "engine": "",
                    "error": "Mode is not specified",
                    "message": "Mode is not specified",
                }
            )
        data = request.get_json(cache=False, force=True)
        if mode == "rename":
            if len(gid) > 20:
                handle_rename(gid, data)
                content = {
                    "files": [],
                    "engine": "",
                    "error": "",
                    "message": "Rename successfully.",
                }
            else:
                content = {
                    "files": [],
                    "engine": "",
                    "error": "Rename failed.",
                    "message": "Cannot rename aria2c torrent file",
                }
        else:
            selected_files, unselected_files = extract_file_ids(data)
            if len(gid) > 20:
                selected_files = "|".join(selected_files)
                unselected_files = "|".join(unselected_files)
                set_qbittorrent(gid, selected_files, unselected_files)
            else:
                selected_files = ",".join(selected_files)
                set_aria2(gid, selected_files)
            content = {
                "files": [],
                "engine": "",
                "error": "",
                "message": "Your selection has been submitted successfully.",
            }
    else:
        try:
            if len(gid) > 20:
                res = qbittorrent_client.torrents_files(torrent_hash=gid)
                content = make_tree(res, "qbittorrent")
            else:
                res = aria2.client.get_files(gid)
                fpath = f"{aria2.client.get_option(gid)['dir']}/"
                content = make_tree(res, "aria2", fpath)
        except Exception as e:
            LOGGER.error(str(e))
            content = {
                "files": [],
                "engine": "",
                "error": "Error getting files",
                "message": str(e),
            }
    return jsonify(content)


def handle_rename(gid, data):
    try:
        _type = data["type"]
        del data["type"]
        if _type == "file":
            qbittorrent_client.torrents_rename_file(torrent_hash=gid, **data)
        else:
            qbittorrent_client.torrents_rename_folder(torrent_hash=gid, **data)
    except NotFound404Error as e:
        raise NotFound404Error from e
    except Exception as e:
        LOGGER.error(f"{e} Errored in renaming")


def set_qbittorrent(gid, selected_files, unselected_files):
    try:
        qbittorrent_client.torrents_file_priority(
            torrent_hash=gid, file_ids=unselected_files, priority=0
        )
    except NotFound404Error as e:
        raise NotFound404Error from e
    except Exception as e:
        LOGGER.error(f"{e} Errored in paused")
    try:
        qbittorrent_client.torrents_file_priority(
            torrent_hash=gid, file_ids=selected_files, priority=1
        )
    except NotFound404Error as e:
        raise NotFound404Error from e
    except Exception as e:
        LOGGER.error(f"{e} Errored in resumed")
    sleep(1)
    if not re_verify(unselected_files, selected_files, gid):
        LOGGER.error(f"Verification Failed! Hash: {gid}")


def set_aria2(gid, selected_files):
    res = aria2.client.change_option(gid, {"select-file": selected_files})
    if res == "OK":
        LOGGER.info(f"Verified! Gid: {gid}")
    else:
        LOGGER.info(f"Verification Failed! Report! Gid: {gid}")


@app.route("/")
def homepage():
    return "<h1>See mirror-leech-telegram-bot <a href='https://www.github.com/anasty17/mirror-leech-telegram-bot'>@GitHub</a> By <a href='https://github.com/anasty17'>Anas</a></h1>"


@app.errorhandler(Exception)
def page_not_found(e):
    return (
        f"<h1>404: Task not found! Mostly wrong input. <br><br>Error: {e}</h2>",
        404,
    )


if __name__ == "__main__":
    app.run()
