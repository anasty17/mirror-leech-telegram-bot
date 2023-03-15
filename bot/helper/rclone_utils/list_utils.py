#!/usr/bin/env python3
from asyncio import wait_for, Event, wrap_future
from aiofiles.os import path as aiopath
from aiofiles import open as aiopen
from configparser import ConfigParser
from pyrogram.handlers import CallbackQueryHandler
from pyrogram.filters import regex, user
from functools import partial
from json import loads
from math import ceil

from bot.helper.telegram_helper.button_build import ButtonMaker
from bot.helper.telegram_helper.message_utils import sendMessage, editMessage
from ..ext_utils.bot_utils import cmd_exec, new_thread, get_readable_file_size, new_task

LIST_LIMIT = 6

@new_task
async def path_updates(client, query, obj):
    await query.answer()
    message = query.message
    data = query.data.split()
    if data[1] == 'pre':
        obj.iter_start -= LIST_LIMIT * obj.page_step
        await obj.get_path_buttons()
    elif data[1] == 'nex':
        obj.iter_start += LIST_LIMIT * obj.page_step
        await obj.get_path_buttons()
    elif data[1] == 'cancel':
        obj.path = ''
        obj.event.set()
        await message.delete()
    elif data[1] == 'back':
        if data[2] == 're':
            await obj.list_config()
        else:
            await obj.back_from_path()
    elif data[1] == 're':
        obj.path = data[2]
        await obj.get_path()
    elif data[1] == 'pa':
        index = int(data[3])
        obj.path = f"{obj.path}{obj.path_list[index]['Path']}" if obj.path.endswith(':') else f"{obj.path}/{obj.path_list[index]['Path']}"
        if data[2] == 'fo':
            await obj.get_path()
        else:
            await message.delete()
            obj.event.set()
    elif data[1] == 'ps':
        if obj.page_step == int(data[2]):
            return
        obj.page_step = int(data[2])
        await obj.get_path_buttons()
    elif data[1] == 'root':
        path = obj.path.split(':', 1)
        if '' in path:
            path.remove('')
        if len(path) > 1:
            obj.path = f"{path[0]}:"
            await obj.get_path()
    elif data[1] == 'cur':
        await message.delete()
        obj.event.set()
    elif data[1] == 'owner':
        obj.config_path = 'rclone.conf'
        await obj.list_remotes()
    elif data[1] == 'user':
        obj.config_path = obj.user_rcc_path
        await obj.list_remotes()

class RcloneHelper:
    def __init__(self, client, message):
        self.__user_id = message.from_user.id
        self.__rc_user = False
        self.__rc_owner = False
        self.__client = client
        self.__message = message
        self.__sections = []
        self.__reply_to = None
        self.event = Event()
        self.user_rcc_path = f'rclone/{self.__user_id}.conf'
        self.config_path = ''
        self.path = ''
        self.path_list = []
        self.iter_start = 0
        self.page_step = 1
        
    @new_thread
    async def __event_handler(self):
        pfunc = partial(path_updates, obj=self)
        handler = self.__client.add_handler(CallbackQueryHandler(pfunc, filters=regex('^rcq') & user(self.__user_id)), group=-1)
        try:
            await wait_for(self.event.wait(), timeout=240)
        except:
            self.path = ''
            self.event.set()
        self.__client.remove_handler(*handler)

    async def get_path_buttons(self):
        items_no = len(self.path_list)
        pages = ceil(items_no/LIST_LIMIT)
        if items_no <= self.iter_start:
            self.iter_start = 0
        elif self.iter_start < 0:
            self.iter_start = LIST_LIMIT * (pages - 1)
        page = (self.iter_start/LIST_LIMIT) + 1 if self.iter_start != 0 else 1
        buttons = ButtonMaker()
        for index, idict in enumerate(self.path_list[self.iter_start:LIST_LIMIT+self.iter_start]):
            orig_index = index + self.iter_start
            ptype = 'fo' if idict['IsDir'] else 'fi'
            name = idict['Path'] if idict['IsDir'] else f"[{get_readable_file_size(idict['Size'])}] {idict['Path']}"
            buttons.ibutton(name, f'rcq pa {ptype} {orig_index}')
        if items_no > LIST_LIMIT:
            for i in [1, 2, 4, 6, 8, 10]:
                buttons.ibutton(i, f'rcq ps {i}', position='header')
            buttons.ibutton('Previous', 'rcq pre', position='footer')
            buttons.ibutton('Next', 'rcq nex', position='footer')
        buttons.ibutton('Choose Current Path', 'rcq cur', position='footer')
        buttons.ibutton('Back', 'rcq back pa', position='footer')
        if len(self.path.split(':', 1)) > 1 and len(self.__sections) > 1 or self.__rc_user and self.__rc_owner:
            buttons.ibutton('Back To Root', 'rcq root', position='footer')
        buttons.ibutton('Cancel', 'rcq cancel', position='footer')
        button = buttons.build_menu(f_cols=2)
        msg = f'Choose Path:\n\nItems: {items_no} | Page: {int(page)}/{pages} | Page Step: {self.page_step}'
        msg += f'\n\nCurrent Path: <code>{self.path}</code>'
        if self.__reply_to is None:
            self.__reply_to = await sendMessage(self.__message, msg, button)
        else:
            await editMessage(self.__reply_to, msg, button)

    async def get_path(self):
        cmd = ['rclone', 'lsjson', f'--config={self.config_path}', self.path]
        res, _, code = await cmd_exec(cmd)
        if code != 0:
            self.path = 'Internal Error!'
            self.event.set()
        else:
            self.path_list = sorted(loads(res), key=lambda x: not x['IsDir'])
            self.iter_start = 0
            await self.get_path_buttons()

    async def list_remotes(self):
        config = ConfigParser()
        async with aiopen(self.config_path, 'r') as f:
            contents = await f.read()
            config.read_string(contents)
        self.__sections = config.sections()
        if len(self.__sections) == 1:
            self.path = f'{self.__sections[0]}:'
            await self.get_path()
        else:
            buttons = ButtonMaker()
            for remote in self.__sections:
                buttons.ibutton(remote, f'rcq re {remote}:')
            if self.__rc_user and self.__rc_owner:
                buttons.ibutton('Back', 'rcq back re')
            buttons.ibutton('Cancel', 'rcq cancel')
            button = buttons.build_menu(2)
            if self.__reply_to is None:
                self.__reply_to = await sendMessage(self.__message, 'Choose Rclone remote:', button)
            else:
                await editMessage(self.__reply_to, 'Choose Rclone remote:', button)

    async def list_config(self):
        if not self.__rc_owner and not self.__rc_user:
            return None
        elif self.__rc_user and self.__rc_owner:
            buttons = ButtonMaker()
            buttons.ibutton('Owner Config', 'rcq owner')
            buttons.ibutton('My Config', 'rcq user')
            buttons.ibutton('Cancel', 'rcq cancel')
            button = buttons.build_menu(2)
            if self.__reply_to is None:
                self.__reply_to = await sendMessage(self.__message, 'Choose Rclone config:', button)
            else:
                await editMessage(self.__reply_to, 'Choose Rclone config:', button)
        else:
            self.config_path = 'rclone.conf' if self.__rc_owner else self.user_rcc_path
            await self.list_remotes()
        return ''
    
    async def back_from_path(self):
        re_path = self.path.split(':', 1)
        if '' in re_path:
            re_path.remove('')
        if len(re_path) > 1:
            path = self.path.rsplit('/', 1)
            self.path = path[0] if len(path) > 1 else f'{re_path[0]}:'
            await self.get_path()
        elif len(self.__sections) > 1:
            await self.list_remotes()
        else:
            await self.list_config()

    async def get_rclone_path(self):
        future = self.__event_handler()
        self.__rc_user = await aiopath.exists(self.user_rcc_path)
        self.__rc_owner = await aiopath.exists('rclone.conf')
        path = await self.list_config()
        if path is None:
            self.event.set()
            return None, None
        await wrap_future(future)
        await self.__reply_to.delete()
        return self.config_path, self.path