# -*- coding: utf-8 -*-
# (c) YashDK [yash-dk@github]
# Redesigned By - @bipuldey19 (https://github.com/SlamDevs/slam-mirrorbot/commit/1e572f4fa3625ecceb953ce6d3e7cf7334a4d542#diff-c3d91f56f4c5d8b5af3d856d15a76bd5f00aa38d712691b91501734940761bdd)

import logging
import qbittorrentapi as qba
import asyncio
from aiohttp import web
import nodes

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    handlers=[logging.FileHandler('log.txt'), logging.StreamHandler()],
                    level=logging.INFO)

LOGGER = logging.getLogger(__name__)

routes = web.RouteTableDef()

rawowners = "<h1 style='text-align: center'>See mirror-leech-telegram-bot <a href='https://www.github.com/anasty17/mirror-leech-telegram-bot'>@GitHub</a> By <a href='https://github.com/anasty17'>Anas</a></h1>"

pin_entry = '''
    <section>
      <form action="{form_url}">
        <div>
          <label for="pin_code">Pin Code :</label>
          <input
            type="text"
            name="pin_code"
            placeholder="Enter the code that you have got from Telegram to access the Torrent"
          />
        </div>
        <button type="submit" class="btn btn-primary">Submit</button>
      </form>
          <span
            >* Dont mess around. Your download will get messed up.</
          >
    </section>
'''
files_list = '''
    <section>
        <h2 class="intro">Select the files you want to download</h2>
        <input type="hidden" name="URL" id="URL" value="{form_url}" />
        <form id="SelectedFilesForm" name="SelectedFilesForm">
            <!-- {My_content} -->
            <input type="submit" name="Submit" />
        </form>
    </section>
'''

with open('bot/wserver/index.html', "r") as codepage:
    rawindexpage = codepage.read()
    codepage.close()
with open('bot/wserver/style1.css', "r") as rawstlye1:
    stlye1 = rawstlye1.read()
    rawstlye1.close()
with open('bot/wserver/style2.css', "r") as rawstlye2:
    stlye2 = rawstlye2.read()
    rawstlye2.close()


@routes.get('/app/files/{hash_id}')
async def list_torrent_contents(request):
    torr = request.match_info["hash_id"]
    gets = request.query

    if "pin_code" not in gets.keys():
        rend_page = rawindexpage.replace("/* style1 */", stlye1).replace("<!-- pin_entry -->", pin_entry) \
            .replace("{form_url}", f"/app/files/{torr}")
        return web.Response(text=rend_page, content_type='text/html')

    client = qba.Client(host="localhost", port="8090")
    try:
        res = client.torrents_files(torrent_hash=torr)
    except qba.NotFound404Error:
        raise web.HTTPNotFound()
    count = 0
    passw = ""
    for n in str(torr):
        if n.isdigit():
            passw += str(n)
            count += 1
        if count == 4:
            break
    if isinstance(passw, bool):
        raise web.HTTPNotFound()
    pincode = passw
    if gets["pin_code"] != pincode:
        wrong_pin = rawindexpage.replace("/* style1 */", stlye1).replace(
            "<!-- Print -->", "<h1 style='text-align: center;color: red;'>Incorrect pin code</h1>")
        return web.Response(text=wrong_pin, content_type='text/html')

    par = nodes.make_tree(res)

    cont = ["", 0]
    nodes.create_list(par, cont)
    rend_page = rawindexpage.replace("/* style2 */", stlye2).replace("<!-- files_list -->", files_list) \
        .replace("{form_url}", f"/app/files/{torr}?pin_code={pincode}").replace("<!-- {My_content} -->", cont[0])
    client.auth_log_out()
    return web.Response(text=rend_page, content_type='text/html')


async def re_verfiy(paused, resumed, client, torr):

    paused = paused.strip()
    resumed = resumed.strip()
    if paused:
        paused = paused.split("|")
    if resumed:
        resumed = resumed.split("|")
    k = 0
    while True:

        res = client.torrents_files(torrent_hash=torr)
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
        LOGGER.info("Reverification Failed: correcting stuff...")
        client.auth_log_out()
        await asyncio.sleep(1)
        client = qba.Client(host="localhost", port="8090")
        try:
            client.torrents_file_priority(torrent_hash=torr, file_ids=paused, priority=0)
        except:
            LOGGER.error("Errored in reverification paused")
        try:
            client.torrents_file_priority(torrent_hash=torr, file_ids=resumed, priority=1)
        except:
            LOGGER.error("Errored in reverification resumed")
        k += 1
        if k > 5:
            return False
    client.auth_log_out()
    LOGGER.info("Verified")
    return True


@routes.post('/app/files/{hash_id}')
async def set_priority(request):

    torr = request.match_info["hash_id"]
    client = qba.Client(host="localhost", port="8090")

    data = await request.post()
    resume = ""
    pause = ""
    data = dict(data)

    for i, value in data.items():
        if i.find("filenode") != -1:
            node_no = i.split("_")[-1]

            if value == "on":
                resume += f"{node_no}|"
            else:
                pause += f"{node_no}|"

    pause = pause.strip("|")
    resume = resume.strip("|")

    try:
        client.torrents_file_priority(torrent_hash=torr, file_ids=pause, priority=0)
    except qba.NotFound404Error:
        raise web.HTTPNotFound()
    except:
        LOGGER.error("Errored in paused")

    try:
        client.torrents_file_priority(torrent_hash=torr, file_ids=resume, priority=1)
    except qba.NotFound404Error:
        raise web.HTTPNotFound()
    except:
        LOGGER.error("Errored in resumed")

    await asyncio.sleep(2)
    if not await re_verfiy(pause, resume, client, torr):
        LOGGER.error("Verification Failed")
    return await list_torrent_contents(request)


@routes.get('/')
async def homepage(request):
    owners = rawindexpage.replace(
        "/* style1 */", stlye1).replace("<!-- Print -->", rawowners)
    return web.Response(text=owners, content_type="text/html")


async def e404_middleware(app, handler):

    async def middleware_handler(request):

        try:
            response = await handler(request)
            if response.status == 404:
                error404 = rawindexpage.replace("/* style1 */", stlye1) \
                    .replace("<!-- Print -->", "<h1 style='text-align: center;color: red;'>404: Page not found</h1><br><h3 style='text-align: center'>mirror-leech-telegram-bot</h3>")
                return web.Response(text=error404, content_type="text/html")
            return response
        except web.HTTPException as ex:
            if ex.status == 404:
                error404 = rawindexpage.replace("/* style1 */", stlye1) \
                    .replace("<!-- Print -->", "<h1 style='text-align: center;color: red;'>404: Page not found</h1><br><h3 style='text-align: center'>mirror-leech-telegram-bot</h3>")
                return web.Response(text=error404, content_type="text/html")
            raise
    return middleware_handler


async def start_server():

    app = web.Application(middlewares=[e404_middleware])
    app.add_routes(routes)
    return app


async def start_server_async(port=80):

    app = web.Application(middlewares=[e404_middleware])
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", port).start()
