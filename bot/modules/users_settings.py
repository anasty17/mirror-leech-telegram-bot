from aiofiles.os import remove, path as aiopath, makedirs
from asyncio import sleep
from functools import partial
from html import escape
from io import BytesIO
from os import getcwd
from pyrogram.filters import command, regex, create
from pyrogram.handlers import MessageHandler, CallbackQueryHandler
from time import time

from bot import (
    bot,
    IS_PREMIUM_USER,
    user_data,
    config_dict,
    DATABASE_URL,
    MAX_SPLIT_SIZE,
    GLOBAL_EXTENSION_FILTER,
)
from bot.helper.ext_utils.bot_utils import update_user_ldata, new_thread, getSizeBytes
from bot.helper.ext_utils.db_handler import DbManager
from bot.helper.ext_utils.media_utils import createThumb
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.filters import CustomFilters
from bot.helper.telegram_helper.message_utils import (
    sendMessage,
    editMessage,
    sendFile,
    deleteMessage,
)

handler_dict = {}


async def get_user_settings(from_user):
    user_id = from_user.id
    name = from_user.mention
    buttons = ButtonMaker()
    thumbpath = f"Thumbnails/{user_id}.jpg"
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    user_dict = user_data.get(user_id, {})

    if (
        user_dict.get("as_doc", False)
        or "as_doc" not in user_dict
        and config_dict["AS_DOCUMENT"]
    ):
        ltype = "DOCUMENT"
    else:
        ltype = "MEDIA"

    thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"

    if user_dict.get("split_size", False):
        split_size = user_dict["split_size"]
    else:
        split_size = config_dict["LEECH_SPLIT_SIZE"]

    if (
        user_dict.get("equal_splits", False)
        or "equal_splits" not in user_dict
        and config_dict["EQUAL_SPLITS"]
    ):
        equal_splits = "Enabled"
    else:
        equal_splits = "Disabled"

    if (
        user_dict.get("media_group", False)
        or "media_group" not in user_dict
        and config_dict["MEDIA_GROUP"]
    ):
        media_group = "Enabled"
    else:
        media_group = "Disabled"

    if user_dict.get("lprefix", False):
        lprefix = user_dict["lprefix"]
    elif "lprefix" not in user_dict and (LP := config_dict["LEECH_FILENAME_PREFIX"]):
        lprefix = LP
    else:
        lprefix = "None"

    if user_dict.get("leech_dest", False):
        leech_dest = user_dict["leech_dest"]
    elif "leech_dest" not in user_dict and (LD := config_dict["LEECH_DUMP_CHAT"]):
        leech_dest = LD
    else:
        leech_dest = "None"

    if (
        IS_PREMIUM_USER
        and user_dict.get("user_transmission", False)
        or "user_transmission" not in user_dict
        and config_dict["USER_TRANSMISSION"]
    ):
        leech_method = "user"
    else:
        leech_method = "bot"

    if (
        IS_PREMIUM_USER
        and user_dict.get("mixed_leech", False)
        or "mixed_leech" not in user_dict
        and config_dict["MIXED_LEECH"]
    ):
        mixed_leech = "Enabled"
    else:
        mixed_leech = "Disabled"

    buttons.ibutton("Leech", f"userset {user_id} leech")

    buttons.ibutton("Rclone", f"userset {user_id} rclone")
    rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
    if user_dict.get("rclone_path", False):
        rccpath = user_dict["rclone_path"]
    elif RP := config_dict["RCLONE_PATH"]:
        rccpath = RP
    else:
        rccpath = "None"

    buttons.ibutton("Gdrive Tools", f"userset {user_id} gdrive")
    tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
    if user_dict.get("gdrive_id", False):
        gdrive_id = user_dict["gdrive_id"]
    elif GI := config_dict["GDRIVE_ID"]:
        gdrive_id = GI
    else:
        gdrive_id = "None"
    index = user_dict["index_url"] if user_dict.get("index_url", False) else "None"
    if (
        user_dict.get("stop_duplicate", False)
        or "stop_duplicate" not in user_dict
        and config_dict["STOP_DUPLICATE"]
    ):
        sd_msg = "Enabled"
    else:
        sd_msg = "Disabled"

    upload_paths = "Added" if user_dict.get("upload_paths", False) else "None"
    buttons.ibutton("Upload Paths", f"userset {user_id} upload_paths")

    default_upload = (
        user_dict.get("default_upload", "") or config_dict["DEFAULT_UPLOAD"]
    )
    du = "Gdrive API" if default_upload == "gd" else "Rclone"
    dub = "Gdrive API" if default_upload != "gd" else "Rclone"
    buttons.ibutton(f"Upload using {dub}", f"userset {user_id} {default_upload}")

    buttons.ibutton("Excluded Extensions", f"userset {user_id} ex_ex")
    if user_dict.get("excluded_extensions", False):
        ex_ex = user_dict["excluded_extensions"]
    elif "excluded_extensions" not in user_dict and GLOBAL_EXTENSION_FILTER:
        ex_ex = GLOBAL_EXTENSION_FILTER
    else:
        ex_ex = "None"

    ns_msg = "Added" if user_dict.get("name_sub", False) else "None"
    buttons.ibutton("Name Subtitute", f"userset {user_id} name_subtitute")

    buttons.ibutton("YT-DLP Options", f"userset {user_id} yto")
    if user_dict.get("yt_opt", False):
        ytopt = user_dict["yt_opt"]
    elif "yt_opt" not in user_dict and (YTO := config_dict["YT_DLP_OPTIONS"]):
        ytopt = YTO
    else:
        ytopt = "None"

    if user_dict:
        buttons.ibutton("Reset All", f"userset {user_id} reset")

    buttons.ibutton("Close", f"userset {user_id} close")

    text = f"""<u>Settings for {name}</u>
Leech Type is <b>{ltype}</b>
Custom Thumbnail <b>{thumbmsg}</b>
Leech Split Size is <b>{split_size}</b>
Equal Splits is <b>{equal_splits}</b>
Media Group is <b>{media_group}</b>
Leech Prefix is <code>{escape(lprefix)}</code>
Leech Destination is <code>{leech_dest}</code>
Leech by <b>{leech_method}</b> session
Mixed Leech is <b>{mixed_leech}</b>
Rclone Config <b>{rccmsg}</b>
Rclone Path is <code>{rccpath}</code>
Gdrive Token <b>{tokenmsg}</b>
Upload Paths is <b>{upload_paths}</b>
Gdrive ID is <code>{gdrive_id}</code>
Index Link is <code>{index}</code>
Stop Duplicate is <b>{sd_msg}</b>
Default Upload is <b>{du}</b>
Name substitution is <b>{ns_msg}</b>
Excluded Extensions is <code>{ex_ex}</code>
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


async def set_thumb(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    des_dir = await createThumb(message, user_id)
    update_user_ldata(user_id, "thumb", des_dir)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "thumb", des_dir)


async def add_rclone(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    rpath = f"{getcwd()}/rclone/"
    await makedirs(rpath, exist_ok=True)
    des_dir = f"{rpath}{user_id}.conf"
    await message.download(file_name=des_dir)
    update_user_ldata(user_id, "rclone_config", f"rclone/{user_id}.conf")
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "rclone_config", des_dir)


async def add_token_pickle(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    tpath = f"{getcwd()}/tokens/"
    await makedirs(tpath, exist_ok=True)
    des_dir = f"{tpath}{user_id}.pickle"
    await message.download(file_name=des_dir)
    update_user_ldata(user_id, "token_pickle", f"tokens/{user_id}.pickle")
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "token_pickle", des_dir)


async def delete_path(_, message, pre_event):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    user_dict = user_data.get(user_id, {})
    names = message.text.split()
    for name in names:
        if name in user_dict["upload_paths"]:
            del user_dict["upload_paths"][name]
    new_value = user_dict["upload_paths"]
    update_user_ldata(user_id, "upload_paths", new_value)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_doc(user_id, "upload_paths", new_value)


async def set_option(_, message, pre_event, option):
    user_id = message.from_user.id
    handler_dict[user_id] = False
    value = message.text
    if option == "split_size":
        if not value.isdigit():
            value = getSizeBytes(value)
        value = min(int(value), MAX_SPLIT_SIZE)
    elif option == "leech_dest":
        if value.startswith("-") or value.isdigit():
            value = int(value)
    elif option == "excluded_extensions":
        fx = value.split()
        value = ["aria2", "!qB"]
        for x in fx:
            x = x.lstrip(".")
            value.append(x.strip().lower())
    elif option == "upload_paths":
        user_dict = user_data.get(user_id, {})
        user_dict.setdefault("upload_paths", {})
        lines = value.split("/n")
        for line in lines:
            name, path = line.split(maxsplit=1)
            user_dict["upload_paths"][name] = path
        value = user_dict["upload_paths"]
    update_user_ldata(user_id, option, value)
    await deleteMessage(message)
    await update_user_settings(pre_event)
    if DATABASE_URL:
        await DbManager().update_user_data(user_id)


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
        return bool(
            user.id == user_id and event.chat.id == query.message.chat.id and mtype
        )

    handler = client.add_handler(
        MessageHandler(pfunc, filters=create(event_filter)), group=-1
    )

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
    name = from_user.mention
    message = query.message
    data = query.data.split()
    handler_dict[user_id] = False
    thumb_path = f"Thumbnails/{user_id}.jpg"
    rclone_conf = f"rclone/{user_id}.conf"
    token_pickle = f"tokens/{user_id}.pickle"
    user_dict = user_data.get(user_id, {})
    if user_id != int(data[1]):
        await query.answer("Not Yours!", show_alert=True)
    elif data[2] in [
        "as_doc",
        "equal_splits",
        "media_group",
        "user_transmission",
        "stop_duplicate",
        "mixed_leech",
    ]:
        update_user_ldata(user_id, data[2], data[3] == "true")
        await query.answer()
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] in ["thumb", "rclone_config", "token_pickle"]:
        if data[2] == "thumb":
            fpath = thumb_path
        elif data[2] == "rclone_config":
            fpath = rclone_conf
        else:
            fpath = token_pickle
        if await aiopath.exists(fpath):
            await query.answer()
            await remove(fpath)
            update_user_ldata(user_id, data[2], "")
            await update_user_settings(query)
            if DATABASE_URL:
                await DbManager().update_user_doc(user_id, data[2])
        else:
            await query.answer("Old Settings", show_alert=True)
            await update_user_settings(query)
    elif data[2] in [
        "yt_opt",
        "lprefix",
        "index_url",
        "excluded_extensions",
        "name_sub",
    ]:
        await query.answer()
        update_user_ldata(user_id, data[2], "")
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] in ["split_size", "leech_dest", "rclone_path", "gdrive_id"]:
        await query.answer()
        if data[2] in user_data.get(user_id, {}):
            del user_data[user_id][data[2]]
            await update_user_settings(query)
            if DATABASE_URL:
                await DbManager().update_user_data(user_id)
    elif data[2] == "leech":
        await query.answer()
        thumbpath = f"Thumbnails/{user_id}.jpg"
        buttons = ButtonMaker()
        buttons.ibutton("Thumbnail", f"userset {user_id} sthumb")
        thumbmsg = "Exists" if await aiopath.exists(thumbpath) else "Not Exists"
        buttons.ibutton("Leech Split Size", f"userset {user_id} lss")
        if user_dict.get("split_size", False):
            split_size = user_dict["split_size"]
        else:
            split_size = config_dict["LEECH_SPLIT_SIZE"]
        buttons.ibutton("Leech Destination", f"userset {user_id} ldest")
        if user_dict.get("leech_dest", False):
            leech_dest = user_dict["leech_dest"]
        elif "leech_dest" not in user_dict and (LD := config_dict["LEECH_DUMP_CHAT"]):
            leech_dest = LD
        else:
            leech_dest = "None"
        buttons.ibutton("Leech Prefix", f"userset {user_id} leech_prefix")
        if user_dict.get("lprefix", False):
            lprefix = user_dict["lprefix"]
        elif "lprefix" not in user_dict and (
            LP := config_dict["LEECH_FILENAME_PREFIX"]
        ):
            lprefix = LP
        else:
            lprefix = "None"
        if (
            user_dict.get("as_doc", False)
            or "as_doc" not in user_dict
            and config_dict["AS_DOCUMENT"]
        ):
            ltype = "DOCUMENT"
            buttons.ibutton("Send As Media", f"userset {user_id} as_doc false")
        else:
            ltype = "MEDIA"
            buttons.ibutton("Send As Document", f"userset {user_id} as_doc true")
        if (
            user_dict.get("equal_splits", False)
            or "equal_splits" not in user_dict
            and config_dict["EQUAL_SPLITS"]
        ):
            buttons.ibutton(
                "Disable Equal Splits", f"userset {user_id} equal_splits false"
            )
            equal_splits = "Enabled"
        else:
            buttons.ibutton(
                "Enable Equal Splits", f"userset {user_id} equal_splits true"
            )
            equal_splits = "Disabled"
        if (
            user_dict.get("media_group", False)
            or "media_group" not in user_dict
            and config_dict["MEDIA_GROUP"]
        ):
            buttons.ibutton(
                "Disable Media Group", f"userset {user_id} media_group false"
            )
            media_group = "Enabled"
        else:
            buttons.ibutton("Enable Media Group", f"userset {user_id} media_group true")
            media_group = "Disabled"
        if (
            IS_PREMIUM_USER
            and user_dict.get("user_transmission", False)
            or "user_transmission" not in user_dict
            and config_dict["USER_TRANSMISSION"]
        ):
            buttons.ibutton(
                "Leech by Bot", f"userset {user_id} user_transmission false"
            )
            leech_method = "user"
        elif IS_PREMIUM_USER:
            leech_method = "bot"
            buttons.ibutton(
                "Leech by User", f"userset {user_id} user_transmission true"
            )
        else:
            leech_method = "bot"

        if (
            IS_PREMIUM_USER
            and user_dict.get("mixed_leech", False)
            or "mixed_leech" not in user_dict
            and config_dict["MIXED_LEECH"]
        ):
            mixed_leech = "Enabled"
            buttons.ibutton(
                "Disable Mixed Leech", f"userset {user_id} mixed_leech false"
            )
        elif IS_PREMIUM_USER:
            mixed_leech = "Disabled"
            buttons.ibutton(
                "Enable Mixed Leech", f"userset {user_id} mixed_leech true"
            )
        else:
            mixed_leech = "Disabled"

        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        text = f"""<u>Leech Settings for {name}</u>
Leech Type is <b>{ltype}</b>
Custom Thumbnail <b>{thumbmsg}</b>
Leech Split Size is <b>{split_size}</b>
Equal Splits is <b>{equal_splits}</b>
Media Group is <b>{media_group}</b>
Leech Prefix is <code>{escape(lprefix)}</code>
Leech Destination is <code>{leech_dest}</code>
Leech by <b>{leech_method}</b> session
Mixed Leech is <b>{mixed_leech}</b>
"""
        await editMessage(message, text, buttons.build_menu(2))
    elif data[2] == "rclone":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("Rclone Config", f"userset {user_id} rcc")
        buttons.ibutton("Default Rclone Path", f"userset {user_id} rcp")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        rccmsg = "Exists" if await aiopath.exists(rclone_conf) else "Not Exists"
        if user_dict.get("rclone_path", False):
            rccpath = user_dict["rclone_path"]
        elif RP := config_dict["RCLONE_PATH"]:
            rccpath = RP
        else:
            rccpath = "None"
        text = f"""<u>Rclone Settings for {name}</u>
Rclone Config <b>{rccmsg}</b>
Rclone Path is <code>{rccpath}</code>"""
        await editMessage(message, text, buttons.build_menu(1))
    elif data[2] == "gdrive":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("token.pickle", f"userset {user_id} token")
        buttons.ibutton("Default Gdrive ID", f"userset {user_id} gdid")
        buttons.ibutton("Index URL", f"userset {user_id} index")
        if (
            user_dict.get("stop_duplicate", False)
            or "stop_duplicate" not in user_dict
            and config_dict["STOP_DUPLICATE"]
        ):
            buttons.ibutton(
                "Disable Stop Duplicate", f"userset {user_id} stop_duplicate false"
            )
            sd_msg = "Enabled"
        else:
            buttons.ibutton(
                "Enable Stop Duplicate", f"userset {user_id} stop_duplicate true"
            )
            sd_msg = "Disabled"
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        tokenmsg = "Exists" if await aiopath.exists(token_pickle) else "Not Exists"
        if user_dict.get("gdrive_id", False):
            gdrive_id = user_dict["gdrive_id"]
        elif GDID := config_dict["GDRIVE_ID"]:
            gdrive_id = GDID
        else:
            gdrive_id = "None"
        index = user_dict["index_url"] if user_dict.get("index_url", False) else "None"
        text = f"""<u>Gdrive Tools Settings for {name}</u>
Gdrive Token <b>{tokenmsg}</b>
Gdrive ID is <code>{gdrive_id}</code>
Index URL is <code>{index}</code>
Stop Duplicate is <b>{sd_msg}</b>"""
        await editMessage(message, text, buttons.build_menu(1))
    elif data[2] == "vthumb":
        await query.answer()
        await sendFile(message, thumb_path, name)
        await update_user_settings(query)
    elif data[2] == "sthumb":
        await query.answer()
        buttons = ButtonMaker()
        if await aiopath.exists(thumb_path):
            buttons.ibutton("View Thumbnail", f"userset {user_id} vthumb")
            buttons.ibutton("Delete Thumbnail", f"userset {user_id} thumb")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send a photo to save it as custom thumbnail. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_thumb, pre_event=query)
        await event_handler(client, query, pfunc, True)
    elif data[2] == "yto":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get("yt_opt", False) or config_dict["YT_DLP_OPTIONS"]:
            buttons.ibutton(
                "Remove YT-DLP Options", f"userset {user_id} yt_opt", "header"
            )
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = """
Send YT-DLP Options. Timeout: 60 sec
Format: key:value|key:value|key:value.
Example: format:bv*+mergeall[vcodec=none]|nocheckcertificate:True
Check all yt-dlp api options from this <a href='https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/YoutubeDL.py#L184'>FILE</a> or use this <a href='https://t.me/mltb_official/177'>script</a> to convert cli arguments to api options.
        """
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=query, option="yt_opt")
        await event_handler(client, query, pfunc)
    elif data[2] == "lss":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get("split_size", False):
            buttons.ibutton("Reset Split Size", f"userset {user_id} split_size")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            f"Send Leech split size in bytes. IS_PREMIUM_USER: {IS_PREMIUM_USER}. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="split_size")
        await event_handler(client, query, pfunc)
    elif data[2] == "rcc":
        await query.answer()
        buttons = ButtonMaker()
        if await aiopath.exists(rclone_conf):
            buttons.ibutton("Delete rclone.conf", f"userset {user_id} rclone_config")
        buttons.ibutton("Back", f"userset {user_id} rclone")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message, "Send rclone.conf. Timeout: 60 sec", buttons.build_menu(1)
        )
        pfunc = partial(add_rclone, pre_event=query)
        await event_handler(client, query, pfunc, document=True)
    elif data[2] == "rcp":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get("rclone_path", False):
            buttons.ibutton("Reset Rclone Path", f"userset {user_id} rclone_path")
        buttons.ibutton("Back", f"userset {user_id} rclone")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Rclone Path. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=query, option="rclone_path")
        await event_handler(client, query, pfunc)
    elif data[2] == "token":
        await query.answer()
        buttons = ButtonMaker()
        if await aiopath.exists(token_pickle):
            buttons.ibutton("Delete token.pickle", f"userset {user_id} token_pickle")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message, "Send token.pickle. Timeout: 60 sec", buttons.build_menu(1)
        )
        pfunc = partial(add_token_pickle, pre_event=query)
        await event_handler(client, query, pfunc, document=True)
    elif data[2] == "gdid":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get("gdrive_id", False):
            buttons.ibutton("Reset Gdrive ID", f"userset {user_id} gdrive_id")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Gdrive ID. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=query, option="gdrive_id")
        await event_handler(client, query, pfunc)
    elif data[2] == "index":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get("index_url", False):
            buttons.ibutton("Remove Index URL", f"userset {user_id} index_url")
        buttons.ibutton("Back", f"userset {user_id} gdrive")
        buttons.ibutton("Close", f"userset {user_id} close")
        rmsg = "Send Index URL. Timeout: 60 sec"
        await editMessage(message, rmsg, buttons.build_menu(1))
        pfunc = partial(set_option, pre_event=query, option="index_url")
        await event_handler(client, query, pfunc)
    elif data[2] == "leech_prefix":
        await query.answer()
        buttons = ButtonMaker()
        if (
            user_dict.get("lprefix", False)
            or "lprefix" not in user_dict
            and config_dict["LEECH_FILENAME_PREFIX"]
        ):
            buttons.ibutton("Remove Leech Prefix", f"userset {user_id} lprefix")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send Leech Filename Prefix. You can add HTML tags. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="lprefix")
        await event_handler(client, query, pfunc)
    elif data[2] == "ldest":
        await query.answer()
        buttons = ButtonMaker()
        if (
            user_dict.get("leech_dest", False)
            or "leech_dest" not in user_dict
            and config_dict["LEECH_DUMP_CHAT"]
        ):
            buttons.ibutton("Reset Leech Destination", f"userset {user_id} leech_dest")
        buttons.ibutton("Back", f"userset {user_id} leech")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send leech destination ID/USERNAME/PM. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="leech_dest")
        await event_handler(client, query, pfunc)
    elif data[2] == "ex_ex":
        await query.answer()
        buttons = ButtonMaker()
        if (
            user_dict.get("excluded_extensions", False)
            or "excluded_extensions" not in user_dict
            and GLOBAL_EXTENSION_FILTER
        ):
            buttons.ibutton(
                "Remove Excluded Extensions", f"userset {user_id} excluded_extensions"
            )
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send exluded extenions seperated by space without dot at beginning. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="excluded_extensions")
        await event_handler(client, query, pfunc)
    elif data[2] == "name_subtitute":
        await query.answer()
        buttons = ButtonMaker()
        if user_dict.get(data[2], False):
            buttons.ibutton("Remove Name Subtitute", f"userset {user_id} name_sub")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        emsg = f"""Word Subtitions. You can add pattern instead of normal text. Timeout: 60 sec
Example: 'text : code : s|mirror : leech|tea :  : s|clone'

1. text will get replaced by code with sensitive case
2. mirror will get replaced by leech
4. tea will get removed with sensitive case
5. clone will get removed

Your Current Value is {user_dict.get('name_sub') or 'not added yet!'}
"""
        await editMessage(
            message,
            emsg,
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="name_sub")
        await event_handler(client, query, pfunc)
    elif data[2] in ["gd", "rc"]:
        await query.answer()
        du = "rc" if data[2] == "gd" else "gd"
        update_user_ldata(user_id, "default_upload", du)
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
    elif data[2] == "upload_paths":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("New Path", f"userset {user_id} new_path")
        if user_dict.get(data[2], False):
            buttons.ibutton("Show All Paths", f"userset {user_id} show_path")
            buttons.ibutton("Remove Path", f"userset {user_id} rm_path")
        buttons.ibutton("Back", f"userset {user_id} back")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Add or remove upload path.\n",
            buttons.build_menu(1),
        )
    elif data[2] == "new_path":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send path name(no space in name) which you will use it as a shortcut and the path/id seperated by space. You can add multiple names and paths separated by new line. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(set_option, pre_event=query, option="upload_paths")
        await event_handler(client, query, pfunc)
    elif data[2] == "rm_path":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        await editMessage(
            message,
            "Send paths names which you want to delete, separated by space. Timeout: 60 sec",
            buttons.build_menu(1),
        )
        pfunc = partial(delete_path, pre_event=query)
        await event_handler(client, query, pfunc)
    elif data[2] == "show_path":
        await query.answer()
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"userset {user_id} upload_paths")
        buttons.ibutton("Close", f"userset {user_id} close")
        user_dict = user_data.get(user_id, {})
        msg = "".join(
            f"<b>{key}</b>: <code>{value}</code>\n"
            for key, value in user_dict["upload_paths"].items()
        )
        await editMessage(
            message,
            msg,
            buttons.build_menu(1),
        )
    elif data[2] == "reset":
        await query.answer()
        if ud := user_data.get(user_id, {}):
            if ud and ("is_sudo" in ud or "is_auth" in ud):
                for k in list(ud.keys()):
                    if k not in ["is_sudo", "is_auth"]:
                        del user_data[user_id][k]
            else:
                user_data[user_id].clear()
        await update_user_settings(query)
        if DATABASE_URL:
            await DbManager().update_user_data(user_id)
        for fpath in [thumb_path, rclone_conf, token_pickle]:
            if await aiopath.exists(fpath):
                await remove(fpath)
    elif data[2] == "back":
        await query.answer()
        await update_user_settings(query)
    else:
        await query.answer()
        await deleteMessage(message.reply_to_message)
        await deleteMessage(message)


async def send_users_settings(_, message):
    if user_data:
        msg = ""
        for u, d in user_data.items():
            kmsg = f"\n<b>{u}:</b>\n"
            if vmsg := "".join(
                f"{k}: <code>{v}</code>\n" for k, v in d.items() if f"{v}"
            ):
                msg += kmsg + vmsg

        msg_ecd = msg.encode()
        if len(msg_ecd) > 4000:
            with BytesIO(msg_ecd) as ofile:
                ofile.name = "users_settings.txt"
                await sendFile(message, ofile)
        else:
            await sendMessage(message, msg)
    else:
        await sendMessage(message, "No users data!")


bot.add_handler(
    MessageHandler(
        send_users_settings,
        filters=command(BotCommands.UsersCommand) & CustomFilters.sudo,
    )
)
bot.add_handler(
    MessageHandler(
        user_settings,
        filters=command(BotCommands.UserSetCommand) & CustomFilters.authorized,
    )
)
bot.add_handler(CallbackQueryHandler(edit_user_settings, filters=regex("^userset")))
