# Source:https://github.com/khainee/rclone-mirror-leech-telegram-bot/blob/master/bot/modules/bulk.py
from asyncio import sleep
from bot import LOGGER, bot, botloop
from pyrogram.handlers import MessageHandler
from pyrogram import filters
from bot.helper.ext_utils.bot_commands import BotCommands
from bot.helper.ext_utils.filters import CustomFilters
from bot.helper.ext_utils.message_utils import sendMessage
from os import path as ospath
from subprocess import run as srun
from bot.modules.mirror_leech import mirror_leech


async def bulk_mirror(client, message):
    await bulk(client, message)
    
async def bulk_leech(client, message):
    await bulk(client, message, isLeech=True)

async def bulk(client, message, isLeech=False):
    user_id= message.from_user.id
    question= await client.send_message(message.chat.id, text= "Send links separated each link by new line or send a txt file, /ignore to cancel")
    try:
        response = await client.listen.Message(filters.document | filters.text, id= filters.user(user_id), timeout = 60)
    except TimeoutError:
        await client.send_message(message.chat.id, text="Too late 60s gone, try again!")
    else:
        try:
            if response.text:
                if "/ignore" in response.text:
                    await client.listen.Cancel(filters.user(user_id))
                else:
                    lines= response.text.split("\n")  
                    count= 0
                    for link in lines:
                        link.strip()
                        if link != "\n":
                            count += 1
                        if len(link) > 1:
                            if isLeech:
                                msg= await bot.send_message(message.chat.id, f"/leech {link}", disable_web_page_preview=True)
                            else:
                                msg= await bot.send_message(message.chat.id, f"/mirror {link}", disable_web_page_preview=True)
                            msg = await client.get_messages(message.chat.id, msg.id)
                            msg.from_user.id = message.from_user.id
                            botloop.create_task(mirror_leech(client, msg, isLeech=isLeech))
                            await sleep(4)
            else:
                file_name = response.document.file_name
                ext= file_name.split(".")[1]
                count= 0
                if ext in ["txt", ".txt"]:
                    if ospath.exists("./links.txt"):
                        srun(["rm", "-rf", "links.txt"])
                    await client.download_media(response, file_name="./links.txt")
                    with open('links.txt', 'r+') as f:
                        lines = f.readlines()
                        for link in lines:
                            link.strip()
                            if link != "\n":
                                count += 1
                            if len(link) > 1:
                                if isLeech:
                                    msg= await bot.send_message(message.chat.id, f"/leech {link}", disable_web_page_preview=True)
                                else:
                                    msg= await bot.send_message(message.chat.id, f"/mirror {link}", disable_web_page_preview=True)
                                msg = await client.get_messages(message.chat.id, msg.id)
                                msg.from_user.id = message.from_user.id
                                botloop.create_task(mirror_leech(client, msg, isLeech=isLeech))
                                await sleep(4)
                else:
                    await sendMessage("Send a txt file", message)
        except Exception as ex:
            await sendMessage(str(ex), message) 
    finally:
        await question.delete()

bulk_mirror_handler = MessageHandler(bulk_mirror, filters= filters.command(BotCommands.BulkCommand) & (CustomFilters.owner_filter | CustomFilters.chat_filter))
bot.add_handler(bulk_mirror_handler)

bulk_leech_handler = MessageHandler(bulk_leech, filters= filters.command(BotCommands.BulkLeechCommand) & (CustomFilters.owner_filter | CustomFilters.chat_filter))
bot.add_handler(bulk_leech_handler)
        
