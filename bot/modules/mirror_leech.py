#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler
from pyrogram.filters import command
from base64 import b64encode
from re import match as re_match, split as re_split
from asyncio import sleep
from aiofiles.os import path as aiopath

from bot import bot, DOWNLOAD_DIR, LOGGER, config_dict
from bot.helper.ext_utils.bot_utils import is_url, is_magnet, is_mega_link, is_gdrive_link, get_content_type, new_task, sync_to_async, is_rclone_path
from bot.helper.ext_utils.exceptions import DirectDownloadLinkException
from bot.helper.mirror_utils.download_utils.aria2_download import add_aria2c_download
from bot.helper.mirror_utils.download_utils.gd_downloader import add_gd_download
from bot.helper.mirror_utils.download_utils.qbit_downloader import add_qb_torrent
from bot.helper.mirror_utils.download_utils.mega_downloader import add_mega_download
from bot.helper.mirror_utils.rclone_utils.transfer import RcloneTransferHelper
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.mirror_utils.download_utils.direct_link_generator import direct_link_generator
from bot.helper.mirror_utils.download_utils.telegram_downloader import TelegramDownloadHelper
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import sendMessage
from bot.helper.listeners.tasks_listener import MirrorLeechListener


@new_task
async def _mirror_leech(client, message, isZip=False, extract=False, isQbit=False, isLeech=False, sameDir={}):
    mesg = message.text.split('\n')
    message_args = mesg[0].split(maxsplit=1)
    ratio = None
    seed_time = None
    select = False
    seed = False
    multi = 0
    link = ''
    folder_name = ''

    if len(message_args) > 1:
        index = 1
        args = mesg[0].split(maxsplit=4)
        args.pop(0)
        for x in args:
            x = x.strip()
            if x == 's':
               select = True
               index += 1
            elif x == 'd':
                seed = True
                index += 1
            elif x.startswith('d:'):
                seed = True
                index += 1
                dargs = x.split(':')
                ratio = dargs[1] or None
                if len(dargs) == 3:
                    seed_time = dargs[2] or None
            elif x.isdigit():
                multi = int(x)
                mi = index
            elif x.startswith('m:'):
                marg = x.split('m:', 1)
                if len(marg) > 1:
                    folder_name = f"/{marg[1]}"
                    if not sameDir:
                        sameDir = set()
                    sameDir.add(message.id)
            else:
                break
        if multi == 0:
            message_args = mesg[0].split(maxsplit=index)
            if len(message_args) > index:
                x = message_args[index].strip()
                if not x.startswith(('n:', 'pswd:', 'up:', 'rcf:')):
                    link = re_split(r' pswd: | n: | up: | rcf: ', x)[0].strip()

        if len(folder_name) > 0:
            seed = False
            ratio = None
            seed_time = None

    @new_task
    async def __run_multi():
        if multi <= 1:
            return
        await sleep(4)
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
        msg = message.text.split(maxsplit=mi+1)
        msg[mi] = f"{multi - 1}"
        nextmsg = await sendMessage(nextmsg, " ".join(msg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        if len(folder_name) > 0:
            sameDir.add(nextmsg.id)
        nextmsg.from_user = message.from_user
        await sleep(4)
        _mirror_leech(client, nextmsg, isZip, extract, isQbit, isLeech, sameDir)

    path = f'{DOWNLOAD_DIR}{message.id}{folder_name}'

    name = mesg[0].split(' n: ', 1)
    name = re_split(' pswd: | rcf: | up: ', name[1])[0].strip() if len(name) > 1 else ''

    pswd = mesg[0].split(' pswd: ', 1)
    pswd = re_split(' n: | rcf: | up: ', pswd[1])[0] if len(pswd) > 1 else None

    rcf = mesg[0].split(' rcf: ', 1)
    rcf = re_split(' n: | pswd: | up: ', rcf[1])[0].strip() if len(rcf) > 1 else None

    up = mesg[0].split(' up: ', 1)
    up = re_split(' n: | pswd: | rcf: ', up[1])[0].strip() if len(up) > 1 else None

    if len(mesg) > 1 and mesg[1].startswith('Tag: '):
        tag, id_ = mesg[1].split('Tag: ')[1].split()
        message.from_user = await client.get_users(id_)
        try:
            await message.unpin()
        except:
            pass
    elif username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    file_ = None
    if reply_to := message.reply_to_message:
        file_ = reply_to.document or reply_to.photo or reply_to.video or reply_to.audio or \
                 reply_to.voice or reply_to.video_note or reply_to.sticker or reply_to.animation or None
        if not reply_to.from_user.is_bot:
            if username := reply_to.from_user.username:
                tag = f"@{username}"
            else:
                tag = reply_to.from_user.mention
        if len(link) == 0 or not is_url(link) and not is_magnet(link):
            if file_ is None:
                reply_text = reply_to.text.split('\n', 1)[0].strip()
                if is_url(reply_text) or is_magnet(reply_text):
                    link = reply_text
            elif reply_to.document and (file_.mime_type == 'application/x-bittorrent' or file_.file_name.endswith('.torrent')):
                link = await reply_to.download()
                file_ = None

    if not is_url(link) and not is_magnet(link) and not await aiopath.exists(link) and not is_rclone_path(link) and file_ is None:
        help_msg = '''
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)

<b>By replying to link/file:</b>
<code>/cmd</code> n: newname pswd: xx(zip/unzip)

<b>Direct link authorization:</b>
<code>/cmd</code> link n: newname pswd: xx(zip/unzip)
<b>username</b>
<b>password</b>

<b>Bittorrent selection:</b>
<code>/cmd</code> <b>s</b> link or by replying to file/link
This option should be always before n: or pswd:

<b>Bittorrent seed</b>:
<code>/cmd</code> <b>d</b> link or by replying to file/link
To specify ratio and seed time add d:ratio:time. Ex: d:0.7:10 (ratio and time) or d:0.7 (only ratio) or d::10 (only time) where time in minutes.
Those options should be always before n: or pswd:

<b>Multi links only by replying to first link/file:</b>
<code>/cmd</code> 10(number of links/files)
Number should be always before n: or pswd:

<b>Multi links within same upload directory only by replying to first link/file:</b>
<code>/cmd</code> 10(number of links/files) m:folder_name
Number and m:folder_name (folder_name without space) should be always before n: or pswd:

<b>Rclone Download</b>:
Treat rclone paths exactly like links
<code>/cmd</code> main:dump/ubuntu.iso or <code>rcl</code> (To select config, remote and path)
Users can add their own rclone from user settings
If you want to add path manually from your config add <code>mrcc:</code> before the path without space
<code>/cmd</code> <code>mrcc:</code>main:/dump/ubuntu.iso

<b>Upload</b>:
<code>/cmd</code> link up: <code>rcl</code> (To select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>Rclone Flags</b>:
<code>/cmd</code> link|path|rcl up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>NOTES:</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>n: and pswd:</b>) should be added randomly after the link if link along with the cmd and after any other option
3. Options (<b>d, s, m: and multi</b>) should be added randomly before the link and before any other option.
4. Commands that start with <b>qb</b> are ONLY for torrents.
5. (n:) option doesn't work with torrents. 
'''
        await sendMessage(message, help_msg)
        return
    
    if link:
        LOGGER.info(link)

    if not is_mega_link(link) and not isQbit and not is_magnet(link) and not is_rclone_path(link) \
       and not is_gdrive_link(link) and not link.endswith('.torrent') and file_ is None:
        content_type = await sync_to_async(get_content_type, link)
        if content_type is None or re_match(r'text/html|text/plain', content_type):
            try:
                link = await sync_to_async(direct_link_generator, link)
                LOGGER.info(f"Generated link: {link}")
            except DirectDownloadLinkException as e:
                LOGGER.info(str(e))
                if str(e).startswith('ERROR:'):
                    await sendMessage(message, str(e))
                    __run_multi()
                    return
    __run_multi()

    if link == 'rcl':
        link = await RcloneList(client, message).get_rclone_path('rcd')
        if not is_rclone_path(link):
            await sendMessage(message, link)
            return
    if (up == 'rcl' or config_dict['RCLONE_PATH'] == 'rcl' and config_dict['DEFAULT_UPLOAD'] == 'rc') and not isLeech:
        up = await RcloneList(client, message).get_rclone_path('rcu')
        if not is_rclone_path(up):
            await sendMessage(message, up)
            return

    listener = MirrorLeechListener(message, isZip, extract, isQbit, isLeech, pswd, tag, select, seed, sameDir, rcf, up)

    if file_ is not None:
        await TelegramDownloadHelper(listener).add_download(reply_to, f'{path}/', name)
    elif is_rclone_path(link):
        if link.startswith('mrcc:'):
            link = link.split('mrcc:', 1)[1]
            config_path = f'rclone/{message.from_user.id}.conf'
        else:
            config_path = 'rclone.conf'
        if not await aiopath.exists(config_path):
            await sendMessage(message, f"Rclone Config: {config_path} not Exists!")
            return
        await RcloneTransferHelper(listener).add_download(link, config_path, f'{path}/', name)
    elif is_gdrive_link(link):
        if not isZip and not extract and not isLeech:
            gmsg = f"Use /{BotCommands.CloneCommand} to clone Google Drive file/folder\n\n"
            gmsg += f"Use /{BotCommands.ZipMirrorCommand[0]} to make zip of Google Drive folder\n\n"
            gmsg += f"Use /{BotCommands.UnzipMirrorCommand[0]} to extracts Google Drive archive folder/file"
            await sendMessage(message, gmsg)
        else:
            await add_gd_download(link, path, listener, name)
    elif is_mega_link(link):
        await add_mega_download(link, f'{path}/', listener, name)
    elif isQbit:
        await add_qb_torrent(link, path, listener, ratio, seed_time)
    else:
        if len(mesg) > 1 and not mesg[1].startswith('Tag:'):
            ussr = mesg[1]
            pssw = mesg[2] if len(mesg) > 2 else ''
            auth = f"{ussr}:{pssw}"
            auth = "Basic " + b64encode(auth.encode()).decode('ascii')
        else:
            auth = ''
        await add_aria2c_download(link, path, listener, name, auth, ratio, seed_time)


async def mirror(client, message):
    _mirror_leech(client, message)

async def unzip_mirror(client, message):
    _mirror_leech(client, message, extract=True)

async def zip_mirror(client, message):
    _mirror_leech(client, message, True)

async def qb_mirror(client, message):
    _mirror_leech(client, message, isQbit=True)

async def qb_unzip_mirror(client, message):
    _mirror_leech(client, message, extract=True, isQbit=True)

async def qb_zip_mirror(client, message):
    _mirror_leech(client, message, True, isQbit=True)

async def leech(client, message):
    _mirror_leech(client, message, isLeech=True)

async def unzip_leech(client, message):
    _mirror_leech(client, message, extract=True, isLeech=True)

async def zip_leech(client, message):
    _mirror_leech(client, message, True, isLeech=True)

async def qb_leech(client, message):
    _mirror_leech(client, message, isQbit=True, isLeech=True)

async def qb_unzip_leech(client, message):
    _mirror_leech(client, message, extract=True, isQbit=True, isLeech=True)

async def qb_zip_leech(client, message):
    _mirror_leech(client, message, True, isQbit=True, isLeech=True)


bot.add_handler(MessageHandler(mirror, filters=command(BotCommands.MirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(unzip_mirror, filters=command(BotCommands.UnzipMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(zip_mirror, filters=command(BotCommands.ZipMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_mirror, filters=command(BotCommands.QbMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_unzip_mirror, filters=command(BotCommands.QbUnzipMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_zip_mirror, filters=command(BotCommands.QbZipMirrorCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(leech, filters=command(BotCommands.LeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(unzip_leech, filters=command(BotCommands.UnzipLeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(zip_leech, filters=command(BotCommands.ZipLeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_leech, filters=command(BotCommands.QbLeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_unzip_leech, filters=command(BotCommands.QbUnzipLeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(qb_zip_leech, filters=command(BotCommands.QbZipLeechCommand) & CustomFilters.authorized))
