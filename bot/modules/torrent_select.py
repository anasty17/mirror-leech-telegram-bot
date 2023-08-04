#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from aiofiles.os import remove as aioremove, path as aiopath

from bot import bot, aria2, download_dict, download_dict_lock, OWNER_ID, user_data, LOGGER
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, sendStatusMessage, deleteMessage
from bot.helper.ext_utils.bot_utils import getDownloadByGid, MirrorStatus, bt_selection_buttons, sync_to_async


async def select(client, message):
    user_id = message.from_user.id
    msg = message.text.split()
    if len(msg) > 1:
        gid = msg[1]
        dl = await getDownloadByGid(gid)
        if dl is None:
            await sendMessage(message, f"GID: <code>{gid}</code> Not Found.")
            return
    elif reply_to_id := message.reply_to_message_id:
        async with download_dict_lock:
            dl = download_dict.get(reply_to_id, None)
        if dl is None:
            await sendMessage(message, "This is not an active task!")
            return
    elif len(msg) == 1:
        msg = ("Reply to an active /cmd which was used to start the qb-download or add gid along with cmd\n\n"
               + "This command mainly for selection incase you decided to select files from already added torrent. "
               + "But you can always use /cmd with arg `s` to select files before download start.")
        await sendMessage(message, msg)
        return

    if OWNER_ID != user_id and dl.message.from_user.id != user_id and \
       (user_id not in user_data or not user_data[user_id].get('is_sudo')):
        await sendMessage(message, "This task is not for you!")
        return
    if dl.status() not in [MirrorStatus.STATUS_DOWNLOADING, MirrorStatus.STATUS_PAUSED, MirrorStatus.STATUS_QUEUEDL]:
        await sendMessage(message, 'Task should be in download or pause (incase message deleted by wrong) or queued (status incase you used torrent file)!')
        return
    if dl.name().startswith('[METADATA]'):
        await sendMessage(message, 'Try after downloading metadata finished!')
        return

    try:
        listener = dl.listener()
        if listener.isQbit:
            id_ = dl.hash()
            client = dl.client()
            if not dl.queued:
                await sync_to_async(client.torrents_pause, torrent_hashes=id_)
        else:
            id_ = dl.gid()
            if not dl.queued:
                try:
                    await sync_to_async(aria2.client.force_pause, id_)
                except Exception as e:
                    LOGGER.error(
                        f"{e} Error in pause, this mostly happens after abuse aria2")
        listener.select = True
    except:
        await sendMessage(message, "This is not a bittorrent task!")
        return

    SBUTTONS = bt_selection_buttons(id_)
    msg = "Your download paused. Choose files then press Done Selecting button to resume downloading."
    await sendMessage(message, msg, SBUTTONS)


async def get_confirm(client, query):
    user_id = query.from_user.id
    data = query.data.split()
    message = query.message
    dl = await getDownloadByGid(data[2])
    if dl is None:
        await query.answer("This task has been cancelled!", show_alert=True)
        await deleteMessage(message)
        return
    if hasattr(dl, 'listener'):
        listener = dl.listener()
    else:
        await query.answer("Not in download state anymore! Keep this message to resume the seed if seed enabled!", show_alert=True)
        return
    if user_id != listener.user_id:
        await query.answer("This task is not for you!", show_alert=True)
    elif data[1] == "pin":
        await query.answer(data[3], show_alert=True)
    elif data[1] == "done":
        await query.answer()
        id_ = data[3]
        if len(id_) > 20:
            client = dl.client()
            tor_info = (await sync_to_async(client.torrents_info, torrent_hash=id_))[0]
            path = tor_info.content_path.rsplit('/', 1)[0]
            res = await sync_to_async(client.torrents_files, torrent_hash=id_)
            for f in res:
                if f.priority == 0:
                    f_paths = [f"{path}/{f.name}", f"{path}/{f.name}.!qB"]
                    for f_path in f_paths:
                        if await aiopath.exists(f_path):
                            try:
                                await aioremove(f_path)
                            except:
                                pass
            if not dl.queued:
                await sync_to_async(client.torrents_resume, torrent_hashes=id_)
        else:
            res = await sync_to_async(aria2.client.get_files, id_)
            for f in res:
                if f['selected'] == 'false' and await aiopath.exists(f['path']):
                    try:
                        await aioremove(f['path'])
                    except:
                        pass
            if not dl.queued:
                try:
                    await sync_to_async(aria2.client.unpause, id_)
                except Exception as e:
                    LOGGER.error(
                        f"{e} Error in resume, this mostly happens after abuse aria2. Try to use select cmd again!")
        await sendStatusMessage(message)
        await deleteMessage(message)


bot.add_handler(MessageHandler(select, filters=command(
    BotCommands.BtSelectCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(get_confirm, filters=regex("^btsel")))
