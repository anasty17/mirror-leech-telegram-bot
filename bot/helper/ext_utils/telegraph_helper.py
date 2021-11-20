# Implement By - @VarnaX-279

import time
import string
import random
import logging

from telegraph import Telegraph
from telegraph.exceptions import RetryAfterError


logger = logging.getLogger('TelegraphHelper')


class TelegraphHelper():
	def __init__(self, short_name=None, author_name=None, author_url=None):
		self.telegraph = Telegraph()
		if short_name:
			self.short_name = short_name
		else:
			self.short_name = ''.join(random.SystemRandom().choices(string.ascii_letters, k=8))
		self.access_token = None
		self.author_name = author_name
		self.author_url = author_url
		self.regenerate_token = self.create_account
		self.create_account()

	def create_account(self):
		self.telegraph.create_account(
			short_name=self.short_name,
			author_name=self.author_name,
			author_url=self.author_url
		)
		self.access_token = self.telegraph.get_access_token()
		logger.info("Creating TELEGRAPH Account using  '" + self.short_name + "' name")

	def create_page(self, title, content):
		try:
			result = self.telegraph.create_page(
				title = title,
				author_name=self.author_name,
				author_url=self.author_url,
				html_content=content
			)
			return result
		except RetryAfterError as st:
			logger.warning(f'Flood control exceeded. I will sleep for {st.retry_after} seconds.')
			time.sleep(st.retry_after)
			return self.create_page(title, content)

	def edit_page(self, path, title, content):
		try:
			result = self.telegraph.edit_page(
				path = path,
				title = title,
				author_name=self.author_name,
				author_url=self.author_url,
				html_content=content
			)
			return result
		except RetryAfterError as st:
			logger.warning(f'Flood control exceeded. I will sleep for {st.retry_after} seconds.')
			time.sleep(st.retry_after)
			return self.edit_page(path, title, content)


telegraph=TelegraphHelper(author_name='Mirror-Leech-Telegram-Bot', author_url='https://github.com/anasty17/mirror-leech-telegram-bot')