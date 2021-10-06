import feedparser
from dotenv import load_dotenv

import psycopg2
from psycopg2 import Error

from telegram.ext import  CommandHandler
from bot import LOGGER, dispatcher, updater, CHAT_ID, DELAY, DB_URI, INIT_FEEDS, CUSTOM_MESSAGES
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters

# Init 

rss_dict = {}
    
# Postgresql

def init_postgres():
    try:
        conn = psycopg2.connect(DB_URI)
        c = conn.cursor()
        c.execute("CREATE TABLE rss (name text, link text, last text, title text)")
        conn.commit()
        conn.close()
        LOGGER.info("Database Created.")
    except psycopg2.errors.DuplicateTable:
        LOGGER.info("Database already exists.")
        rss_load()

def postgres_load_all():
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    c.execute("SELECT * FROM rss")
    rows = c.fetchall()
    conn.close()
    return rows

def postgres_write(name, link, last, title):
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    q = [(name), (link), (last), (title)]
    c.execute("INSERT INTO rss (name, link, last, title) VALUES(%s, %s, %s, %s)", q)
    conn.commit()
    conn.close()
    rss_load()

def postgres_update(last, name, title):
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    q = [(last), (title), (name)]
    c.execute("UPDATE rss SET last=%s, title=%s WHERE name=%s", q)
    conn.commit()
    conn.close()

def postgres_find(q):
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    # check the database for the latest feed
    c.execute("SELECT link FROM rss WHERE name = %s", q)
    feedurl = c.fetchone()
    conn.close()
    return feedurl

def postgres_delete(q):
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    try:
        c.execute("DELETE FROM rss WHERE name = %s", q)
        conn.commit()
        conn.close()
    except psycopg2.errors.UndefinedTable:
        pass
    rss_load()

def postgres_deleteall():
    # clear database & dictionary
    conn = psycopg2.connect(DB_URI)
    c = conn.cursor()
    c.execute("TRUNCATE TABLE rss")
    conn.commit()
    conn.close()
    rss_dict.clear()
    LOGGER.info('Database deleted.')

# RSS

def rss_load():
    # if the dict is not empty, empty it.
    if bool(rss_dict):
        rss_dict.clear()

    for row in postgres_load_all():
        rss_dict[row[0]] = (row[1], row[2], row[3])

def cmd_rsshelp(update, context):
    help_string=f"""
<b>Commands:</b> 
• /rsshelp: <i>To get this message</i>
• /feeds: <i>List your subscriptions</i>
• /get Title 10: <i>Force fetch last n item(s)</i>
• /sub Title https://www.rss-url.com: <i>Subscribe to a RSS feed</i>
• /unsub Title: <i>Removes the RSS subscription corresponding to it's title</i>
• /unsuball: <i>Removes all subscriptions</i>
"""
    update.effective_message.reply_text(help_string, parse_mode='HTMl')

def cmd_rss_list(update, context):
    listfeed = ""
    if bool(rss_dict) is False:
        update.effective_message.reply_text("No subscriptions.")
    else:
        for title, url_list in rss_dict.items():
            listfeed +=f"Title: {title}\nFeed: {url_list[0]}\n\n"
        update.effective_message.reply_text(f"<b>Your subscriptions:</b>\n\n" + listfeed, parse_mode='HTMl')

def cmd_get(update, context):
    try:
        count = context.args[1]
        q = (context.args[0],)
        feedurl = postgres_find(q)
        if  feedurl != None:
            feedinfo = ""
            try:
                if int(context.args[1]) > 0:
                    feed_num = int(context.args[1])
                else:
                    raise Exception  
            except (ValueError, Exception):
                update.effective_message.reply_text("Enter a value > 0.")
                LOGGER.error("You trolling? Study Math doofus.")
            else:
                msg = update.effective_message.reply_text(f"Getting the last <b>{count}</b> item(s), please wait!", parse_mode='HTMl')
                for num_feeds in range(feed_num):
                    rss_d = feedparser.parse(feedurl[0])
                    feedinfo +=f"<b>{rss_d.entries[num_feeds]['title']}</b>\n{rss_d.entries[num_feeds]['link']}\n\n"
                msg.edit_text(feedinfo, parse_mode='HTMl')    
        else:
            update.effective_message.reply_text("No such feed found.")
    except IndexError:
        update.effective_message.reply_text("Please use this format to fetch:\n/get Title 10", parse_mode='HTMl')

def cmd_rss_sub(update, context):
    addfeed = ""
    # try if there are 2 arguments passed
    try:
        context.args[1]
    except IndexError:
        update.effective_message.reply_text(f"Please use this format to add:\n/sub Title https://www.rss-url.com", parse_mode='HTMl')
    else:
        try:
            # try if the url is a valid RSS feed
            rss_d = feedparser.parse(context.args[1])
            rss_d.entries[0]['title']
            title_rss =  f"<b>{rss_d.feed.title}</b> latest record:\n<b>{rss_d.entries[0]['title']}</b>\n{rss_d.entries[0]['link']}"    
            postgres_write(context.args[0], context.args[1], str(rss_d.entries[0]['link']), str(rss_d.entries[0]['title']))
            addfeed = f"<b>Subscribed!</b>\nTitle: {context.args[0]}\nFeed: {context.args[1]}"
            update.effective_message.reply_text(addfeed, parse_mode='HTMl')
            update.effective_message.reply_text(title_rss, parse_mode='HTMl')
        except IndexError:
            update.effective_message.reply_text("The link doesn't seem to be a RSS feed or it's not supported!")

def cmd_rss_unsub(update, context):
    try:
        q = (context.args[0],)        
        postgres_delete(q)
        update.effective_message.reply_text("If it exists in the database, it'll be removed.")
    except IndexError:
        update.effective_message.reply_text(f"Please use this format to remove:\n/unsub Title", parse_mode='HTMl')                

def cmd_rss_unsuball(update, context):
    if rss_dict != {}:
        postgres_deleteall()
        update.effective_message.reply_text("Deleted all subscriptions.")
    else:
        update.effective_message.reply_text("No subscriptions.")

def init_feeds():
    if INIT_FEEDS == "True":
        for name, url_list in rss_dict.items():
            try:
                rss_d = feedparser.parse(url_list[0])
                postgres_update(str(rss_d.entries[0]['link']), name, str(rss_d.entries[0]['title']))
                LOGGER.info("Feed name: "+ name)
                LOGGER.info("Latest feed item: "+ rss_d.entries[0]['link'])
            except IndexError:
                LOGGER.info(f"There was an error while parsing this feed: {url_list[0]}")
                continue                    
        rss_load()
        LOGGER.info('Initiated feeds.')

def rss_monitor(context):
    feed_info = ""
    for name, url_list in rss_dict.items():
        try:
            feed_count = 0
            feed_titles = []
            feed_urls = []
            # check whether the URL & title of the latest item is in the database
            rss_d = feedparser.parse(url_list[0])
            if (url_list[1] != rss_d.entries[0]['link'] and url_list[2] != rss_d.entries[0]['title']):
                # check until a new item pops up
                while (url_list[1] != rss_d.entries[feed_count]['link'] and url_list[2] != rss_d.entries[feed_count]['title']):
                    feed_titles.insert(0, rss_d.entries[feed_count]['title'])
                    feed_urls.insert(0, rss_d.entries[feed_count]['link'])
                    feed_count += 1
                for x in range(len(feed_urls)):
                    feed_info = f"{CUSTOM_MESSAGES}\n<b>{feed_titles[x]}</b>\n{feed_urls[x]}"
                    context.bot.send_message(CHAT_ID, feed_info, parse_mode='HTMl')
                # overwrite the existing item with the latest item
                postgres_update(str(rss_d.entries[0]['link']), name, str(rss_d.entries[0]['title']))
        except IndexError:
            LOGGER.info(f"There was an error while parsing this feed: {url_list[0]}")
            continue
        else:
            LOGGER.info("Feed name: "+ name)
            LOGGER.info("Latest feed item: "+ rss_d.entries[0]['link'])
    rss_load()
    LOGGER.info('Database Updated.')

def rss_init():
    job_queue = updater.job_queue

    dispatcher.add_handler(CommandHandler(BotCommands.RssHelpCommand, cmd_rsshelp, filters=CustomFilters.owner_filter, run_async=True))    
    dispatcher.add_handler(CommandHandler("feeds", cmd_rss_list, filters=CustomFilters.owner_filter, run_async=True))
    dispatcher.add_handler(CommandHandler("get", cmd_get, filters=CustomFilters.owner_filter, run_async=True))     
    dispatcher.add_handler(CommandHandler("sub", cmd_rss_sub, filters=CustomFilters.owner_filter, run_async=True))
    dispatcher.add_handler(CommandHandler("unsub", cmd_rss_unsub, filters=CustomFilters.owner_filter, run_async=True))
    dispatcher.add_handler(CommandHandler("unsuball", cmd_rss_unsuball, filters=CustomFilters.owner_filter, run_async=True))

    init_postgres()
    init_feeds()

    job_queue.run_repeating(rss_monitor, DELAY)
