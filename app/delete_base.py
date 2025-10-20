import logging
import os
import re
import sys

from tgram import Telegram


class DeleteBase:
    _logger = None

    def __init__(self, config):
        self.config = config
        self.tg = Telegram(config)
        self.log = self.get_logger()

    @classmethod
    def get_logger(cls) -> logging.Logger:
        """
        Provide a shared logger configured for Cleanerr.
        Uses singleton pattern so all modules reuse the same logger instance.
        """
        if cls._logger is None:
            cls._logger = cls._configure_logger()
        return cls._logger

    @staticmethod
    def _configure_logger() -> logging.Logger:
        logger = logging.getLogger("cleanerr")
        log_level = os.getenv("LOG_LEVEL", "INFO").upper()
        level = getattr(logging, log_level, logging.INFO)
        logger.setLevel(level)

        if not logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(handler)

        logger.propagate = False
        return logger

    @staticmethod
    def _clean_title(item) -> str:
        title = re.sub(r"\s*\(\d{4}\)$", "", item["title"]).strip()
        return f"{title[:40]} ({item['year']})"
