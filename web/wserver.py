from uvloop import install

install()
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from logging import getLogger, FileHandler, StreamHandler, INFO, basicConfig, WARNING
from asyncio import sleep
from sabnzbdapi import SabnzbdClient
from aioaria2 import Aria2HttpClient
from aioqbt.client import create_client
from aiohttp.client_exceptions import ClientError

from web.nodes import extract_file_ids, make_tree

getLogger("httpx").setLevel(WARNING)
getLogger("aiohttp").setLevel(WARNING)

aria2 = None
qbittorrent = None
sabnzbd_client = SabnzbdClient(
    host="http://localhost",
    api_key="mltb",
    port="8070",
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global aria2, qbittorrent
    aria2 = Aria2HttpClient("http://localhost:6800/jsonrpc")
    qbittorrent = await create_client("http://localhost:8090/api/v2/")
    yield
    await aria2.close()
    await qbittorrent.close()


app = FastAPI(lifespan=lifespan)


templates = Jinja2Templates(directory="web/templates/")

basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[FileHandler("log.txt"), StreamHandler()],
    level=INFO,
)

LOGGER = getLogger(__name__)


async def re_verify(paused, resumed, hash_id):
    k = 0
    while True:
        res = await qbittorrent.torrents.files(hash_id)
        verify = True
        for i in res:
            if i.index in paused and i.priority != 0:
                verify = False
                break
            if i.index in resumed and i.priority == 0:
                verify = False
                break
        if verify:
            break
        LOGGER.info("Reverification Failed! Correcting stuff...")
        await sleep(0.5)
        if paused:
            try:
                await qbittorrent.torrents.file_prio(
                    hash=hash_id, id=paused, priority=0
                )
            except (ClientError, TimeoutError, Exception) as e:
                LOGGER.error(f"{e} Errored in reverification paused!")
        if resumed:
            try:
                await qbittorrent.torrents.file_prio(
                    hash=hash_id, id=resumed, priority=1
                )
            except (ClientError, TimeoutError, Exception) as e:
                LOGGER.error(f"{e} Errored in reverification resumed!")
        k += 1
        if k > 5:
            return False
    LOGGER.info(f"Verified! Hash: {hash_id}")
    return True


@app.get("/app/files", response_class=HTMLResponse)
async def files(request: Request):
    return templates.TemplateResponse("page.html", {"request": request})


@app.api_route(
    "/app/files/torrent", methods=["GET", "POST"], response_class=HTMLResponse
)
async def handle_torrent(request: Request):
    params = request.query_params

    if not (gid := params.get("gid")):
        return JSONResponse(
            {
                "files": [],
                "engine": "",
                "error": "GID is missing",
                "message": "GID not specified",
            }
        )

    if not (pin := params.get("pin")):
        return JSONResponse(
            {
                "files": [],
                "engine": "",
                "error": "Pin is missing",
                "message": "PIN not specified",
            }
        )

    code = "".join([nbr for nbr in gid if nbr.isdigit()][:4])
    if code != pin:
        return JSONResponse(
            {
                "files": [],
                "engine": "",
                "error": "Invalid pin",
                "message": "The PIN you entered is incorrect",
            }
        )

    if request.method == "POST":
        if not (mode := params.get("mode")):
            return JSONResponse(
                {
                    "files": [],
                    "engine": "",
                    "error": "Mode is not specified",
                    "message": "Mode is not specified",
                }
            )
        data = await request.json()
        if mode == "rename":
            if len(gid) > 20:
                await handle_rename(gid, data)
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
            if gid.startswith("SABnzbd_nzo"):
                await set_sabnzbd(gid, unselected_files)
            elif len(gid) > 20:
                await set_qbittorrent(gid, selected_files, unselected_files)
            else:
                selected_files = ",".join(selected_files)
                await set_aria2(gid, selected_files)
            content = {
                "files": [],
                "engine": "",
                "error": "",
                "message": "Your selection has been submitted successfully.",
            }
    else:
        try:
            if gid.startswith("SABnzbd_nzo"):
                res = await sabnzbd_client.get_files(gid)
                content = make_tree(res, "sabnzbd")
            elif len(gid) > 20:
                res = await qbittorrent.torrents.files(gid)
                content = make_tree(res, "qbittorrent")
            else:
                res = await aria2.getFiles(gid)
                op = await aria2.getOption(gid)
                fpath = f"{op['dir']}/"
                content = make_tree(res, "aria2", fpath)
        except (ClientError, TimeoutError, Exception) as e:
            LOGGER.error(str(e))
            content = {
                "files": [],
                "engine": "",
                "error": "Error getting files",
                "message": str(e),
            }
    return JSONResponse(content)


async def handle_rename(gid, data):
    try:
        _type = data["type"]
        del data["type"]
        if _type == "file":
            await qbittorrent.torrents.rename_file(hash=gid, **data)
        else:
            await qbittorrent.torrents.rename_folder(hash=gid, **data)
    except (ClientError, TimeoutError, Exception) as e:
        LOGGER.error(f"{e} Errored in renaming")


async def set_sabnzbd(gid, unselected_files):
    await sabnzbd_client.remove_file(gid, unselected_files)
    LOGGER.info(f"Verified! nzo_id: {gid}")


async def set_qbittorrent(gid, selected_files, unselected_files):
    if unselected_files:
        try:
            await qbittorrent.torrents.file_prio(
                hash=gid, id=unselected_files, priority=0
            )
        except (ClientError, TimeoutError, Exception) as e:
            LOGGER.error(f"{e} Errored in paused")
    if selected_files:
        try:
            await qbittorrent.torrents.file_prio(
                hash=gid, id=selected_files, priority=1
            )
        except (ClientError, TimeoutError, Exception) as e:
            LOGGER.error(f"{e} Errored in resumed")
    await sleep(0.5)
    if not await re_verify(unselected_files, selected_files, gid):
        LOGGER.error(f"Verification Failed! Hash: {gid}")


async def set_aria2(gid, selected_files):
    res = await aria2.changeOption(gid, {"select-file": selected_files})
    if res == "OK":
        LOGGER.info(f"Verified! Gid: {gid}")
    else:
        LOGGER.info(f"Verification Failed! Report! Gid: {gid}")


@app.get("/", response_class=HTMLResponse)
async def homepage():
    return (
        "<h1>See mirror-leech-telegram-bot "
        "<a href='https://www.github.com/anasty17/mirror-leech-telegram-bot'>@GitHub</a> "
        "By <a href='https://github.com/anasty17'>Anas</a></h1>"
    )


@app.exception_handler(Exception)
async def page_not_found(_, exc):
    return HTMLResponse(
        f"<h1>404: Task not found! Mostly wrong input. <br><br>Error: {exc}</h1>",
        status_code=404,
    )
