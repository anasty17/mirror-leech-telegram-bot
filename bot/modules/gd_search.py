from .. import LOGGER, user_data
from ..helper.ext_utils.bot_utils import (
    sync_to_async,
    get_telegraph_list,
    new_task,
)
from ..helper.mirror_leech_utils.gdrive_utils.search import GoogleDriveSearch
from ..helper.telegram_helper.button_build import ButtonMaker
from ..helper.telegram_helper.message_utils import send_message, edit_message


def _parse_bool(value):
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    raise ValueError("Invalid boolean callback value")


async def list_buttons(user_id, is_recursive=True, user_token=False):
    buttons = ButtonMaker()
    buttons.data_button(
        "Folders", f"list_types {user_id} folders {is_recursive} {user_token}"
    )
    buttons.data_button(
        "Files", f"list_types {user_id} files {is_recursive} {user_token}"
    )
    buttons.data_button(
        "Both", f"list_types {user_id} both {is_recursive} {user_token}"
    )
    buttons.data_button(
        f"Recursive: {is_recursive}",
        f"list_types {user_id} rec {is_recursive} {user_token}",
    )
    buttons.data_button(
        f"User Token: {user_token}",
        f"list_types {user_id} ut {is_recursive} {user_token}",
    )
    buttons.data_button("Cancel", f"list_types {user_id} cancel")
    return buttons.build_menu(2)


async def _list_drive(key, message, item_type, is_recursive, user_token, user_id):
    LOGGER.info(f"listing: {key}")
    if user_token:
        user_dict = user_data.get(user_id, {})
        target_id = user_dict.get("GDRIVE_ID", "") or ""
        LOGGER.info(target_id)
    else:
        target_id = ""
    telegraph_content, contents_no = await sync_to_async(
        GoogleDriveSearch(is_recursive=is_recursive, item_type=item_type).drive_list,
        key,
        target_id,
        user_id,
    )
    if telegraph_content:
        try:
            button = await get_telegraph_list(telegraph_content)
        except Exception as e:
            await edit_message(message, e)
            return
        msg = f"<b>Found {contents_no} result for <i>{key}</i></b>"
        await edit_message(message, msg, button)
    else:
        await edit_message(message, f"No result found for <i>{key}</i>")


@new_task
async def select_type(_, query):
    user_id = query.from_user.id
    message = query.message
    data = query.data.split()
    if len(data) < 3:
        await query.answer(text="Invalid selection data.", show_alert=True)
        return
    if user_id != int(data[1]):
        await query.answer(text="Not Yours!", show_alert=True)
        return
    if data[2] == "cancel":
        await query.answer()
        await edit_message(message, "list has been canceled!")
        return
    if len(data) < 5:
        await query.answer(text="Invalid selection data.", show_alert=True)
        return
    try:
        is_recursive = _parse_bool(data[3])
        user_token = _parse_bool(data[4])
    except ValueError:
        await query.answer(text="Invalid selection data.", show_alert=True)
        return
    if data[2] == "rec":
        await query.answer()
        buttons = await list_buttons(user_id, not is_recursive, user_token)
        await edit_message(message, "Choose list options:", buttons)
        return
    if data[2] == "ut":
        await query.answer()
        buttons = await list_buttons(user_id, is_recursive, not user_token)
        await edit_message(message, "Choose list options:", buttons)
        return
    reply = message.reply_to_message
    if not reply or not reply.text or len(reply.text.split(maxsplit=1)) < 2:
        await query.answer(text="Search message is unavailable.", show_alert=True)
        return
    key = reply.text.split(maxsplit=1)[1].strip()
    await query.answer()
    await edit_message(message, f"<b>Searching for <i>{key}</i></b>")
    await _list_drive(key, message, data[2], is_recursive, user_token, user_id)


@new_task
async def gdrive_search(_, message):
    if len(message.text.split()) == 1:
        return await send_message(message, "Send a search key along with command")
    user_id = message.from_user.id
    buttons = await list_buttons(user_id)
    await send_message(message, "Choose list options:", buttons)
