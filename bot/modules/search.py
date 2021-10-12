import math
import qbittorrentapi as qba
from telegram import InlineKeyboardMarkup
from telegram.ext import CallbackQueryHandler, CommandHandler

from bot import dispatcher, LOGGER, get_client, search_dict_lock, search_dict
from bot.helper.telegram_helper.message_utils import editMessage, sendMessage
from bot.helper.ext_utils.bot_utils import new_thread, get_readable_file_size
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper import button_build


@new_thread
def search(update, context):
    try:
        key = update.message.text.split(" ", maxsplit=1)[1]
        client = get_client()
        search = client.search_start(pattern=str(key), plugins='all', category='all')
        srchmsg = sendMessage("Searching...", context.bot, update)
        user_id = update.message.from_user.id
        search_id = search.id
        LOGGER.info(f"qBittorrent Search: {key}")
        while True:
            result_status = client.search_status(search_id=search_id)
            status = result_status[0].status
            if status != 'Running':
                break
        dict_search_results = client.search_results(search_id=search_id)
        search_results = dict_search_results.results
        total_results = dict_search_results.total
        if total_results != 0:
            total_pages = math.ceil(total_results/3)
            msg = getResult(search_results)
            buttons = button_build.ButtonMaker()
            if total_results > 3:
                msg += f"<b>Pages: </b>1/{total_pages} | <b>Results: </b>{total_results}"
                buttons.sbutton("Previous", f"srchprev {user_id} {search_id}")
                buttons.sbutton("Next", f"srchnext {user_id} {search_id}")
            buttons.sbutton("Close", f"closesrch {user_id} {search_id}")
            button = InlineKeyboardMarkup(buttons.build_menu(2))
            editMessage(msg, srchmsg, button)
            with search_dict_lock:
                search_dict[search_id] = client, search_results, total_results, total_pages, 1, 0
        else:
            editMessage(f"No result found for <i>{key}</i>", srchmsg)
    except IndexError:
        sendMessage("Send a search key along with command", context.bot, update)
    except Exception as e:
        LOGGER.error(str(e))

def searchPages(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    data = query.data
    data = data.split(" ")
    search_id = int(data[2])
    if user_id != int(data[1]):
        query.answer(text="Not Yours!", show_alert=True)
        return
    with search_dict_lock:
        try:
            client, search_results, total_results, total_pages, pageNo, start = search_dict[search_id]
        except:
            query.answer(text="Old Result", show_alert=True)
            query.message.delete()
            return
    if data[0] == "srchnext":
        if pageNo == total_pages:
            start = 0
            pageNo = 1
        else:
            start += 3
            pageNo += 1
    elif data[0] == "srchprev":
        if pageNo == 1:
            pageNo = total_pages
            start = 3 * (total_pages -1)
        else:
            pageNo -= 1
            start -= 3
    elif data[0] == "closesrch":
        client.search_delete(search_id)
        client.auth_log_out()
        with search_dict_lock:
            try:
                del search_dict[search_id]
            except:
                pass
        query.message.delete()
        return
    with search_dict_lock:
        search_dict[search_id] = client, search_results, total_results, total_pages, pageNo, start
    msg = getResult(search_results, start=start)
    msg += f"<b>Pages: </b>{pageNo}/{total_pages} | <b>Results: </b>{total_results}"
    buttons = button_build.ButtonMaker()
    buttons.sbutton("Previous", f"srchprev {user_id} {search_id}")
    buttons.sbutton("Next", f"srchnext {user_id} {search_id}")
    buttons.sbutton("Close", f"closesrch {user_id} {search_id}")
    button = InlineKeyboardMarkup(buttons.build_menu(2))
    query.answer()
    editMessage(msg, query.message, button)

def getResult(search_results, start=0):
    msg = ""
    for index, result in enumerate(search_results[start:], start=1):
        msg += f"<a href='{result.descrLink}'>{result.fileName}</a>\n"
        msg += f"<b>Size: </b>{get_readable_file_size(result.fileSize)}\n"
        msg += f"<b>Seeders: </b>{result.nbSeeders} | <b>Leechers: </b>{result.nbLeechers}\n"
        msg += f"<b>Link: </b><code>{result.fileUrl}</code>\n\n"
        if index == 3:
            break
    return msg


search_handler = CommandHandler(BotCommands.SearchCommand, search, filters=CustomFilters.authorized_chat | CustomFilters.authorized_user, run_async=True)
srchnext_handler = CallbackQueryHandler(searchPages, pattern="srchnext", run_async=True)
srchprevious_handler = CallbackQueryHandler(searchPages, pattern="srchprev", run_async=True)
delsrch_handler = CallbackQueryHandler(searchPages, pattern="closesrch", run_async=True)
dispatcher.add_handler(search_handler)
dispatcher.add_handler(srchnext_handler)
dispatcher.add_handler(srchprevious_handler)
dispatcher.add_handler(delsrch_handler)
