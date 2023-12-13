from pyrogram.handlers import CallbackQueryHandler
from pyrogram.filters import regex

from bot import bot
from bot.helper.telegram_helper.message_utils import editMessage, deleteMessage
from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.ext_utils.bot_utils import COMMAND_USAGE
from bot.helper.ext_utils.help_messages import YT_HELP_DICT, MIRROR_HELP_DICT


async def argUsage(_, query):
    data = query.data.split()
    message = query.message
    if data[1] == "close":
        await deleteMessage(message)
    elif data[1] == "back":
        if data[2] == "m":
            await editMessage(
                message, COMMAND_USAGE["mirror"][0], COMMAND_USAGE["mirror"][1]
            )
        else:
            await editMessage(message, COMMAND_USAGE["yt"][0], COMMAND_USAGE["yt"][1])
    elif data[1] == "m":
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"help back m")
        button = buttons.build_menu()
        await editMessage(message, MIRROR_HELP_DICT[data[2]], button)
    elif data[1] == "yt":
        buttons = ButtonMaker()
        buttons.ibutton("Back", f"help back m")
        button = buttons.build_menu()
        await editMessage(message, YT_HELP_DICT[data[2]], button)


bot.add_handler(CallbackQueryHandler(argUsage, filters=regex("^help")))
