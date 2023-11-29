from feedparser import parse as feedparse
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from asyncio import Lock, sleep
from datetime import datetime, timedelta
from time import time
from functools import partial
from aiohttp import ClientSession
from apscheduler.triggers.interval import IntervalTrigger
from re import split as re_split, findall
from io import BytesIO
from bs4 import BeautifulSoup as bs
import lxml
from traceback import format_exc


from bot import scheduler, rss_dict, LOGGER, DATABASE_URL, config_dict, bot
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    editMessage,
    sendRss,
    sendFile,
    deleteMessage,
    
)
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import new_thread
from bot.helper.ext_utils.exceptions import RssShutdownException
from bot.helper.ext_utils.help_messages import RSS_HELP_MESSAGE

rss_dict_lock = Lock()
handler_dict = {}

'''
yts https://yts.mx/rss/0/720p/action/5 -c l
nyasi https://sukebei.nyaa.si/?page=rss&c=2_0&f=2 -c ql -e
nj https://nextjav.com -c ql
ij https://ijavtorrent.com -c ql
oj https://onejav.com -c ql
nk https://nekopoi.care
ph-new https://www.pornhub.com/video?o=cm -c yl
ph-1 https://www.pornhub.com/model/broken-sluts -c yl
ph-2 https://www.pornhub.com/pornstar/eva-elfie -c yl
ph-3 https://www.pornhub.com/model/zxlecya -c yl
ph-4 https://www.pornhub.com/model/adult-sex -c yl
ph-5 https://www.pornhub.com/channels/av-taxi6 -c yl
ph-6 https://www.pornhub.com/model/hongkongdoll -c yl
ph-7 https://www.pornhub.com/channels/brazzers -c yl
ph-8 https://www.pornhub.com/pornstar/alex-adams -c yl
ph-9 https://www.pornhub.com/model/nadja-rey -c yl
ph-10 https://www.pornhub.com/model/pinay-porn-videos -c yl
'''

async def get_html(url):
    if is_ph_link(url):
        url += "/videos?&page=1"
    
    async with ClientSession(trust_env=True) as session:
        async with session.get(url) as res:
            return await res.text()


def is_ph_link(url):
    return url.startswith('https://www.pornhub.com')
    
def is_nj_link(url):
    return url.startswith("https://nextjav.com")

def is_nk_link(url):
    return url.startswith("https://nekopoi.care")

def is_oj_link(url):
    return url.startswith("https://onejav.com")

def is_ij_link(url):
    return url.startswith("https://ijavtorrent.com")

# PH-START
PH_EX = """PH-Ex:
<code>ph-1 https://www.pornhub.com/model/lis-evans -c yl
ph-2 https://www.pornhub.com/pornstar/angela-white -c yl
ph-3 https://www.pornhub.com/channels/mommys-boy -c yl</code>"""
async def ph_scraper(url):
    base_url = "https://www.pornhub.com"
    a = "/model/"
    b = "/pornstar/"
    c = "/channels/"
    #base_url + a/b/c + {username}/videos?&page={}"
    
    r = []
    l = []
    if not url:
        return r
    try:
        content = await get_html(url)
        html = bs(content, 'lxml')
        if a in url or b in url:
            
            for c in html.select('div.profileContentLeft')[0].findAll('div', attrs = {'class':'wrap'}):
                l.append(c)
        elif c in url:
            try:
                for c in html.select('div.widgetContainer')[0].findAll('div', attrs = {'class':'wrap flexibleHeight'}):
                    l.append(c)
                if len(l) == 0:
                    raise AttributeError
            except AttributeError:
                for c in html.select('div.widgetContainer')[1].findAll('div', attrs = {'class':'wrap flexibleHeight'}):
                    l.append(c)
        elif 'video?o=cm' in url:
            #newws
            for c in html.findAll('div', attrs = {'class':'wrap flexibleHeight'}):
                l.append(c)
        #else:
        #    r.append("Unsupported PH-LINK", "")
        
        if l:
            for v in l:
                #img_url = c.img['src']
                title = v.a['title'].replace(",","")
                link = base_url + v.a['href']
                r.append(f"{title},{link}")
    except Exception as e:
        LOGGER.error(f"{url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {url}')
    return r

"""
if __name__ == '__main__':
    print(ph_scraper("https://www.pornhub.com/model/lis-evans"))
    print()
    print(ph_scraper("https://www.pornhub.com/pornstar/angela-white"))
    print()
    print(ph_scraper("https://www.pornhub.com/channels/mommys-boy"))
    
"""

# NJ-START
NJ_TAG = "NJ-"
async def nj_scraper(last_feed=False):
    r = []
    base_url = "https://nextjav.com"
    try:
        content = await get_html(base_url)
        html = bs(content, 'lxml')
        for c in html.findAll('div', attrs = {'class':'portfolio_item status-publish format-standard has-post-thumbnail'}):
            title = c.h2.text
            link_page = base_url + c.a['href']
            
            new_content = await get_html(link_page)
            new_html = bs(new_content, 'lxml')
            link_dl = base_url + new_html.find('a', attrs = {'class':'button btn btn-danger btn-download'})['href']

            r.append(f"{title},{link_dl}")
            if last_feed:
                return r
    except Exception as e:
        LOGGER.error(f"{base_url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {base_url}')
    return r

# NK-START
async def nk_scraper(category='hentai', last_feed=False):
    #if category not in ['jav', 'hentai']:
        #return None

    url = "https://nekopoi.care/category/" + category
    r = []
    try:
        content = await get_html(url)
        html = bs(content, 'lxml')
        for x in html.select('div.result')[0].findAll('div', attrs = {'class' : 'top'}):
            img_url = x.img['src']
            title = x.h2.text
            link_eps = x.a['href']
    
            #result.append(title)
          
            eps_content = await get_html(link_eps)
            soup_eps = bs(eps_content, 'lxml')
            link_stream = '\n'.join(x.iframe['src'] for x in soup_eps.select(
                'div.show-stream')[0].findAll(
                'div', attrs = {'class' : 'openstream'}
                )
            )
    
            link_dl = '\n'.join("\n[{}]\n{}".format(
            findall(r'\[(.*?)]', l.find('div', attrs = {'class' : 'name'}).string)[-1], l.p)
            for l in soup_eps.select(
              'div.boxdownload')[0].findAll(
                'div', attrs = {'class' : 'liner'}
                )
            )#.replace('<p>', '').replace('</p>', '')
          
            caption = f"#nekopoi_{choice}\n{title}\n{link_stream}{link_dl}"
            #if len(caption) > 1024:
            if len(caption) > 4000:
                caption = f"#nekopoi_{choice}\n{title[:30]}\n{link_stream}\n\n<a href='{link_eps}'>See more</a>"
        
            r.append(f"{title},{caption}")
            if last_feed:
                return r
    except Exception as e:
        LOGGER.error(f"{url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {url}')
    return r

#OJ-START
async def one_jav_scraper(last_feed=False):
    base_url = "https://onejav.com"
    r = []
    try:
        content = await get_html(base_url + '/new')
        html = bs(content, 'lxml')
        #LOGGER.info(html)
        for c in html.findAll('div', attrs = {'class':'card mb-3'}):
            title = c.h5.a.text.strip().replace("\n","")
            link = base_url + c.find('a', class_='button is-primary is-fullwidth').get('href')
            r.append(f"{title},{link}")
            if last_feed:
                return r
    except Exception as e:
        LOGGER.error(f"{base_url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {base_url}')
    return r

#IJ-START
async def ijavtorrent_scraper(last_feed=False):
    base_url = "https://ijavtorrent.com"
    r = []
    try:
        content = await get_html(base_url + '/?sortby=lastupdated')
        html = bs(content, 'lxml')
        #LOGGER.info(html)
        for c in html.findAll('table', attrs = {'class':'table table-sm mt-2'}):
            #title = c.h5.a.text.strip().replace("\n","")
            link = base_url + c.find('a', class_='download-click-track').get('href')
            r.append(f"{link[-6:]},{link}")
            if last_feed:
                return r
    except Exception as e:
        LOGGER.error(f"{base_url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {base_url}')
    return r



# RSS-GLOBAL-START
async def rss_scraper(url):
    r = []
    try:
        content = await get_html(url)
        rss_d = feedparse(content)
        for c in rss_d.entries:
            title = c['title']
            try:
                link = c['links'][1]['href']
            except IndexError:
                link = c['link']

            r.append(f"{title},{link}")
    except Exception as e:
        LOGGER.error(f"{url} ERROR: {e}")
    LOGGER.info(f'Found {len(r)} from {url}')
    return r


async def rssMenu(event):
    user_id = event.from_user.id
    buttons = ButtonMaker()
    buttons.ibutton("Subscribe", f"rss sub {user_id}")
    buttons.ibutton("Subscriptions", f"rss list {user_id} 0")
    buttons.ibutton("Get Items", f"rss get {user_id}")
    buttons.ibutton("Edit", f"rss edit {user_id}")
    buttons.ibutton("Pause", f"rss pause {user_id}")
    buttons.ibutton("Resume", f"rss resume {user_id}")
    buttons.ibutton("Unsubscribe", f"rss unsubscribe {user_id}")
    if await CustomFilters.sudo("", event):
        #buttons.ibutton("Local Subs", f"rss local {user_id}")
        buttons.ibutton("All Subscriptions", f"rss listall {user_id} 0")
        buttons.ibutton("Pause All", f"rss allpause {user_id}")
        buttons.ibutton("Resume All", f"rss allresume {user_id}")
        buttons.ibutton("Unsubscribe All", f"rss allunsub {user_id}")
        buttons.ibutton("Delete User", f"rss deluser {user_id}")
        if scheduler.running:
            buttons.ibutton("Shutdown Rss", f"rss shutdown {user_id}")
        else:
            buttons.ibutton("Start Rss", f"rss start {user_id}")
    buttons.ibutton("Close", f"rss close {user_id}")
    button = buttons.build_menu(2)
    msg = f"Rss Menu | Users: {len(rss_dict)} | Running: {scheduler.running}"
    return msg, button

async def updateRssMenu(query):
    msg, button = None, None
    try:
        msg, button = await rssMenu(query)
        await editMessage(query.message, msg, button)
    except Exception:
        LOGGER.error(format_exc())

async def getRssMenu(_, message):
    msg, button = None, None
    try:
        msg, button = await rssMenu(message)
        await sendMessage(message, msg, button)
    except Exception:
        LOGGER.error(format_exc())

async def rssSub(client, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention
    msg = ''
    items = message.text.split('\n')
    for index, item in enumerate(items, start=1):
        args = item.split()
        if len(args) < 2:
            await sendMessage(message, f'{item}. Wrong Input format. Read help message before adding new subcription!')
            continue
        title = args[0].strip()
        if (user_feeds := rss_dict.get(user_id, False)) and title in user_feeds:
            await sendMessage(message, f"This title {title} already subscribed! Choose another title!")
            continue
        feed_link = args[1].strip()
        if feed_link.startswith(('-inf', '-exf', '-c')):
            await sendMessage(message, f'Wrong input in line {index}! Re-add only the mentioned line correctly! Read the example!')
            continue
        
        inf = None
        exf = None
        cmd = None
        inf_lists = []
        exf_lists = []
        if len(args) > 2:
            arg = item.split(' -c ', 1)
            cmd = re_split(' -inf | -exf ',
                           arg[1])[0].strip() if len(arg) > 1 else None
            arg = item.split(' -inf ', 1)
            inf = re_split(
                ' -c | -exf ', arg[1])[0].strip() if len(arg) > 1 else None
            arg = item.split(' -exf ', 1)
            exf = re_split(
                ' -c | -inf ', arg[1])[0].strip() if len(arg) > 1 else None
            if inf is not None:
                filters_list = inf.split('|')
                for x in filters_list:
                    y = x.split(' or ')
                    inf_lists.append(y)
            if exf is not None:
                filters_list = exf.split('|')
                for x in filters_list:
                    y = x.split(' or ')
                    exf_lists.append(y)
                    
        try:
            if is_ph_link(feed_link):
                # PH-START
                r = await ph_scraper(feed_link)
            elif is_nj_link(feed_link):
                # NJ-START
                r = await nj_scraper(last_feed=True)
            elif is_nk_link(feed_link):
                #NK-START
                r = await nk_scraper(last_feed=True)
            elif is_oj_link(feed_link):
                #OJ-START
                r = await one_jav_scraper(last_feed=True)
            elif is_ij_link(feed_link):
                #IJ-START
                r = await ijavtorrent_scraper(last_feed=True)
            else:
                # RSS-GLOBAL-START
                r = await rss_scraper(feed_link)
            
            if len(r) > 0:
                last_title, last_link = r[0].split(",")
            else:
                raise Exception('🐒')

            msg += f"\n{index}."
            msg += f"\n<b>TAG: </b><code>{title}</code>"
            msg += f"\n<b>LINK: </b><code>{feed_link}</code>"
            msg += f"\n<b>CMD: </b><code>{cmd}</code>"
            msg += f"\n<b>INF: </b><code>{inf}</code>"
            msg += f"\n<b>EXF: </b><code>{exf}</code>"
            msg += f"\n<b>L. TITLE: </b><code>{last_title}</code>"
            msg += f"\n<b>L. LINK: </b><code>{last_link}</code>"

            async with rss_dict_lock:
                if rss_dict.get(user_id, False):
                    rss_dict[user_id][title] = {'link': feed_link, 'last_feed': last_link, 'last_title': last_title,
                                                'inf': inf_lists, 'exf': exf_lists, 'paused': False, 'command': cmd, 'tag': tag}
                else:
                    rss_dict[user_id] = {title: {'link': feed_link, 'last_feed': last_link, 'last_title': last_title,
                                                'inf': inf_lists, 'exf': exf_lists, 'paused': False, 'command': cmd, 'tag': tag}}
            LOGGER.info(
                f"Rss Feed Added: id: {user_id} - title: {title} - link: {feed_link} - c: {cmd} - inf: {inf} - exf: {exf}")
        except Exception as e:
            await updateRssMenu(pre_event)
            err_msg = f"<code>{feed_link}</code> doesn't seem to be a RSS feed or it's region-blocked!, \n\nERROR: {e}"
            await sendMessage(message, err_msg)
    if DATABASE_URL:
        await DbManger().rss_update(user_id)
    if msg:
        await sendMessage(message, msg)
    await updateRssMenu(pre_event)
    is_sudo = await CustomFilters.sudo(client, message)
    if scheduler.state == 2:
        scheduler.resume()
    elif is_sudo and not scheduler.running:
        addJob(config_dict['RSS_DELAY'])
        scheduler.start()
    await deleteMessage(message)

async def getUserId(title):
    async with rss_dict_lock:
        return next(
            (
                (True, user_id)
                for user_id, feed in list(rss_dict.items())
                if feed["title"] == title
            ),
            (False, False),
        )


async def rssUpdate(_, message, pre_event, state):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    titles = message.text.split()
    is_sudo = await CustomFilters.sudo("", message)
    updated = []
    for title in titles:
        title = title.strip()
        if not (res := rss_dict[user_id].get(title, False)):
            if is_sudo:
                res, user_id = await getUserId(title)
            if not res:
                user_id = message.from_user.id
                await sendMessage(message, f"{title} not found!")
                continue
        istate = rss_dict[user_id][title].get("paused", False)
        if istate and state == "pause" or not istate and state == "resume":
            await sendMessage(message, f"{title} already {state}d!")
            continue
        async with rss_dict_lock:
            updated.append(title)
            if state == "unsubscribe":
                del rss_dict[user_id][title]
            elif state == "pause":
                rss_dict[user_id][title]["paused"] = True
            elif state == "resume":
                rss_dict[user_id][title]["paused"] = False
        if state == "resume":
            if scheduler.state == 2:
                scheduler.resume()
            elif is_sudo and not scheduler.running:
                addJob(config_dict["RSS_DELAY"])
                scheduler.start()
        if is_sudo and DATABASE_URL and user_id != message.from_user.id:
            await DbManger().rss_update(user_id)
        if not rss_dict[user_id]:
            async with rss_dict_lock:
                del rss_dict[user_id]
            if DATABASE_URL:
                await DbManger().rss_delete(user_id)
                if not rss_dict:
                    await DbManger().trunc_table("rss")
    LOGGER.info(f"Rss link with Title(s): {updated} has been {state}d!")
    await sendMessage(
        message, f"Rss links with Title(s): <code>{updated}</code> has been {state}d!"
    )
    if DATABASE_URL and rss_dict.get(user_id):
        await DbManger().rss_update(user_id)
    await updateRssMenu(pre_event)


async def rssList(query, start, all_users=False):
    user_id = query.from_user.id
    buttons = ButtonMaker()
    if all_users:
        list_feed = f"<b>All subscriptions | Page: {int(start/5)} </b>"
        async with rss_dict_lock:
            keysCount = sum(len(v.keys()) for v in list(rss_dict.values()))
            index = 0
            for titles in list(rss_dict.values()):
                for index, (title, data) in enumerate(
                    list(titles.items())[start : 5 + start]
                ):
                    list_feed += f"\n\n<b>Title:</b> <code>{title}</code>\n"
                    list_feed += f"<b>Feed Url:</b> <code>{data['link']}</code>\n"
                    list_feed += f"<b>Command:</b> <code>{data['command']}</code>\n"
                    list_feed += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
                    list_feed += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
                    list_feed += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
                    list_feed += f"<b>User:</b> {data['tag'].lstrip('@')}"
                    index += 1
                    if index == 5:
                        break
    else:
        list_feed = f"<b>Your subscriptions | Page: {int(start/5)} </b>"
        async with rss_dict_lock:
            keysCount = len(rss_dict.get(user_id, {}).keys())
            for title, data in list(rss_dict[user_id].items())[start : 5 + start]:
                list_feed += f"\n\n<b>Title:</b> <code>{title}</code>\n<b>Feed Url: </b><code>{data['link']}</code>\n"
                list_feed += f"<b>Command:</b> <code>{data['command']}</code>\n"
                list_feed += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
                list_feed += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
                list_feed += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
    buttons.ibutton("Back", f"rss back {user_id}")
    buttons.ibutton("Close", f"rss close {user_id}")
    if keysCount > 5:
        for x in range(0, keysCount, 5):
            buttons.ibutton(f"{int(x/5)}", f"rss list {user_id} {x}", position="footer")
    button = buttons.build_menu(2)
    if query.message.text.html == list_feed:
        return
    await editMessage(query.message, list_feed, button)

async def rssGet(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    args = message.text.split()
    if len(args) < 2:
        await sendMessage(
            message,
            f"{args}. Wrong Input format. You should add number of the items you want to get. Read help message before adding new subcription!",
        )
        await updateRssMenu(pre_event)
        return
    try:
        title = args[0]
        count = int(args[1])
        data = rss_dict[user_id].get(title, False)
        if data and count > 0:
            try:
                msg = await sendMessage(
                    message, f"Getting the last <b>{count}</b> item(s) from {title}"
                )
                async with ClientSession(trust_env=True) as session:
                    async with session.get(data["link"]) as res:
                        html = await res.text()
                rss_d = feedparse(html)
                item_info = ""
                for item_num in range(count):
                    try:
                        link = rss_d.entries[item_num]["links"][1]["href"]
                    except IndexError:
                        link = rss_d.entries[item_num]["link"]
                    item_info += f"<b>Name: </b><code>{rss_d.entries[item_num]['title'].replace('>', '').replace('<', '')}</code>\n"
                    item_info += f"<b>Link: </b><code>{link}</code>\n\n"
                item_info_ecd = item_info.encode()
                if len(item_info_ecd) > 4000:
                    with BytesIO(item_info_ecd) as out_file:
                        out_file.name = f"rssGet {title} items_no. {count}.txt"
                        await sendFile(message, out_file)
                    await deleteMessage(msg)
                else:
                    await editMessage(msg, item_info)
            except IndexError as e:
                LOGGER.error(str(e))
                await editMessage(
                    msg, "Parse depth exceeded. Try again with a lower value."
                )
            except Exception as e:
                LOGGER.error(str(e))
                await editMessage(msg, str(e))
    except Exception as e:
        LOGGER.error(str(e))
        await sendMessage(message, f"Enter a valid value!. {e}")
    await updateRssMenu(pre_event)


async def rssEdit(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    items = message.text.split("\n")
    for item in items:
        args = item.split()
        title = args[0].strip()
        if len(args) < 2:
            await sendMessage(
                message,
                f"{item}. Wrong Input format. Read help message before editing!",
            )
            continue
        elif not rss_dict[user_id].get(title, False):
            await sendMessage(message, "Enter a valid title. Title not found!")
            continue
        inf_lists = []
        exf_lists = []
        arg = item.split(" -c ", 1)
        cmd = re_split(" -inf | -exf ", arg[1])[0].strip() if len(arg) > 1 else None
        arg = item.split(" -inf ", 1)
        inf = re_split(" -c | -exf ", arg[1])[0].strip() if len(arg) > 1 else None
        arg = item.split(" -exf ", 1)
        exf = re_split(" -c | -inf ", arg[1])[0].strip() if len(arg) > 1 else None
        async with rss_dict_lock:
            if cmd is not None:
                if cmd.lower() == "none":
                    cmd = None
                rss_dict[user_id][title]["command"] = cmd
            if inf is not None:
                if inf.lower() != "none":
                    filters_list = inf.split("|")
                    for x in filters_list:
                        y = x.split(" or ")
                        inf_lists.append(y)
                rss_dict[user_id][title]["inf"] = inf_lists
            if exf is not None:
                if exf.lower() != "none":
                    filters_list = exf.split("|")
                    for x in filters_list:
                        y = x.split(" or ")
                        exf_lists.append(y)
                rss_dict[user_id][title]["exf"] = exf_lists
    if DATABASE_URL:
        await DbManger().rss_update(user_id)
    await updateRssMenu(pre_event)


async def rssDelete(_, message, pre_event):
    handler_dict[message.from_user.id] = False
    users = message.text.split()
    for user in users:
        user = int(user)
        async with rss_dict_lock:
            del rss_dict[user]
        if DATABASE_URL:
            await DbManger().rss_delete(user)
    await updateRssMenu(pre_event)


async def event_handler(client, query, pfunc):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        user = event.from_user or event.sender_chat
        return bool(
            user.id == user_id and event.chat.id == query.message.chat.id and event.text
        )

    handler = client.add_handler(MessageHandler(pfunc, create(event_filter)), group=-1)
    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await updateRssMenu(query)
    client.remove_handler(*handler)


@new_thread
async def rssListener(client, query):
    user_id = query.from_user.id
    message = query.message
    data = query.data.split()
    if int(data[2]) != user_id and not await CustomFilters.sudo("", query):
        await query.answer(
            text="You don't have permission to use these buttons!", show_alert=True
        )
    elif data[1] == "close":
        await query.answer()
        handler_dict[user_id] = False
        await deleteMessage(message.reply_to_message)
        await deleteMessage(message)
    elif data[1] == "back":
        await query.answer()
        handler_dict[user_id] = False
        await updateRssMenu(query)
    elif data[1] == "sub":
        await query.answer()
        handler_dict[user_id] = False
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"rss back {user_id}")
        buttons.ibutton("Close", f"rss close {user_id}")
        button = buttons.build_menu(2)
        await editMessage(message, RSS_HELP_MESSAGE, button)
        pfunc = partial(rssSub, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[1] == "list":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rssList(query, start)
    elif data[1] == "get":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await editMessage(
                message,
                "Send one title with value separated by space get last X items.\nTitle Value\nTimeout: 60 sec.",
                button,
            )
            pfunc = partial(rssGet, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] in ["unsubscribe", "pause", "resume"]:
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            if data[1] == "pause":
                buttons.ibutton("Pause AllMyFeeds", f"rss uallpause {user_id}")
            elif data[1] == "resume":
                buttons.ibutton("Resume AllMyFeeds", f"rss uallresume {user_id}")
            elif data[1] == "unsubscribe":
                buttons.ibutton("Unsub AllMyFeeds", f"rss uallunsub {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await editMessage(
                message,
                f"Send one or more rss titles separated by space to {data[1]}.\nTimeout: 60 sec.",
                button,
            )
            pfunc = partial(rssUpdate, pre_event=query, state=data[1])
            await event_handler(client, query, pfunc)
    elif data[1] == "edit":
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = """Send one or more rss titles with new filters or command separated by new line.
Examples:
Title1 -c mirror -up remote:path/subdir -exf none -inf 1080 or 720 opt: up: remote:path/subdir
Title2 -c none -inf none -opt none
Title3 -c mirror -rcf xxx -up xxx -z pswd
Note: Only what you provide will be edited, the rest will be the same like example 2: exf will stay same as it is.
Timeout: 60 sec. Argument -c for command and options
            """
            await editMessage(message, msg, button)
            pfunc = partial(rssEdit, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1].startswith("uall"):
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith("unsub"):
            async with rss_dict_lock:
                del rss_dict[int(data[2])]
            if DATABASE_URL:
                await DbManger().rss_delete(int(data[2]))
            await updateRssMenu(query)
        elif data[1].endswith("pause"):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]["paused"] = True
            if DATABASE_URL:
                await DbManger().rss_update(int(data[2]))
        elif data[1].endswith("resume"):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]["paused"] = False
            if scheduler.state == 2:
                scheduler.resume()
            if DATABASE_URL:
                await DbManger().rss_update(int(data[2]))
        await updateRssMenu(query)
    elif data[1].startswith("all"):
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith("unsub"):
            async with rss_dict_lock:
                rss_dict.clear()
            if DATABASE_URL:
                await DbManger().trunc_table("rss")
            await updateRssMenu(query)
        elif data[1].endswith("pause"):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]["paused"] = True
            if scheduler.running:
                scheduler.pause()
            if DATABASE_URL:
                await DbManger().rss_update_all()
        elif data[1].endswith("resume"):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]["paused"] = False
            if scheduler.state == 2:
                scheduler.resume()
            elif not scheduler.running:
                addJob(config_dict["RSS_DELAY"])
                scheduler.start()
            if DATABASE_URL:
                await DbManger().rss_update_all()
    elif data[1] == "deluser":
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = "Send one or more user_id separated by space to delete their resources.\nTimeout: 60 sec."
            await editMessage(message, msg, button)
            pfunc = partial(rssDelete, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] == "listall":
        if not rss_dict:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rssList(query, start, all_users=True)
    elif data[1] == "shutdown":
        if scheduler.running:
            await query.answer()
            scheduler.shutdown(wait=False)
            await sleep(0.5)
            await updateRssMenu(query)
        else:
            await query.answer(text="Already Stopped!", show_alert=True)
    elif data[1] == "start":
        if not scheduler.running:
            await query.answer()
            addJob(config_dict["RSS_DELAY"])
            scheduler.start()
            await updateRssMenu(query)
        else:
            await query.answer(text="Already Running!", show_alert=True)


async def rssMonitor():
    if not config_dict['RSS_CHAT']:
        LOGGER.warning('RSS_CHAT not added! Shutting down rss scheduler...')
        scheduler.shutdown(wait=False)
        return
    if not rss_dict:
        scheduler.pause()
        return
    all_paused = True
    for user, items in list(rss_dict.items()):
        for title, data in list(items.items()):
            try:
                if data['paused']:
                    continue
                if is_ph_link(data['link']):
                    # PH-START
                    r = await ph_scraper(data['link'])
                    last_title, last_link = r[0].split(",")
                elif is_nj_link(data['link']):
                    # NJ-START
                    r = await nj_scraper()
                    last_title, last_link = r[0].split(",")
                elif is_nk_link(data['link']):
                    #NK-START
                    r = await nk_scraper()
                    last_title, last_link = r[0].split(",")
                elif is_oj_link(data['link']):
                    #OJ-START
                    r = await one_jav_scraper()
                    last_title, last_link = r[0].split(",")
                elif is_ij_link(data['link']):
                    #IJ-START
                    r = await ijavtorrent_scraper()
                    last_title, last_link = r[0].split(",")
                    
                else:
                    # RSS-GLOBAL-START
                    r = await rss_scraper(data['link'])
                    last_title, last_link = r[0].split(",")
                    
                all_paused = False
                if data['last_feed'] == last_link or data['last_title'] == last_title:
                    continue
                feed_count = 0
                while True:
                    try:
                        await sleep(config_dict['SEND_MSG_DELAY'])
                    except:
                        raise RssShutdownException('Rss Monitor Stopped!')
                    try:
                        item_title, url = r[feed_count].split(",")
                        #LOGGER.info(x)
                        #item_title, url = x.split(",")
                        if data['last_title'] == item_title or data['last_feed'] == url:
                            break
                    except IndexError:
                        LOGGER.warning(
                            f"Reached Max index no. {feed_count} for this feed: {title}. Maybe you need to use less RSS_DELAY to not miss some torrents")
                        break
                    parse = True
                    for flist in data['inf']:
                        if all(x not in item_title.lower() for x in flist):
                            parse = False
                            feed_count += 1
                            break
                    for flist in data['exf']:
                        if any(x in item_title.lower() for x in flist):
                            parse = False
                            feed_count += 1
                            break
                    if not parse:
                        continue
                    if command := data['command']:
                        cmd = command.split(maxsplit=1)
                        cmd.insert(1, url)
                        feed_msg = " ".join(cmd)
                        if not feed_msg.startswith('/'):
                            feed_msg = f"/{feed_msg}"
                    else:
                        feed_msg = f"<b>Name: </b><code>{item_title.replace('>', '').replace('<', '')}</code>\n\n"
                        feed_msg += f"<b>Link: </b><code>{url}</code>"
                    feed_msg += f"\n<b>Tag: </b><code>{data['tag']}</code> <code>{user}</code>"
                    await sendRss(feed_msg)
                    feed_count += 1
                
                async with rss_dict_lock:
                    if user not in rss_dict or not rss_dict[user].get(title, False):
                        continue
                    rss_dict[user][title].update(
                        {'last_feed': last_link, 'last_title': last_title})
                await DbManger().rss_update(user)
                LOGGER.info(f"Updated. Feed Name: {title} => Last Link: {last_link}")
            except RssShutdownException:
                LOGGER.error(format_exc())
                scheduler.shutdown(wait=False)
                break
            except Exception as e:
                LOGGER.error(
                    f"{e} - Feed Name: {title} - Feed Link: {data['link']}")
                #LOGGER.error(format_exc())
                continue
    
    if scheduler.running and all_paused:
        scheduler.pause()



def addJob(delay):
    scheduler.add_job(
        rssMonitor,
        trigger=IntervalTrigger(seconds=delay),
        id="0",
        name="RSS",
        misfire_grace_time=15,
        max_instances=1,
        next_run_time=datetime.now() + timedelta(seconds=20),
        replace_existing=True,
    )


addJob(config_dict["RSS_DELAY"])
scheduler.start()
bot.add_handler(
    MessageHandler(
        getRssMenu, filters=command(BotCommands.RssCommand) & CustomFilters.authorized
    )
)
bot.add_handler(CallbackQueryHandler(rssListener, filters=regex("^rss")))