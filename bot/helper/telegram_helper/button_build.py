from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class ButtonMaker:
    def __init__(self):
        self.button = []

    def buildbutton(self, key, link):
        self.button.append(InlineKeyboardButton(text = key, url = link))

    def sbutton(self, key, data):
        self.button.append(InlineKeyboardButton(text = key, callback_data = data))

    def build_menu(self, n_cols, footer_buttons=None, header_buttons=None):
        menu = [self.button[i:i + n_cols] for i in range(0, len(self.button), n_cols)]
        if header_buttons:
            menu.insert(0, header_buttons)
        if footer_buttons:
            menu.append(footer_buttons)
        return InlineKeyboardMarkup(menu)
