from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class ButtonMaker:
    def __init__(self):
        self.button = []
        self.header_button = []
        self.footer_button = []

    def buildbutton(self, key, link, footer=False, header=False):
        if not footer and not header:
            self.button.append(InlineKeyboardButton(text = key, url = link))
        elif header:
            self.header_button.append(InlineKeyboardButton(text = key, url = link))
        elif footer:
            self.footer_button.append(InlineKeyboardButton(text = key, url = link))

    def sbutton(self, key, data, footer=False, header=False):
        if not footer and not header:
            self.button.append(InlineKeyboardButton(text = key, callback_data = data))
        elif header:
            self.header_button.append(InlineKeyboardButton(text = key, callback_data = data))
        elif footer:
            self.footer_button.append(InlineKeyboardButton(text = key, callback_data = data))

    def build_menu(self, n_cols):
        menu = [self.button[i:i + n_cols] for i in range(0, len(self.button), n_cols)]
        if self.header_button:
            menu.insert(0, self.header_button)
        if self.footer_button:
            menu.append(self.footer_button)
        return InlineKeyboardMarkup(menu)
