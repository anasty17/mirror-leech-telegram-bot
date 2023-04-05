from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton


class ButtonMaker:
    def __init__(self):
        self.__button = []
        self.__header_button = []
        self.__footer_button = []

    def ubutton(self, key, link, position=None):
        if not position:
            self.__button.append(InlineKeyboardButton(text=key, url=link))
        elif position == 'header':
            self.__header_button.append(
                InlineKeyboardButton(text=key, url=link))
        elif position == 'footer':
            self.__footer_button.append(
                InlineKeyboardButton(text=key, url=link))

    def ibutton(self, key, data, position=None):
        if not position:
            self.__button.append(InlineKeyboardButton(
                text=key, callback_data=data))
        elif position == 'header':
            self.__header_button.append(
                InlineKeyboardButton(text=key, callback_data=data))
        elif position == 'footer':
            self.__footer_button.append(
                InlineKeyboardButton(text=key, callback_data=data))

    def build_menu(self, b_cols=1, h_cols=8, f_cols=8):
        menu = [self.__button[i:i+b_cols]
                for i in range(0, len(self.__button), b_cols)]
        if self.__header_button:
            h_cnt = len(self.__header_button)
            if h_cnt > h_cols:
                header_buttons = [self.__header_button[i:i+h_cols]
                                  for i in range(0, len(self.__header_button), h_cols)]
                menu = header_buttons + menu
            else:
                menu.insert(0, self.__header_button)
        if self.__footer_button:
            if len(self.__footer_button) > f_cols:
                [menu.append(self.__footer_button[i:i+f_cols])
                 for i in range(0, len(self.__footer_button), f_cols)]
            else:
                menu.append(self.__footer_button)
        return InlineKeyboardMarkup(menu)
