#!/usr/bin/env python3
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from pyrogram.filters import command, regex
from asyncio import sleep
from re import split as re_split
from aiohttp import ClientSession

from bot import DOWNLOAD_DIR, bot, config_dict, user_data, LOGGER
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import get_readable_file_size, is_url, new_task, sync_to_async, new_task, is_rclone_path
from bot.helper.mirror_utils.download_utils.yt_dlp_download_helper import YoutubeDLHelper
from bot.helper.mirror_utils.rclone_utils.list import RcloneList
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.listeners.tasks_listener import MirrorLeechListener

listener_dict = {}


async def _mdisk(link, name):
    key = link.split('/')[-1]
    async with ClientSession() as session:
        async with session.get(f'https://diskuploader.entertainvideo.com/v1/file/cdnurl?param={key}') as resp:
            if resp.status == 200:
                resp_json = await resp.json()
                link = resp_json['source']
                if not name:
                    name = resp_json['filename']
            return name, link

async def _auto_cancel(msg, task_id):
    await sleep(120)
    try:
        del listener_dict[task_id]
        await editMessage(msg, 'Timed out! Task has been cancelled.')
    except:
        pass

@new_task
async def _ytdl(client, message, isZip=False, isLeech=False, sameDir={}):
    mssg = message.text
    user_id = message.from_user.id
    msg_id = message.id
    qual = ''
    select = False
    multi = 0
    link = ''
    folder_name = ''

    args = mssg.split(maxsplit=3)
    args.pop(0)
    if len(args) > 0:
        index = 1
        for x in args:
            x = x.strip()
            if x == 's':
               select = True
               index += 1
            elif x.strip().isdigit():
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
            args = mssg.split(maxsplit=index)
            if len(args) > index:
                x = args[index].strip()
                if not x.startswith(('n:', 'pswd:', 'up:', 'rcf:', 'opt:')):
                    link = re_split(r' opt: | pswd: | n: | rcf: | up: ', x)[0].strip()

    @new_task
    async def __run_multi():
        if multi <= 1:
            return
        await sleep(4)
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=message.reply_to_message_id + 1)
        ymsg = mssg.split(maxsplit=mi+1)
        ymsg[mi] = f"{multi - 1}"
        nextmsg = await sendMessage(nextmsg, " ".join(ymsg))
        nextmsg = await client.get_messages(chat_id=message.chat.id, message_ids=nextmsg.id)
        if len(folder_name) > 0:
            sameDir.add(nextmsg.id)
        nextmsg.from_user = message.from_user
        await sleep(4)
        _ytdl(client, nextmsg, isZip, isLeech, sameDir)

    path = f'{DOWNLOAD_DIR}{message.id}{folder_name}'

    name = mssg.split(' n: ', 1)
    name = re_split(' pswd: | opt: | up: | rcf: ', name[1])[0].strip() if len(name) > 1 else ''

    pswd = mssg.split(' pswd: ', 1)
    pswd = re_split(' n: | opt: | up: | rcf: ', pswd[1])[0] if len(pswd) > 1 else None

    opt = mssg.split(' opt: ', 1)
    opt = re_split(' n: | pswd: | up: | rcf: ', opt[1])[0].strip() if len(opt) > 1 else ''

    rcf = mssg.split(' rcf: ', 1)
    rcf = re_split(' n: | pswd: | up: | opt: ', rcf[1])[0].strip() if len(rcf) > 1 else None

    up = mssg.split(' up: ', 1)
    up = re_split(' n: | pswd: | rcf: | opt: ', up[1])[0].strip() if len(up) > 1 else None


    if username := message.from_user.username:
        tag = f"@{username}"
    else:
        tag = message.from_user.mention

    if reply_to := message.reply_to_message:
        if len(link) == 0:
            link = reply_to.text.split('\n', 1)[0].strip()
        if not reply_to.from_user.is_bot:
            if username := reply_to.from_user.username:
                tag = f"@{username}"
            else:
                tag = reply_to.from_user.mention

    if not is_url(link):
        help_msg = """
<b>Send link along with command line:</b>
<code>/cmd</code> s link n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>By replying to link:</b>
<code>/cmd</code> n: newname pswd: xx(zip) opt: x:y|x1:y1

<b>Quality Buttons:</b>
Incase default quality added but you need to select quality for specific link or links with multi links feature.
<code>/cmd</code> s link
This option should be always before n:, pswd: and opt:

<b>Options Example:</b> opt: playliststart:^10|matchtitle:S13|writesubtitles:true|live_from_start:true|postprocessor_args:{"ffmpeg": ["-threads", "4"]}|wait_for_video:(5, 100)

<b>Multi links only by replying to first link:</b>
<code>/cmd</code> 10(number of links)
Number should be always before n:, pswd: and opt:

<b>Multi links within same upload directory only by replying to first link:</b>
<code>/cmd</code> 10(number of links) m:folder_name
Number and m:folder_name should be always before n:, pswd: and opt:

<b>Options Note:</b> Add `^` before integer, some values must be integer and some string.
Like playlist_items:10 works with string, so no need to add `^` before the number but playlistend works only with integer so you must add `^` before the number like example above.
You can add tuple and dict also. Use double quotes inside dict.

<b>Upload</b>:
<code>/cmd</code> link up: <code>rcl</code> (To select rclone config, remote and path)
You can directly add the upload path. up: remote:dir/subdir
If DEFAULT_UPLOAD is `rc` then you can pass up: `gd` to upload using gdrive tools to GDRIVE_ID.
If DEFAULT_UPLOAD is `gd` then you can pass up: `rc` to upload to RCLONE_PATH.
If you want to add path manually from your config (uploaded from usetting) add <code>mrcc:</code> before the path without space
<code>/cmd</code> link up: <code>mrcc:</code>main:dump

<b>Rclone Flags</b>:
<code>/cmd</code> link up: path|rcl rcf: --buffer-size:8M|--drive-starred-only|key|key:value
This will override all other flags except --exclude
Check here all <a href='https://rclone.org/flags/'>RcloneFlags</a>.

<b>NOTES:</b>
1. When use cmd by reply don't add any option in link msg! Always add them after cmd msg!
2. Options (<b>s, m: and multi</b>) should be added randomly before link and before any other option.
3. Options (<b>n:, pswd: and opt:</b>) should be added randomly after the link if link along with the cmd or after cmd if by reply.
4. You can always add video quality from yt-dlp api options.

Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a>.
        """
        await sendMessage(message, help_msg)
        return

    if (up == 'rcl' or config_dict['RCLONE_PATH'] == 'rcl' and config_dict['DEFAULT_UPLOAD'] == 'rc') and not isLeech:
        up = await RcloneList(client, message).get_rclone_path('rcu')
        if not is_rclone_path(up):
            await sendMessage(message, up)
            return

    listener = MirrorLeechListener(message, isZip, isLeech=isLeech, pswd=pswd, tag=tag, sameDir=sameDir, rcFlags=rcf, upPath=up)
    if 'mdisk.me' in link:
        name, link = await _mdisk(link, name)
    ydl = YoutubeDLHelper(listener)
    try:
        result = await sync_to_async(ydl.extractMetaData, link, name, opt, True)
    except Exception as e:
        msg = str(e).replace('<', ' ').replace('>', ' ')
        await sendMessage(message, f"{tag} {msg}")
        __run_multi()
        return
    __run_multi()
    if not select:
        YTQ = config_dict['YT_DLP_QUALITY']
        user_dict = user_data.get(user_id, {})
        if 'format:' in opt:
            opts = opt.split('|')
            for f in opts:
                if f.startswith('format:'):
                    qual = f.split('format:', 1)[1]
        elif user_dict.get('yt_ql'):
            qual = user_dict['yt_ql']
        elif 'yt_ql' not in user_dict and YTQ:
            qual = YTQ
    if qual:
        playlist = 'entries' in result
        LOGGER.info(f"Downloading with YT-DLP: {link}")
        await ydl.add_download(link, path, name, qual, playlist, opt)
    else:
        buttons = ButtonMaker()
        best_video = "bv*+ba/b"
        best_audio = "ba/b"
        formats_dict = {}
        if 'entries' in result:
            for i in ['144', '240', '360', '480', '720', '1080', '1440', '2160']:
                video_format = f"bv*[height<=?{i}][ext=mp4]+ba[ext=m4a]/b[height<=?{i}]"
                b_data = f"{i}|mp4"
                formats_dict[b_data] = video_format
                buttons.ibutton(f"{i}-mp4", f"qu {msg_id} {b_data} t")
                video_format = f"bv*[height<=?{i}][ext=webm]+ba/b[height<=?{i}]"
                b_data = f"{i}|webm"
                formats_dict[b_data] = video_format
                buttons.ibutton(f"{i}-webm", f"qu {msg_id} {b_data} t")
            buttons.ibutton("MP3", f"qu {msg_id} mp3 t")
            buttons.ibutton("Best Videos", f"qu {msg_id} {best_video} t")
            buttons.ibutton("Best Audios", f"qu {msg_id} {best_audio} t")
            buttons.ibutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(3)
            bmsg = await sendMessage(message, 'Choose Playlist Videos Quality:', YTBUTTONS)
        else:
            formats = result.get('formats')
            is_m4a = False
            if formats is not None:
                for frmt in formats:
                    if frmt.get('tbr'):

                        format_id = frmt['format_id']

                        if frmt.get('filesize'):
                            size = frmt['filesize']
                        elif frmt.get('filesize_approx'):
                            size = frmt['filesize_approx']
                        else:
                            size = 0

                        if frmt.get('video_ext') == 'none' and frmt.get('acodec') != 'none':
                            if frmt.get('audio_ext') == 'm4a':
                                is_m4a = True
                            b_name = f"{frmt['acodec']}-{frmt['ext']}"
                            v_format = f"ba[format_id={format_id}]"
                        elif frmt.get('height'):
                            height = frmt['height']
                            ext = frmt['ext']
                            fps = frmt['fps'] if frmt.get('fps') else ''
                            b_name = f"{height}p{fps}-{ext}"
                            if ext == 'mp4':
                                ba_ext = '[ext=m4a]' if is_m4a else ''
                                v_format = f"bv*[format_id={format_id}]+ba{ba_ext}/b[height=?{height}]"
                            else:
                                v_format = f"bv*[format_id={format_id}]+ba/b[height=?{height}]"
                        else:
                            continue

                        if b_name in formats_dict:
                            formats_dict[b_name][str(frmt['tbr'])] = [size, v_format]
                        else:
                            formats_dict[b_name] = {str(frmt['tbr']): [size, v_format]}

                for b_name, d_dict in formats_dict.items():
                    if len(d_dict) == 1:
                        tbr, v_list = list(d_dict.items())[0]
                        buttonName = f"{b_name} ({get_readable_file_size(v_list[0])})"
                        buttons.ibutton(buttonName, f"qu {msg_id} {b_name}|{tbr}")
                    else:
                        buttons.ibutton(b_name, f"qu {msg_id} dict {b_name}")
            buttons.ibutton("MP3", f"qu {msg_id} mp3")
            buttons.ibutton("Best Video", f"qu {msg_id} {best_video}")
            buttons.ibutton("Best Audio", f"qu {msg_id} {best_audio}")
            buttons.ibutton("Cancel", f"qu {msg_id} cancel")
            YTBUTTONS = buttons.build_menu(2)
            bmsg = await sendMessage(message, 'Choose Video Quality:', YTBUTTONS)

        listener_dict[msg_id] = [listener, user_id, link, name, YTBUTTONS, opt, formats_dict, path]
        await _auto_cancel(bmsg, msg_id)

async def _qual_subbuttons(task_id, b_name, msg):
    buttons = ButtonMaker()
    task_info = listener_dict[task_id]
    formats_dict = task_info[6]
    for tbr, d_data in formats_dict[b_name].items():
        buttonName = f"{tbr}K ({get_readable_file_size(d_data[0])})"
        buttons.ibutton(buttonName, f"qu {task_id} {b_name}|{tbr}")
    buttons.ibutton("Back", f"qu {task_id} back")
    buttons.ibutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    await editMessage(msg, f"Choose Bit rate for <b>{b_name}</b>:", SUBBUTTONS)

async def _mp3_subbuttons(task_id, msg, playlist=False):
    buttons = ButtonMaker()
    audio_qualities = [64, 128, 320]
    for q in audio_qualities:
        if playlist:
            i = 's'
            audio_format = f"ba/b-{q} t"
        else:
            i = ''
            audio_format = f"ba/b-{q}"
        buttons.ibutton(f"{q}K-mp3", f"qu {task_id} {audio_format}")
    buttons.ibutton("Back", f"qu {task_id} back")
    buttons.ibutton("Cancel", f"qu {task_id} cancel")
    SUBBUTTONS = buttons.build_menu(2)
    await editMessage(msg, f"Choose Audio{i} Bitrate:", SUBBUTTONS)

@new_task
async def select_format(client, query):
    user_id = query.from_user.id
    data = query.data.split()
    message = query.message
    task_id = int(data[1])
    try:
        task_info = listener_dict[task_id]
    except:
        await editMessage(message, "This is an old task")
        return
    uid = task_info[1]
    if user_id != uid and not await CustomFilters.sudo(client, query):
        await query.answer(text="This task is not for you!", show_alert=True)
        return
    elif data[2] == "dict":
        await query.answer()
        b_name = data[3]
        await _qual_subbuttons(task_id, b_name, message)
        return
    elif data[2] == "back":
        await query.answer()
        await editMessage(message, 'Choose Video Quality:', task_info[4])
        return
    elif data[2] == "mp3":
        await query.answer()
        playlist = len(data) == 4
        await _mp3_subbuttons(task_id, message, playlist)
        return
    elif data[2] == "cancel":
        await query.answer()
        await editMessage(message, 'Task has been cancelled.')
        del listener_dict[task_id]
    else:
        await query.answer()
        listener = task_info[0]
        link = task_info[2]
        name = task_info[3]
        opt = task_info[5]
        qual = data[2]
        path = task_info[7]
        if len(data) == 4:
            playlist = True
            if '|' in qual:
                qual = task_info[6][qual]
        else:
            playlist = False
            if '|' in qual:
                b_name, tbr = qual.split('|')
                qual = task_info[6][b_name][tbr][1]
        ydl = YoutubeDLHelper(listener)
        LOGGER.info(f"Downloading with YT-DLP: {link}")
        await message.delete()
        del listener_dict[task_id]
        await ydl.add_download(link, path, name, qual, playlist, opt)

async def ytdl(client, message):
    _ytdl(client, message)

async def ytdlZip(client, message):
    _ytdl(client, message, True)

async def ytdlleech(client, message):
    _ytdl(client, message, isLeech=True)

async def ytdlZipleech(client, message):
    _ytdl(client, message, True, True)

bot.add_handler(MessageHandler(ytdl, filters=command(BotCommands.YtdlCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(ytdlZip, filters=command(BotCommands.YtdlZipCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(ytdlleech, filters=command(BotCommands.YtdlLeechCommand) & CustomFilters.authorized))
bot.add_handler(MessageHandler(ytdlZipleech, filters=command(BotCommands.YtdlZipLeechCommand) & CustomFilters.authorized))
bot.add_handler(CallbackQueryHandler(select_format, filters=regex("^qu")))
