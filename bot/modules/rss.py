import feedparser
# import requests

# from io import BytesIO
from time import sleep
from telegram.ext import CommandHandler
# from requests.exceptions import RequestException

from bot import dispatcher, job_queue, rss_dict, rss_dict_lock, LOGGER, DB_URI, RSS_DELAY, RSS_CHAT_ID, RSS_COMMAND
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, sendRss
from bot.helper.ext_utils.bot_utils import new_thread
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.ext_utils.db_handler import DbManger

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
                rss_d = feedparser.parse(feed_url[0])
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

@new_thread
def rss_sub(update, context):
    try:
        args = update.message.text.split(" ")
        title = str(args[1])
        feed_link = str(args[2])
        exists = rss_dict.get(title)
        if exists is not None:
            LOGGER.error("This title already subscribed! Choose another title!")
            return sendMessage("This title already subscribed! Choose another title!", context.bot, update)
        try:
            rss_d = feedparser.parse(feed_link)
            sub_msg = "<b>Subscribed!</b>"
            sub_msg += f"\n\n<b>Title: </b><code>{title}</code>\n<b>Feed Url: </b>{feed_link}"
            sub_msg += f"\n\n<b>latest record for </b>{rss_d.feed.title}:"
            sub_msg += f"\n\n<b>Name: </b><code>{rss_d.entries[0]['title']}</code>"
            try:
                link = rss_d.entries[0]['links'][1]['href']
            except IndexError:
                link = rss_d.entries[0]['link']
            sub_msg += f"\n\n<b>Link: </b><code>{link}</code>"
            DbManger().rss_add(title, feed_link, str(rss_d.entries[0]['link']), str(rss_d.entries[0]['title']))
            with rss_dict_lock:
                if len(rss_dict) == 0:
                    rss_job.enabled = True
                rss_dict[title] = [feed_link, str(rss_d.entries[0]['link']), str(rss_d.entries[0]['title'])]
            sendMessage(sub_msg, context.bot, update)
            LOGGER.info(f"Rss Feed Added: {title} - {feed_link}")
        except (IndexError, AttributeError) as e:
            LOGGER.error(str(e))
            msg = "The link doesn't seem to be a RSS feed or it's region-blocked!"
            sendMessage(msg, context.bot, update)
        except Exception as e:
            LOGGER.error(str(e))
            sendMessage(str(e), context.bot, update)
    except IndexError:
        sendMessage(f"Use this format to add feed url:\n/{BotCommands.RssSubCommand} Title https://www.rss-url.com", context.bot, update)

@new_thread
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

@new_thread
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
        for name, url_list in rss_dict.items():
            """
            try:
                resp = requests.get(url_list[0], timeout=15)
            except RequestException as e:
                LOGGER.error(f"{e} for feed: {name} - {url_list[0]}")
                continue
            content = BytesIO(resp.content)
            """
            try:
                rss_d = feedparser.parse(url_list[0])
                last_link = rss_d.entries[0]['link']
                last_title = rss_d.entries[0]['title']
                if (url_list[1] != last_link and url_list[2] != last_title):
                    feed_count = 0
                    while (url_list[1] != rss_d.entries[feed_count]['link'] and url_list[2] != rss_d.entries[feed_count]['title']):
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
                    rss_dict[name] = [url_list[0], str(last_link), str(last_title)]
                    LOGGER.info(f"Feed Name: {name}")
                    LOGGER.info(f"Last item: {rss_d.entries[0]['link']}")
            except IndexError as e:
                LOGGER.error(f"There was an error while parsing this feed: {name} - {url_list[0]} - Error: {e}")
                continue
            except Exception as e:
                LOGGER.error(str(e))
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
