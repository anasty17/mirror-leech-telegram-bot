#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from base64 import b64encode
from re import match as re_match
from asyncio import sleep
from aiofiles.os import path as aiopath

from bot import bot, DOWNLOAD_DIR, LOGGER, config_dict, user_data
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_mega_link, is_gdrive_link, get_content_type, new_task, sync_to_async, is_rclone_path, is_telegram_link, arg_parser, is_gdrive_id
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_utils.download_utils.gd_download import add_gd_download
from bot.helper.mirror_utils.download_utils.qbit_download import add_qb_torrent
from bot.helper.mirror_utils.download_utils.mega_download import add_mega_download
from bot.helper.mirror_utils.download_utils.rclone_download import add_rclone_download
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_utils.gdrive_utlis.list import gdriveList
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_download import TelegramDownloadHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage, get_tg_link_content
from bot.helper.listeners.task_listener import MirrorLeechListener
from bot.helper.ext_utils.help_messages import MIRROR_HELP_MESSAGE
from bot.helper.ext_utils.bulk_links import extract_bulk_links


@new_task
async def _mirror_leech(client, message, isQbit=False, isLeech=False, sameDir=None, bulk=[]):
    text = message.text.split('\n')
    input_list = text[0].split(' ')

    arg_base = {'link': '', '-i': 0, '-m': '', '-d': False, '-j': False, '-s': False, '-b': False,
                '-n': '', '-e': False, '-z': False, '-up': '', '-rcf': '', '-au': '', '-ap': ''}

    args = arg_parser(input_list[1:], arg_base)

    try:
        multi = int(args['-i'])
    except:
        multi = 0

    select = args['-s']
    seed = args['-d']
    isBulk = args['-b']
    folder_name = args['-m']
    name = args['-n']
    up = args['-up']
    rcf = args['-rcf']
    link = args['link']
    compress = args['-z']
    extract = args['-e']
    join = args['-j']

    bulk_start = 0
    bulk_end = 0
    ratio = None
    seed_time = None
    reply_to = None
    file_ = None
    session = ''

    if not isinstance(seed, bool):
        dargs = seed.split(':')
        ratio = dargs[0] or None
        if len(dargs) == 2:
            seed_time = dargs[1] or None
        seed = True

    if not isinstance(isBulk, bool):
        dargs = isBulk.split(':')
        bulk_start = dargs[0] or None
        if len(dargs) == 2:
            bulk_end = dargs[1] or None
        isBulk = True

    if folder_name and not isBulk:
        seed = False
        ratio = None
        seed_time = None
        folder_name = f'/{folder_name}'
        if sameDir is None:
            sameDir = {'total': multi, 'tasks': set(), 'name': folder_name}
        sameDir['tasks'].add(message.id)

    if isBulk:
        try:
            bulk = await extract_bulk_links(message, bulk_start, bulk_end)
            if len(bulk) == 0:
                raise ValueError('Bulk Empty!')
        except:
            await sendMessage(message, 'Reply to text file or tg message that have links seperated by new line!')
            return
        b_msg = input_list[:1]
        b_msg.append(f'{bulk[0]} -i {len(bulk)}')
        nextmsg = await sendMessage(message, " ".join(b_msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        nextmsg.from_user = message.from_user
        _mirror_leech(client, nextmsg, isQbit, isLeech, sameDir, bulk)
        return

    if len(bulk) != 0:
        del bulk[0]

    @new_task
    async def __run_multi():
        if multi <= 1:
            return
        await sleep(5)
        if len(bulk) != 0:
            msg = input_list[:1]
            msg.append(f'{bulk[0]} -i {multi - 1}')
            nextmsg = await sendMessage(message, " ".join(msg))
        else:
            msg = [s.strip() for s in input_list]
            index = msg.index('-i')
            msg[index+1] = f"{multi - 1}"
            nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
            nextmsg = await sendMessage(nextmsg, " ".join(msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        if folder_name:
            sameDir['tasks'].add(nextmsg.id)
        nextmsg.from_user = message.from_user
        await sleep(5)
        _mirror_leech(client, nextmsg, isQbit, isLeech, sameDir, bulk)

    __run_multi()

    path = f'{DOWNLOAD_DIR}{message.id}{folder_name}'

    if len(text) > 1 and text[1].startswith('Tag: '):
        tag, id_ = text[1].split('Tag: ')[1].split()
        message.from_user = await client.get_users(id_)
        try:
            await message.unpin()
        except:
            pass

    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if link and is_telegram_link(link):
        try:
            reply_to, session = await get_tg_link_content(link)
        except Exception as e:
            await sendMessage(message, f'ERROR: {e}')
            return
    elif not link and (reply_to := message.reply_to_message):
        if reply_to.text:
            reply_text = reply_to.text.split('\n', 1)[0].strip()
            if reply_text and is_telegram_link(reply_text):
                try:
                    reply_to, session = await get_tg_link_content(reply_text)
                except Exception as e:
                    await sendMessage(message, f'ERROR: {e}')
                    return

    if reply_to:
        file_ = reply_to.document or reply_to.photo or reply_to.video or reply_to.audio or \
            reply_to.voice or reply_to.video_note or reply_to.sticker or reply_to.animation or None

        if file_ is None:
            reply_text = reply_to.text.split('\n', 1)[0].strip()
            if is_url(reply_text) or is_magnet(reply_text):
                link = reply_text
        elif reply_to.document and (file_.mime_type == 'application/x-bittorrent' or file_.file_name.endswith('.torrent')):
            link = await reply_to.download()
            file_ = None

    if not is_url(link) and not is_magnet(link) and not await aiopath.exists(link) and not is_rclone_path(link) \
         and not is_gdrive_id(link) and file_ is None:
        await sendMessage(message, MIRROR_HELP_MESSAGE)
        return

    if link:
        LOGGER.info(link)

    if not is_mega_link(link) and not isQbit and not is_magnet(link) and not is_rclone_path(link) \
       and not is_gdrive_link(link) and not link.endswith('.torrent') and file_ is None and not is_gdrive_id(link):
        content_type = await get_content_type(link)
        if content_type is None or re_match(r'text/html|text/plain', content_type):
            try:
                link = await sync_to_async(direct_link_generator, link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    await sendMessage(message, str(e))
                    return

    user_id = message.from_user.id
    if not isLeech:
        user_dict = user_data.get(user_id, {})
        default_upload = user_dict.get('default_upload', '')
        if not up and (default_upload == 'rc' or not default_upload and config_dict['DEFAULT_UPLOAD'] == 'rc') or up == 'rc':
            up = user_dict.get('rclone_path') or config_dict['RCLONE_PATH']
        if not up and (default_upload == 'gd' or not default_upload and config_dict['DEFAULT_UPLOAD'] == 'gd') or up == 'gd':
            up = user_dict.get('gdrive_id') or config_dict['GDRIVE_ID']
        if not up:
            await sendMessage(message, 'No Upload Destination!')
            return
        elif up != 'rcl' and is_rclone_path(up):
            if up.startswith('mrcc:'):
                config_path = f'rclone/{user_id}.conf'
            else:
                config_path = 'rclone.conf'
            if not await aiopath.exists(config_path):
                await sendMessage(message, f"Rclone Config: {config_path} not Exists!")
                return
        elif up != 'gdl' and is_gdrive_id(up):
            if up.startswith('mtp:'):
                token_path = f'tokens/{user_id}.pickle'
            elif not config_dict['USE_SERVICE_ACCOUNTS']:
                token_path = 'token.pickle'
            else:
                token_path = 'accounts'
            if not await aiopath.exists(token_path):
                await sendMessage(message, f"token.pickle or service accounts: {token_path} not Exists!")
                return
        if not is_gdrive_id(up) and not is_rclone_path(up):
            await sendMessage(message, 'Wrong Upload Destination!')
            return

    if link == 'rcl':
        link = await RcloneList(client, message).get_rclone_path('rcd')
        if not is_rclone_path(link):
            await sendMessage(message, link)
            return
    elif link == 'gdl':
        link = await gdriveList(client, message).get_target_id('gdd')
        if not is_gdrive_id(link):
            await sendMessage(message, link)
            return

    if not isLeech:
        if up == 'rcl':
            up = await RcloneList(client, message).get_rclone_path('rcu')
            if not is_rclone_path(up):
                await sendMessage(message, up)
                return
        elif up == 'gdl':
            up = await gdriveList(client, message).get_target_id('gdu')
            if not is_gdrive_id(up):
                await sendMessage(message, up)
                return

    listener = MirrorLeechListener(
        message, compress, extract, isQbit, isLeech, tag, select, seed, sameDir, rcf, up, join)

    if file_ is not None:
        await TelegramDownloadHelper(listener).add_download(reply_to, f'{path}/', name, session)
    elif is_rclone_path(link):
        if link.startswith('mrcc:'):
            link = link.split('mrcc:', 1)[1]
            config_path = f'rclone/{user_id}.conf'
        else:
            config_path = 'rclone.conf'
        if not await aiopath.exists(config_path):
            await sendMessage(message, f"Rclone Config: {config_path} not Exists!")
            return
        await add_rclone_download(link, config_path, f'{path}/', name, listener)
    elif is_gdrive_link(link) or is_gdrive_id(link):
        await add_gd_download(link, path, listener, name)
    elif is_mega_link(link):
        await add_mega_download(link, f'{path}/', listener, name)
    elif isQbit:
        await add_qb_torrent(link, path, listener, ratio, seed_time)
    else:
        ussr = args['-au']
        pssw = args['-ap']
        if ussr or pssw:
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        await add_aria2c_download(link, path, listener, name, auth, ratio, seed_time)


async def mirror(client, message):
    _mirror_leech(client, message)


async def qb_mirror(client, message):
    _mirror_leech(client, message, isQbit=True)


async def leech(client, message):
    _mirror_leech(client, message, isLeech=True)


async def qb_leech(client, message):
    _mirror_leech(client, message, isQbit=True, isLeech=True)


bot.add_handler(MessageHandler(mirror, filters=command(
    BotCommands.MirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_mirror, filters=command(
    BotCommands.QbMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(leech, filters=command(
    BotCommands.LeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_leech, filters=command(
    BotCommands.QbLeechCommand) & CustomFilters.authorized))
