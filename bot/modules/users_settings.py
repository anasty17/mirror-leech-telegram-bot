#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex, create
from aiofiles import open as aiopen
from aiofiles.os import remove as aioremove, path as aiopath, mkdir
from os import path as ospath, getcwd
from PIL import Image
from time import time
from functools import partial
from html import escape
from io import BytesIO
from asyncio import sleep

from bot import bot, user_data, config_dict, DATABASE_URL, IS_PREMIUM_USER, MAX_SPLIT_SIZE
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage, sendFile
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.db_handler import DbManger
from bot.helper.ext_utils.bot_utils import update_user_ldata, sync_to_async, new_thread

handler_dict = {}


async def get_user_settings(from_user):
    user_id = from_user.id
    name = from_user.mention
    buttons = ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    rclone_path = f'rclone/{user_id}.conf'
    user_dict = user_data.get(user_id, {})
    if user_dict.get('as_doc', False) or 'as_doc' not in user_dict and config_dict['AS_DOCUMENT']:
        ltype = "DOCUMENT"
        buttons.ibutton("Send As Media", f"userset {user_id} doc")
    else:
        ltype = "MEDIA"
        buttons.ibutton("Send As Document", f"userset {user_id} doc")

    buttons.ibutton("Thumbnail", f"userset {user_id} sthumb")
    thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"

    buttons.ibutton("Leech Splits", f"userset {user_id} lss")
    if user_dict.get('split_size', False):
        split_size = user_dict['split_size']
    else:
        split_size = config_dict['LEECH_SPLIT_SIZE']

    if user_dict.get('equal_splits', False) or 'equal_splits' not in user_dict and config_dict['EQUAL_SPLITS']:
        equal_splits = 'Enabled'
    else:
        equal_splits = 'Disabled'

    if user_dict.get('media_group', False) or 'media_group' not in user_dict and config_dict['MEDIA_GROUP']:
        media_group = 'Enabled'
    else:
        media_group = 'Disabled'

    buttons.ibutton("Leech Prefix", f"userset {user_id} lprefix")
    if user_dict.get('lprefix', False):
        lprefix = user_dict['lprefix']
    elif 'lprefix' not in user_dict and (LP := config_dict['LEECH_FILENAME_PREFIX']):
        lprefix = LP
    else:
        lprefix = 'None'

    buttons.ibutton("Leech Destination", f"userset {user_id} ldest")
    if user_dict.get('leech_dest', False):
        leech_dest = user_dict['leech_dest']
    elif 'leech_dest' not in user_dict and (LD := config_dict['LEECH_DUMP_CHAT']):
        leech_dest = LD
    else:
        leech_dest = 'None'

    buttons.ibutton("Rclone", f"userset {user_id} rcc")
    rccmsg = "Exists" if await aiopath.exists(rclone_path) else "Not Exists"

    buttons.ibutton("YT-DLP Options", f"userset {user_id} yto")
    if user_dict.get('yt_opt', False):
        ytopt = user_dict['yt_opt']
    elif 'yt_opt' not in user_dict and (YTO := config_dict['YT_DLP_OPTIONS']):
        ytopt = YTO
    else:
        ytopt = 'None'

    buttons.ibutton("Close", f"userset {user_id} close")

    text = f"""<u>Settings for {name}</u>
Leech Type is <b>{ltype}</b>
Custom Thumbnail <b>{thumbmsg}</b>
Leech Split Size is <b>{split_size}</b>
Equal Splits is <b>{equal_splits}</b>
Media Group is <b>{media_group}</b>
Leech Prefix is <code>{escape(lprefix)}</code>
Leech Destination is <code>{leech_dest}</code>
Rclone Config <b>{rccmsg}</b>
YT-DLP Options is <b><code>{escape(ytopt)}</code></b>"""

    return text, buttons.build_menu(1)


async def update_user_settings(query):
    msg, button = await get_user_settings(query.from_user)
    await editMessage(query.message, msg, button)


async def user_settings(_, message):
    from_user = message.from_user
    handler_dict[from_user.id] = False
    msg, button = await get_user_settings(from_user)
    await sendMessage(message, msg, button)


async def set_yt_options(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    update_user_ldata(user_id, 'yt_opt', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def set_prefix(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    update_user_ldata(user_id, 'lprefix', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def set_thumb(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    path = "Thumbnails/"
    if not await aiopath.isdir(path):
        await mkdir(path)
    photo_dir = await message.download()
    des_dir = ospath.join(path, f'{user_id}.jpg')
    await sync_to_async(Image.open(photo_dir).convert("RGB").save, des_dir, "JPEG")
    await aioremove(photo_dir)
    update_user_ldata(user_id, 'thumb', des_dir)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_doc(user_id, 'thumb', des_dir)


async def add_rclone(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    path = f'{getcwd()}/rclone/'
    if not await aiopath.isdir(path):
        await mkdir(path)
    des_dir = ospath.join(path, f'{user_id}.conf')
    await message.download(file_name=des_dir)
    update_user_ldata(user_id, 'rclone', f'rclone/{user_id}.conf')
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_doc(user_id, 'rclone', des_dir)


async def leech_split_size(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = min(int(message.text), MAX_SPLIT_SIZE)
    update_user_ldata(user_id, 'split_size', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def set_leech_destination(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    if value.isdigit() or value.startswith('-'):
        value = int(value)
    update_user_ldata(user_id, 'leech_dest', value)
    await message.delete()
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManger().update_user_data(user_id)


async def event_handler(client, query, pfunc, photo=False, document=False):
    user_id = query.from_user.id
    handler_dict[user_id] = True
    start_time = time()

    async def event_filter(_, __, event):
        if photo:
            mtype = event.photo
        elif document:
            mtype = event.document
        else:
            mtype = event.text
        user = event.from_user or event.sender_chat
        return bool(user.id == user_id and event.chat.id == query.message.chat.id and mtype)

    handler = client.add_handler(MessageHandler(
        pfunc, filters=create(event_filter)), group=-1)

    while handler_dict[user_id]:
        await sleep(0.5)
        if time() - start_time > 60:
            handler_dict[user_id] = False
            await update_user_settings(query)
    client.remove_handler(*handler)


@new_thread
async def edit_user_settings(client, query):
    from_user = query.from_user
    user_id = from_user.id
    message = query.message
    data = query.data.split()
    thumb_path = f'Thumbnails/{user_id}.jpg'
    rclone_path = f'rclone/{user_id}.conf'
    user_dict = user_data.get(user_id, {})
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] == "doc":
        update_user_ldata(user_id, 'as_doc',
                          not user_dict.get('as_doc', False))
        await query.answer()
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'vthumb':
        handler_dict[user_id] = False
        await query.answer()
        await sendFile(message, thumb_path, from_user.mention)
        await update_user_settings(query)
    elif data[2] == "dthumb":
        handler_dict[user_id] = False
        if await aiopath.exists(thumb_path):
            await query.answer()
            await aioremove(thumb_path)
            update_user_ldata(user_id, 'thumb', '')
            await update_user_settings(query)
            if DATABASE_URL:
                await DbManger().update_user_doc(user_id, 'thumb')
        else:
            await query.answer("Old Settings", show_alert=True)
            await update_user_settings(query)
    elif data[2] == "sthumb":
        await query.answer()
        buttons = ButtonMaker()
        if await aiopath.exists(thumb_path):
            buttons.ibutton("View Thumbnail", f"userset {user_id} vthumb")
            buttons.ibutton("Delete Thumbnail", f"userset {user_id} dthumb")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(message, 'Send a photo to save it as custom thumbnail. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(set_thumb, pre_event=query)
        await event_handler(client, query, pfunc, True)
    elif data[2] == 'yto':
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} back")
        if user_dict.get('yt_opt', False) or config_dict['YT_DLP_OPTIONS']:
            buttons.ibutton("Remove YT-DLP Options",
                            f"userset {user_id} ryto", 'header')
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = '''
Send YT-DLP Options. Timeout: 60 sec
Format: key:value|key:value|key:value.
Example: format:bv*+mergeall[vcodec=none]|nocheckcertificate:True
Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official/177'>script</a> to convert cli arguments to api options.
        '''
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_yt_options, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'ryto':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'yt_opt', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'lss':
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get('split_size', False):
            buttons.ibutton("Reset Split Size", f"userset {user_id} rlss")
        if user_dict.get('equal_splits', False) or 'equal_splits' not in user_dict and config_dict['EQUAL_SPLITS']:
            buttons.ibutton("Disable Equal Splits",
                            f"userset {user_id} esplits")
        else:
            buttons.ibutton("Enable Equal Splits",
                            f"userset {user_id} esplits")
        if user_dict.get('media_group', False) or 'media_group' not in user_dict and config_dict['MEDIA_GROUP']:
            buttons.ibutton("Disable Media Group", f"userset {user_id} mgroup")
        else:
            buttons.ibutton("Enable Media Group", f"userset {user_id} mgroup")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(message, f'Send Leech split size in bytes. IS_PREMIUM_USER: {IS_PREMIUM_USER}. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(leech_split_size, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'rlss':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'split_size', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'esplits':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'equal_splits',
                          not user_dict.get('equal_splits', False))
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'mgroup':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'media_group',
                          not user_dict.get('media_group', False))
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'rcc':
        await query.answer()
        buttons = ButtonMaker()
        if await aiopath.exists(rclone_path):
            buttons.ibutton("Delete rclone.conf", f"userset {user_id} drcc")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(message, 'Send rclone.conf. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(add_rclone, pre_event=query)
        await event_handler(client, query, pfunc, document=True)
    elif data[2] == 'drcc':
        handler_dict[user_id] = False
        if await aiopath.exists(rclone_path):
            await query.answer()
            await aioremove(rclone_path)
            update_user_ldata(user_id, 'rclone', '')
            await update_user_settings(query)
            if DATABASE_URL:
                await DbManger().update_user_doc(user_id, 'rclone')
        else:
            await query.answer("Old Settings", show_alert=True)
            await update_user_settings(query)
    elif data[2] == 'lprefix':
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get('lprefix', False) or 'lprefix' not in user_dict and config_dict['LEECH_FILENAME_PREFIX']:
            buttons.ibutton("Remove Leech Prefix",
                            f"userset {user_id} rlprefix")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(message, 'Send Leech Filename Prefix. You can add HTML tags. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(set_prefix, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'rlprefix':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'lprefix', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'ldest':
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get('leech_dest', False) or 'leech_dest' not in user_dict and config_dict['LEECH_DUMP_CHAT']:
            buttons.ibutton("Remove Leech Destination",
                            f"userset {user_id} rldest")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(message, 'Send leech destination ID/USERNAME. Timeout: 60 sec', buttons.build_menu(1))
        pfunc = partial(set_leech_destination, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == 'rldest':
        handler_dict[user_id] = False
        await query.answer()
        update_user_ldata(user_id, 'leech_dest', '')
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManger().update_user_data(user_id)
    elif data[2] == 'back':
        handler_dict[user_id] = False
        await query.answer()
        await update_user_settings(query)
    else:
        handler_dict[user_id] = False
        await query.answer()
        await message.reply_to_message.delete()
        await message.delete()


async def send_users_settings(client, message):
    if user_data:
        msg = ''
        for u, d in user_data.items():
            kmsg = f'\n<b>{u}:</b>\n'
            if vmsg := ''.join(f'{k}: <code>{v}</code>\n' for k, v in d.items() if v):
                msg += kmsg + vmsg

        msg_ecd = msg.encode()
        if len(msg_ecd) > 4000:
            with BytesIO(msg_ecd) as ofile:
                ofile.name = 'users_settings.txt'
                await sendFile(message, ofile)
        else:
            await sendMessage(message, msg)
    else:
        await sendMessage(message, 'No users data!')


bot.add_handler(MessageHandler(send_users_settings, filters=command(
    BotCommands.UsersCommand) & CustomFilters.sudo))
bot.add_handler(MessageHandler(user_settings, filters=command(
    BotCommands.UserSetCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(
    edit_user_settings, filters=regex("^userset")))
