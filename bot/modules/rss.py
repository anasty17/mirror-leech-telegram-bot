#!/usr/bin/env python3
from feedparser import parse as feedparse
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from asyncio import Lock, sleep
from datetime import datetime, timedelta
from time import time
from functools import partial
from aiohttp import ClientSession
from apscheduler.triggers.interval import IntervalTrigger
from re import split as re_split
from io import BytesIO

from bot import scheduler, rss_dict, LOGGER, DATABASE_URL, config_dict, bot
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, sendRss, sendFile
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import new_thread
from bot.helper.ext_utils.exceptions import RssShutdownException
from bot.helper.ext_utils.help_messages import RSS_HELP_MESSAGE

rss_dict_lock = Lock()
handler_dict = {}


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
    if await CustomFilters.sudo('', event):
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
    msg = f'Rss Menu | Users: {len(rss_dict)} | Running: {scheduler.running}'
    return msg, button


async def updateRssMenu(query):
    msg, button = await rssMenu(query)
    await editMessage(query.message, msg, button)


async def getRssMenu(client, message):
    msg, button = await rssMenu(message)
    await sendMessage(message, msg, button)


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
        else:
            inf = None
            exf = None
            cmd = None
        try:
            async with ClientSession(trust_env=True) as session:
                async with session.get(feed_link) as res:
                    html = await res.text()
            rss_d = feedparse(html)
            last_title = rss_d.entries[0]['title']
            msg += "<b>Subscribed!</b>"
            msg += f"\n<b>Title: </b><code>{title}</code>\n<b>Feed Url: </b>{feed_link}"
            msg += f"\n<b>latest record for </b>{rss_d.feed.title}:"
            msg += f"\nName: <code>{last_title.replace('>', '').replace('<', '')}</code>"
            try:
                last_link = rss_d.entries[0]['links'][1]['href']
            except IndexError:
                last_link = rss_d.entries[0]['link']
            msg += f"\nLink: <code>{last_link}</code>"
            msg += f"\n<b>Command: </b><code>{cmd}</code>"
            msg += f"\n<b>Filters:-</b>\ninf: <code>{inf}</code>\nexf: <code>{exf}<code/>"
            async with rss_dict_lock:
                if rss_dict.get(user_id, False):
                    rss_dict[user_id][title] = {'link': feed_link, 'last_feed': last_link, 'last_title': last_title,
                                                'inf': inf_lists, 'exf': exf_lists, 'paused': False, 'command': cmd, 'tag': tag}
                else:
                    rss_dict[user_id] = {title: {'link': feed_link, 'last_feed': last_link, 'last_title': last_title,
                                                 'inf': inf_lists, 'exf': exf_lists, 'paused': False, 'command': cmd, 'tag': tag}}
            LOGGER.info(
                f"Rss Feed Added: id: {user_id} - title: {title} - link: {feed_link} - c: {cmd} - inf: {inf} - exf: {exf}")
        except (IndexError, AttributeError) as e:
            emsg = f"The link: {feed_link} doesn't seem to be a RSS feed or it's region-blocked!"
            await sendMessage(message, emsg + '\nError: ' + str(e))
        except Exception as e:
            await sendMessage(message, str(e))
    if DATABASE_URL:
        await DbManger().rss_update(user_id)
    if msg:
        await sendMessage(message, msg)
    await updateRssMenu(pre_event)


async def getUserId(title):
    async with rss_dict_lock:
        return next(((True, user_id) for user_id, feed in list(rss_dict.items()) if feed['title'] == title), (False, False))


async def rssUpdate(client, message, pre_event, state):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    titles = message.text.split()
    is_sudo = await CustomFilters.sudo(client, message)
    updated = []
    for title in titles:
        title = title.strip()
        if not (res := rss_dict[user_id].get(title, False)):
            if is_sudo:
                res, user_id = await getUserId(title)
            if not res:
                user_id = message.from_user.id
                await sendMessage(message, f'{title} not found!')
                continue
        istate = rss_dict[user_id][title].get('paused', False)
        if istate and state == 'pause' or not istate and state == 'resume':
            await sendMessage(message, f'{title} already {state}d!')
            continue
        async with rss_dict_lock:
            updated.append(title)
            if state == 'unsubscribe':
                del rss_dict[user_id][title]
            elif state == 'pause':
                rss_dict[user_id][title]['paused'] = True
            elif state == 'resume':
                rss_dict[user_id][title]['paused'] = False
        if state == 'resume':
            if scheduler.state == 2:
                scheduler.resume()
            elif is_sudo and not scheduler.running:
                addJob(config_dict['RSS_DELAY'])
                scheduler.start()
        if is_sudo and DATABASE_URL and user_id != message.from_user.id:
            await DbManger().rss_update(user_id)
        if not rss_dict[user_id]:
            async with rss_dict_lock:
                del rss_dict[user_id]
            if DATABASE_URL:
                await DbManger().rss_delete(user_id)
                if not rss_dict:
                    await DbManger().trunc_table('rss')
    LOGGER.info(f"Rss link with Title(s): {updated} has been {state}d!")
    await sendMessage(message, f"Rss links with Title(s): <code>{updated}</code> has been {state}d!")
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
                for index, (title, data) in enumerate(list(titles.items())[start:5+start]):
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
            for title, data in list(rss_dict[user_id].items())[start:5+start]:
                list_feed += f"\n\n<b>Title:</b> <code>{title}</code>\n<b>Feed Url: </b><code>{data['link']}</code>\n"
                list_feed += f"<b>Command:</b> <code>{data['command']}</code>\n"
                list_feed += f"<b>Inf:</b> <code>{data['inf']}</code>\n"
                list_feed += f"<b>Exf:</b> <code>{data['exf']}</code>\n"
                list_feed += f"<b>Paused:</b> <code>{data['paused']}</code>\n"
    buttons.ibutton("Back", f"rss back {user_id}")
    buttons.ibutton("Close", f"rss close {user_id}")
    if keysCount > 5:
        for x in range(0, keysCount, 5):
            buttons.ibutton(
                f'{int(x/5)}', f"rss list {user_id} {x}", position='footer')
    button = buttons.build_menu(2)
    if query.message.text.html == list_feed:
        return
    await editMessage(query.message, list_feed, button)


async def rssGet(client, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    args = message.text.split()
    if len(args) < 2:
        await sendMessage(message, f'{args}. Wrong Input format. You should add number of the items you want to get. Read help message before adding new subcription!')
        await updateRssMenu(pre_event)
        return
    try:
        title = args[0]
        count = int(args[1])
        data = rss_dict[user_id].get(title, False)
        if data and count > 0:
            try:
                msg = await sendMessage(message, f"Getting the last <b>{count}</b> item(s) from {title}")
                async with ClientSession(trust_env=True) as session:
                    async with session.get(data['link']) as res:
                        html = await res.text()
                rss_d = feedparse(html)
                item_info = ""
                for item_num in range(count):
                    try:
                        link = rss_d.entries[item_num]['links'][1]['href']
                    except IndexError:
                        link = rss_d.entries[item_num]['link']
                    item_info += f"<b>Name: </b><code>{rss_d.entries[item_num]['title'].replace('>', '').replace('<', '')}</code>\n"
                    item_info += f"<b>Link: </b><code>{link}</code>\n\n"
                item_info_ecd = item_info.encode()
                if len(item_info_ecd) > 4000:
                    with BytesIO(item_info_ecd) as out_file:
                        out_file.name = f"rssGet {title} items_no. {count}.txt"
                        await sendFile(message, out_file)
                    await msg.delete()
                else:
                    await editMessage(msg, item_info)
            except IndexError as e:
                LOGGER.error(str(e))
                await editMessage(msg, "Parse depth exceeded. Try again with a lower value.")
            except Exception as e:
                LOGGER.error(str(e))
                await editMessage(msg, str(e))
    except Exception as e:
        LOGGER.error(str(e))
        await sendMessage(message, f"Enter a valid value!. {e}")
    await updateRssMenu(pre_event)


async def rssEdit(client, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    items = message.text.split('\n')
    for item in items:
        args = item.split()
        title = args[0].strip()
        if len(args) < 2:
            await sendMessage(message, f'{item}. Wrong Input format. Read help message before editing!')
            continue
        elif not rss_dict[user_id].get(title, False):
            await sendMessage(message, "Enter a valid title. Title not found!")
            continue
        inf_lists = []
        exf_lists = []
        arg = item.split(' -c ', 1)
        cmd = re_split(' -inf | -exf ', arg[1]
                       )[0].strip() if len(arg) > 1 else None
        arg = item.split(' -inf ', 1)
        inf = re_split(' -c | -exf ', arg[1]
                       )[0].strip() if len(arg) > 1 else None
        arg = item.split(' -exf ', 1)
        exf = re_split(' -c | -inf ', arg[1]
                       )[0].strip() if len(arg) > 1 else None
        async with rss_dict_lock:
            if cmd is not None:
                if cmd.lower() == 'none':
                    cmd = None
                rss_dict[user_id][title]['command'] = cmd
            if inf is not None:
                if inf.lower() != 'none':
                    filters_list = inf.split('|')
                    for x in filters_list:
                        y = x.split(' or ')
                        inf_lists.append(y)
                rss_dict[user_id][title]['inf'] = inf_lists
            if exf is not None:
                if exf.lower() != 'none':
                    filters_list = exf.split('|')
                    for x in filters_list:
                        y = x.split(' or ')
                        exf_lists.append(y)
                rss_dict[user_id][title]['exf'] = exf_lists
    if DATABASE_URL:
        await DbManger().rss_update(user_id)
    await updateRssMenu(pre_event)


async def rssDelete(client, message, pre_event):
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
        return bool(user.id == user_id and event.chat.id == query.message.chat.id and event.text)
    handler = client.add_handler(MessageHandler(
        pfunc, create(event_filter)), group=-1)
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
    if int(data[2]) != user_id and not await CustomFilters.sudo(client, query):
        await query.answer(text="You don't have permission to use these buttons!", show_alert=True)
    elif data[1] == 'close':
        await query.answer()
        handler_dict[user_id] = False
        await message.reply_to_message.delete()
        await message.delete()
    elif data[1] == 'back':
        await query.answer()
        handler_dict[user_id] = False
        await updateRssMenu(query)
    elif data[1] == 'sub':
        await query.answer()
        handler_dict[user_id] = False
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"rss back {user_id}")
        buttons.ibutton("Close", f"rss close {user_id}")
        button = buttons.build_menu(2)
        await editMessage(message, RSS_HELP_MESSAGE, button)
        pfunc = partial(rssSub, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[1] == 'list':
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rssList(query, start)
    elif data[1] == 'get':
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await editMessage(message, 'Send one title with value separated by space get last X items.\nTitle Value\nTimeout: 60 sec.', button)
            pfunc = partial(rssGet, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] in ['unsubscribe', 'pause', 'resume']:
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            if data[1] == 'pause':
                buttons.ibutton("Pause AllMyFeeds", f"rss uallpause {user_id}")
            elif data[1] == 'resume':
                buttons.ibutton("Resume AllMyFeeds",
                                f"rss uallresume {user_id}")
            elif data[1] == 'unsubscribe':
                buttons.ibutton("Unsub AllMyFeeds", f"rss uallunsub {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            await editMessage(message, f'Send one or more rss titles separated by space to {data[1]}.\nTimeout: 60 sec.', button)
            pfunc = partial(rssUpdate, pre_event=query, state=data[1])
            await event_handler(client, query, pfunc)
    elif data[1] == 'edit':
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = '''Send one or more rss titles with new filters or command separated by new line.
Examples:
Title1 -c mirror -up remote:path/subdir -exf none -inf 1080 or 720 opt: up: remote:path/subdir
Title2 -c none -inf none -opt none
Title3 -c mirror -rcf xxx -up xxx -z pswd
Note: Only what you provide will be edited, the rest will be the same like example 2: exf will stay same as it is.
Timeout: 60 sec. Argument -c for command and options
            '''
            await editMessage(message, msg, button)
            pfunc = partial(rssEdit, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1].startswith('uall'):
        handler_dict[user_id] = False
        if len(rss_dict.get(int(data[2]), {})) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith('unsub'):
            async with rss_dict_lock:
                del rss_dict[int(data[2])]
            if DATABASE_URL:
                await DbManger().rss_delete(int(data[2]))
            await updateRssMenu(query)
        elif data[1].endswith('pause'):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]['paused'] = True
            if DATABASE_URL:
                await DbManger().rss_update(int(data[2]))
        elif data[1].endswith('resume'):
            async with rss_dict_lock:
                for title in list(rss_dict[int(data[2])].keys()):
                    rss_dict[int(data[2])][title]['paused'] = False
            if scheduler.state == 2:
                scheduler.resume()
            if DATABASE_URL:
                await DbManger().rss_update(int(data[2]))
        await updateRssMenu(query)
    elif data[1].startswith('all'):
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
            return
        await query.answer()
        if data[1].endswith('unsub'):
            async with rss_dict_lock:
                rss_dict.clear()
            if DATABASE_URL:
                await DbManger().trunc_table('rss')
            await updateRssMenu(query)
        elif data[1].endswith('pause'):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]['paused'] = True
            if scheduler.running:
                scheduler.pause()
            if DATABASE_URL:
                await DbManger().rss_update_all()
        elif data[1].endswith('resume'):
            async with rss_dict_lock:
                for user in list(rss_dict.keys()):
                    for title in list(rss_dict[user].keys()):
                        rss_dict[int(data[2])][title]['paused'] = False
            if scheduler.state == 2:
                scheduler.resume()
            elif not scheduler.running:
                addJob(config_dict['RSS_DELAY'])
                scheduler.start()
            if DATABASE_URL:
                await DbManger().rss_update_all()
    elif data[1] == 'deluser':
        if len(rss_dict) == 0:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            buttons = ButtonMaker()
            buttons.ibutton("Back", f"rss back {user_id}")
            buttons.ibutton("Close", f"rss close {user_id}")
            button = buttons.build_menu(2)
            msg = 'Send one or more user_id separated by space to delete their resources.\nTimeout: 60 sec.'
            await editMessage(message, msg, button)
            pfunc = partial(rssDelete, pre_event=query)
            await event_handler(client, query, pfunc)
    elif data[1] == 'listall':
        if not rss_dict:
            await query.answer(text="No subscriptions!", show_alert=True)
        else:
            await query.answer()
            start = int(data[3])
            await rssList(query, start, all_users=True)
    elif data[1] == 'shutdown':
        if scheduler.running:
            await query.answer()
            scheduler.shutdown(wait=False)
            await sleep(0.5)
            await updateRssMenu(query)
        else:
            await query.answer(text="Already Stopped!", show_alert=True)
    elif data[1] == 'start':
        if not scheduler.running:
            await query.answer()
            addJob(config_dict['RSS_DELAY'])
            scheduler.start()
            await updateRssMenu(query)
        else:
            await query.answer(text="Already Running!", show_alert=True)


async def rssMonitor():
    if not config_dict['RSS_CHAT']:
        LOGGER.warning('RSS_CHAT not added! Shutting down rss scheduler...')
        scheduler.shutdown(wait=False)
        return
    if len(rss_dict) == 0:
        scheduler.pause()
        return
    all_paused = True
    for user, items in list(rss_dict.items()):
        for title, data in list(items.items()):
            await sleep(0)
            try:
                if data['paused']:
                    continue
                async with ClientSession(trust_env=True) as session:
                    async with session.get(data['link']) as res:
                        html = await res.text()
                rss_d = feedparse(html)
                try:
                    last_link = rss_d.entries[0]['links'][1]['href']
                except IndexError:
                    last_link = rss_d.entries[0]['link']
                last_title = rss_d.entries[0]['title']
                if data['last_feed'] == last_link or data['last_title'] == last_title:
                    all_paused = False
                    continue
                all_paused = False
                feed_count = 0
                while True:
                    try:
                        await sleep(10)
                    except:
                        raise RssShutdownException('Rss Monitor Stopped!')
                    try:
                        item_title = rss_d.entries[feed_count]['title']
                        try:
                            url = rss_d.entries[feed_count]['links'][1]['href']
                        except IndexError:
                            url = rss_d.entries[feed_count]['link']
                        if data['last_feed'] == url or data['last_title'] == item_title:
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
                LOGGER.info(f"Feed Name: {title}")
                LOGGER.info(f"Last item: {last_link}")
            except RssShutdownException as ex:
                LOGGER.info(ex)
                break
            except Exception as e:
                LOGGER.error(
                    f"{e} Feed Name: {title} - Feed Link: {data['link']}")
                continue
    if all_paused:
        scheduler.pause()


def addJob(delay):
    scheduler.add_job(rssMonitor, trigger=IntervalTrigger(seconds=delay), id='0', name='RSS', misfire_grace_time=15,
                      max_instances=1, next_run_time=datetime.now()+timedelta(seconds=20), replace_existing=True)


addJob(config_dict['RSS_DELAY'])
scheduler.start()
bot.add_handler(MessageHandler(getRssMenu, filters=command(
    BotCommands.RssCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(rssListener, filters=regex("^rss")))
