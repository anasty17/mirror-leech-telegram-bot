#!/usr/bin/env python3
from string import ascii_letters
from random import SystemRandom
from asyncio import sleep
from telegraph.aio import Telegraph
from telegraph.exceptions import RetryAfterError

from bot import LOGGER, bot_loop


class TelegraphHelper:
    def __init__(self, author_name=None, author_url=None):
        self.telegraph = Telegraph(domain='graph.org')
        self.short_name = ''.join(SystemRandom().choices(ascii_letters, k=8))
        self.access_token = None
        self.author_name = author_name
        self.author_url = author_url

    async def create_account(self):
        await self.telegraph.create_account(
            short_name=self.short_name,
            author_name=self.author_name,
            author_url=self.author_url
        )
        self.access_token = self.telegraph.get_access_token()
        LOGGER.info("Creating Telegraph Account")

    async def create_page(self, title, content):
        try:
            return await self.telegraph.create_page(
                title=title,
                author_name=self.author_name,
                author_url=self.author_url,
                html_content=content
            )
        except RetryAfterError as st:
            LOGGER.warning(
                f'Telegraph Flood control exceeded. I will sleep for {st.retry_after} seconds.')
            await sleep(st.retry_after)
            return await self.create_page(title, content)

    async def edit_page(self, path, title, content):
        try:
            return await self.telegraph.edit_page(
                path=path,
                title=title,
                author_name=self.author_name,
                author_url=self.author_url,
                html_content=content
            )
        except RetryAfterError as st:
            LOGGER.warning(
                f'Telegraph Flood control exceeded. I will sleep for {st.retry_after} seconds.')
            await sleep(st.retry_after)
            return await self.edit_page(path, title, content)

    async def edit_telegraph(self, path, telegraph_content):
        nxt_page = 1
        prev_page = 0
        num_of_path = len(path)
        for content in telegraph_content:
            if nxt_page == 1:
                content += f'<b><a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
                nxt_page += 1
            else:
                if prev_page <= num_of_path:
                    content += f'<b><a href="https://telegra.ph/{path[prev_page]}">Prev</a></b>'
                    prev_page += 1
                if nxt_page < num_of_path:
                    content += f'<b> | <a href="https://telegra.ph/{path[nxt_page]}">Next</a></b>'
                    nxt_page += 1
            await self.edit_page(
                path=path[prev_page],
                title='Mirror-leech-bot Torrent Search',
                content=content
            )
        return


telegraph = TelegraphHelper('Mirror-Leech-Telegram-Bot',
                            'https://github.com/anasty17/mirror-leech-telegram-bot')

bot_loop.run_until_complete(telegraph.create_account())
