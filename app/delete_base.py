import re
from tgram import Telegram


class DeleteBase:
    def __init__(self, config):
        self.config = config
        self.tg = Telegram(config)

    @staticmethod
    def _clean_title(item) -> str:
        title = re.sub(r"\s*\(\d{4}\)$", "", item["title"]).strip()
        return f"{title[:40]} ({item['year']})"
