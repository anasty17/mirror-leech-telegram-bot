#Special thanks; FridayUserBot
import aiohttp
from bs4 import BeautifulSoup
import json
import re
from typing import Callable, Coroutine, Dict, List, Tuple, Union
from bot.helper.telegram_helper.bot_commands import BotCommands
from bot import app, bot
from pyrogram import filters, Client
from pyrogram.types import Chat, Message, User

def get_text(message: Message) -> [None, str]:
    """Extract Text From Commands"""
    text_to_return = message.text
    if message.text is None:
        return None
    if " " not in text_to_return:
        return None

    try:
        return message.text.split(None, 1)[1]
    except IndexError:
        return None


async def get_content(url):
    async with aiohttp.ClientSession() as session:
        r = await session.get(url)
        return await r.read()

@app.on_message(filters.command([BotCommands.ImdbCommand, f'{BotCommands.ImdbCommand}@{bot.username}']))
async def _(client, message):
    query = get_text(message)
    msg = await message.reply_text("`Searching For Movie..`")
    #reply = message.reply_to_message or message
    if not query:
        await msg.edit("`Please Give Me An Input.`")
        return
    url = "https://www.imdb.com/find?ref_=nv_sr_fn&q=" + query + "&s=all"
    r = await get_content(url)
    soup = BeautifulSoup(r, "lxml")
    o_ = soup.find("td", {"class": "result_text"})
    if not o_:
        return await msg.edit("`No Results Found, Matching Your Query.`")
    url = "https://www.imdb.com" + o_.find('a').get('href')
    resp = await get_content(url)
    b = BeautifulSoup(resp, "lxml")
    r_json = json.loads(b.find("script", attrs={"type": "application/ld+json"}).contents[0])
    res_str = "<b>#IMDBRESULT</b>"
    if r_json.get("@type"):
        res_str += f"\n<b>Type:</b> <code>{r_json['@type']}</code> \n"
    if r_json.get("name"):
        res_str += f"<b>Name:</b> {r_json['name']} \n"
    if r_json.get("contentRating"):
        res_str += f"<b>Content Rating :</b> <code>{r_json['contentRating']}</code> \n"
    if r_json.get("genre"):
        all_genre = r_json['genre']
        genre = "".join(f"{i}, " for i in all_genre)
        genre = genre[:-2]
        res_str += f"<b>Genres:</b> <code>{genre}</code> \n"
    if r_json.get("actor"):
        all_actors = r_json['actor']
        actors = "".join(f"{i['name']}, " for i in all_actors)
        actors = actors[:-2]
        res_str += f"<b>Actors:</b> <code>{actors}</code> \n"
    if r_json.get("trailer"):
        trailer_url = "https://imdb.com" + r_json['trailer']['embedUrl']
        res_str += f"<b>Trailer :</b> {trailer_url} \n"
    if r_json.get("description"):
        res_str += f"<b>Description:</b> <code>{r_json['description']}</code> \n"
    if r_json.get("keywords"):
        keywords = r_json['keywords'].split(",")
        key_ = ""
        for i in keywords:
            i = i.replace(" ", "_")
            key_ += f"#{i}, "
        key_ = key_[:-2]
        res_str += f"<b>Keywords / Tags :</b> {key_} \n"
    if r_json.get("datePublished"):
        res_str += f"<b>Date Published:</b> <code>{r_json['datePublished']}</code> \n"
    if r_json.get("aggregateRating"):
        res_str += f"<b>Rating Count:</b> <code>{r_json['aggregateRating']['ratingCount']}</code> \n<b>Rating Value:</b> <code>{r_json['aggregateRating']['ratingValue']}</code> \n"
    res_str += f"<b>URL :</b> {url}"
    thumb = r_json.get('image')
    if thumb:
        await msg.delete()
        return await message.reply_photo(thumb, caption=res_str)
    await msg.edit(res_str)  
