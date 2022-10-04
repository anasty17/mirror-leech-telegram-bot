from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class ButtonMaker:
    def __init__(self):
        self.__button = []
        self.__header_button = []
        self.__footer_button = []

    def buildbutton(self, key, link, position=None):
        if not position:
            self.__button.append(InlineKeyboardButton(text = key, url = link))
        elif position == 'header':
            self.__header_button.append(InlineKeyboardButton(text = key, url = link))
        elif position == 'footer':
            self.__footer_button.append(InlineKeyboardButton(text = key, url = link))

    def sbutton(self, key, data, position=None):
        if not position:
            self.__button.append(InlineKeyboardButton(text = key, callback_data = data))
        elif position == 'header':
            self.__header_button.append(InlineKeyboardButton(text = key, callback_data = data))
        elif position == 'footer':
            self.__footer_button.append(InlineKeyboardButton(text = key, callback_data = data))

    def build_menu(self, n_cols):
        menu = [self.__button[i:i + n_cols] for i in range(0, len(self.__button), n_cols)]
        if self.__header_button:
            menu.insert(0, self.__header_button)
        if self.__footer_button:
            menu.append(self.__footer_button)
        return InlineKeyboardMarkup(menu)
