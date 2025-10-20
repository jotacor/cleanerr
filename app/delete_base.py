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
        self._log = self.get_logger()

    def log(self, item_or_label, size_gb: float = 0.0, clean_title: bool = True, width: int = 50, filler: str = "_", level: str = "INFO") -> None:
        label = None
        if isinstance(item_or_label, dict) and clean_title:
            label = self._clean_title(item_or_label)
            size_gb = int(item_or_label["statistics"]["sizeOnDisk"] if 'statistics' in item_or_label else item_or_label["file_size"]) / 1073741824
        else:
            label = str(item_or_label)
            width = 0
            filler = ""

        entry = self._format_size_entry(label, size_gb, width, filler)
        self._log.info(entry)
        return size_gb

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

    @staticmethod
    def _format_size_entry(label: str, size_gb: float = 0.0, width: int = 50, filler: str = "_") -> str:
        label = label or ""
        padding = width - len(label)
        if padding < 1:
            padding = 1
        size = f"{size_gb:7.2f} GB" if size_gb != 0.0 else ''
        return f"{label}{filler * padding}{size}"
