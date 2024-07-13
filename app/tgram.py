import telegram
import asyncio


class Telegram:
    def __init__(self, config):
        self.telegram_chat_id = config.telegram_chat_id
        self.bot = None
        if config.telegram_token and config.telegram_chat_id:
            self.bot = telegram.Bot(token=config.telegram_token)

    def send_message(self, msg):
      if self.bot:
        asyncio.run(self.bot.sendMessage(chat_id=self.telegram_chat_id, text=msg))
