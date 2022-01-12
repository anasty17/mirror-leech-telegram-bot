from feedparser import parse as feedparse
from time import sleep
from telegram.ext import CommandHandler
from threading import Lock

from bot import dispatcher, job_queue, rss_dict, LOGGER, DB_URI, RSS_DELAY, RSS_CHAT_ID, RSS_COMMAND
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, sendRss
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger

rss_dict_lock = Lock()

def rss_list(update, context):
    if len(rss_dict) > 0:
        list_feed = "<b>Your subscriptions: </b>\n\n"
        for title, url in list(rss_dict.items()):
            list_feed += f"<b>Title:</b> <code>{title}</code>\n<b>Feed Url: </b><code>{url[0]}</code>\n\n"
        sendMessage(list_feed, context.bot, update)
    else:
        sendMessage("No subscriptions.", context.bot, update)

def rss_get(update, context):
    try:
        args = update.message.text.split(" ")
        title = args[1]
        count = int(args[2])
        feed_url = rss_dict.get(title)
        if feed_url is not None and count > 0:
            try:
                msg = sendMessage(f"Getting the last <b>{count}</b> item(s) from {title}", context.bot, update)
                rss_d = feedparse(feed_url[0])
                item_info = ""
                for item_num in range(count):
                    try:
                        link = rss_d.entries[item_num]['links'][1]['href']
                    except IndexError:
                        link = rss_d.entries[item_num]['link']
                    item_info += f"<b>Name: </b><code>{rss_d.entries[item_num]['title']}</code>\n"
                    item_info += f"<b>Link: </b><code>{link}</code>\n\n"
                editMessage(item_info, msg)
            except IndexError as e:
                LOGGER.error(str(e))
                editMessage("Parse depth exceeded. Try again with a lower value.", msg)
            except Exception as e:
                LOGGER.error(str(e))
                editMessage(str(e), msg)
        else:
            sendMessage("Enter a vaild title/value.", context.bot, update)
    except (IndexError, ValueError):
        sendMessage(f"Use this format to fetch:\n/{BotCommands.RssGetCommand} Title value", context.bot, update)

def rss_sub(update, context):
    try:
        args = update.message.text.split(" ", 3)
        title = str(args[1])
        feed_link = str(args[2])
        f_lists = []
        try:
            filters = str(args[3]).lower()
            if filters.startswith('f: '):
                filters = filters.split('f: ', 1)[1]
                filters_list = filters.split('|')
                for x in filters_list:
                   y = x.split(' or ')
                   f_lists.append(y)
            else:
                filters = None
        except:
            filters = None
        exists = rss_dict.get(title)
        if exists is not None:
            LOGGER.error("This title already subscribed! Choose another title!")
            return sendMessage("This title already subscribed! Choose another title!", context.bot, update)
        try:
            rss_d = feedparse(feed_link)
            sub_msg = "<b>Subscribed!</b>"
            sub_msg += f"\n\n<b>Title: </b><code>{title}</code>\n<b>Feed Url: </b>{feed_link}"
            sub_msg += f"\n\n<b>latest record for </b>{rss_d.feed.title}:"
            sub_msg += f"\n\n<b>Name: </b><code>{rss_d.entries[0]['title']}</code>"
            try:
                link = rss_d.entries[0]['links'][1]['href']
            except IndexError:
                link = rss_d.entries[0]['link']
            sub_msg += f"\n\n<b>Link: </b><code>{link}</code>"
            sub_msg += f"\n\n<b>Filters: </b><code>{filters}</code>"
            last_link = str(rss_d.entries[0]['link'])
            last_title = str(rss_d.entries[0]['title'])
            DbManger().rss_add(title, feed_link, last_link, last_title, filters)
            with rss_dict_lock:
                if len(rss_dict) == 0:
                    rss_job.enabled = True
                rss_dict[title] = [feed_link, last_link, last_title, f_lists]
            sendMessage(sub_msg, context.bot, update)
            LOGGER.info(f"Rss Feed Added: {title} - {feed_link} - {filters}")
        except (IndexError, AttributeError) as e:
            LOGGER.error(str(e))
            msg = "The link doesn't seem to be a RSS feed or it's region-blocked!"
            sendMessage(msg, context.bot, update)
        except Exception as e:
            LOGGER.error(str(e))
            sendMessage(str(e), context.bot, update)
    except IndexError:
        msg = f"Use this format to add feed url:\n/{BotCommands.RssSubCommand} Title https://www.rss-url.com"
        msg += " f: 1080 or 720 or 144p|mkv or mp4|hevc (optional)\n\nThis filter will parse links that it's titles"
        msg += " contains `(1080 or 720 or 144p) and (mkv or mp4) and hevc` words. You can add whatever you want.\n\n"
        msg += "Another example: f:  1080  or 720p|.web. or .webrip.|hvec or x264 .. This will parse titles that contains"
        msg += " ( 1080  or 720p) and (.web. or .webrip.) and (hvec or x264). I have added space before and after 1080"
        msg += " to avoid wrong matching. If this `10805695` number in title it will match 1080 if added 1080 without"
        msg += " spaces after it."
        msg += "\n\nFilters Notes:\n\n1. | means and.\n\n2. Add `or` between similar keys, you can add it"
        msg += " between qualities or between extensions, so don't add filter like this f: 1080|mp4 or 720|web"
        msg += " because this will parse 1080 and (mp4 or 720) and web ... not (1080 and mp4) or (720 and web)."
        msg += "\n\n3. You can add `or` and `|` as much as you want."
        msg += "\n\n4. Take look on title if it has static special character after or before the qualities or extensions"
        msg += " or whatever and use them in filter to avoid wrong match"
        sendMessage(msg, context.bot, update)

def rss_unsub(update, context):
    try:
        args = update.message.text.split(" ")
        title = str(args[1])
        exists = rss_dict.get(title)
        if exists is None:
            LOGGER.error("Rss link not exists! Nothing removed!")
            sendMessage("Rss link not exists! Nothing removed!", context.bot, update)
        else:
            DbManger().rss_delete(title)
            with rss_dict_lock:
                del rss_dict[title]
            sendMessage(f"Rss link with Title: {title} removed!", context.bot, update)
            LOGGER.info(f"Rss link with Title: {title} removed!")
    except IndexError:
        sendMessage(f"Use this format to remove feed url:\n/{BotCommands.RssUnSubCommand} Title", context.bot, update)

def rss_unsuball(update, context):
    if len(rss_dict) > 0:
        DbManger().rss_delete_all()
        with rss_dict_lock:
            rss_dict.clear()
        rss_job.enabled = False
        sendMessage("All subscriptions deleted.", context.bot, update)
        LOGGER.info("All Rss Subscriptions has been removed")
    else:
        sendMessage("No subscriptions to remove!", context.bot, update)

def rss_monitor(context):
    with rss_dict_lock:
        if len(rss_dict) == 0:
            rss_job.enabled = False
            return
        rss_saver = rss_dict
    for name, data in rss_saver.items():
        try:
            rss_d = feedparse(data[0])
            last_link = rss_d.entries[0]['link']
            last_title = rss_d.entries[0]['title']
            if data[1] == last_link or data[2] == last_title:
                continue
            feed_count = 0
            while True:
                try:
                    if data[1] == rss_d.entries[feed_count]['link'] or data[2] == rss_d.entries[feed_count]['title']:
                        break
                except IndexError:
                    LOGGER.info(f"Reached Max index no. {feed_count} for this feed: {name}. \
                          Maybe you need to add less RSS_DELAY to not miss some torrents")
                    break
                parse = True
                for list in data[3]:
                    if not any(x in str(rss_d.entries[feed_count]['title']).lower() for x in list):
                        parse = False
                        feed_count += 1
                        break
                if not parse:
                    continue
                try:
                    url = rss_d.entries[feed_count]['links'][1]['href']
                except IndexError:
                    url = rss_d.entries[feed_count]['link']
                if RSS_COMMAND is not None:
                    feed_msg = f"{RSS_COMMAND} {url}"
                else:
                    feed_msg = f"<b>Name: </b><code>{rss_d.entries[feed_count]['title']}</code>\n\n"
                    feed_msg += f"<b>Link: </b><code>{url}</code>"
                sendRss(feed_msg, context.bot)
                feed_count += 1
                sleep(5)
            DbManger().rss_update(name, str(last_link), str(last_title))
            with rss_dict_lock:
                rss_dict[name] = [data[0], str(last_link), str(last_title), data[3]]
            LOGGER.info(f"Feed Name: {name}")
            LOGGER.info(f"Last item: {last_link}")
        except Exception as e:
            LOGGER.error(f"{e} Feed Name: {name} - Feed Link: {data[0]}")
            continue

if DB_URI is not None and RSS_CHAT_ID is not None:
    rss_list_handler = CommandHandler(BotCommands.RssListCommand, rss_list, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    rss_get_handler = CommandHandler(BotCommands.RssGetCommand, rss_get, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    rss_sub_handler = CommandHandler(BotCommands.RssSubCommand, rss_sub, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    rss_unsub_handler = CommandHandler(BotCommands.RssUnSubCommand, rss_unsub, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)
    rss_unsub_all_handler = CommandHandler(BotCommands.RssUnSubAllCommand, rss_unsuball, filters=CustomFilters.owner_filter | CustomFilters.sudo_user, run_async=True)

    dispatcher.add_handler(rss_list_handler)
    dispatcher.add_handler(rss_get_handler)
    dispatcher.add_handler(rss_sub_handler)
    dispatcher.add_handler(rss_unsub_handler)
    dispatcher.add_handler(rss_unsub_all_handler)
    rss_job = job_queue.run_repeating(rss_monitor, interval=RSS_DELAY, first=20, name="RSS")
