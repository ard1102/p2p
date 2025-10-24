import logging
from logging.handlers import RotatingFileHandler
from typing import Dict

from common.config_manager import ConfigManager


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"


class Logger:
    """Singleton Logger for the indexing server."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._loggers = {}
        return cls._instance

    def setup_logger(self, name: str = "indexing_server") -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        cm = ConfigManager()
        # Fallback if config not explicitly loaded yet
        cfg: Dict = cm.get("logging.indexing_server", default={})
        log_file = cfg.get("log_file", "logs/indexing_server.log")
        max_bytes = int(cfg.get("max_bytes", 1048576))
        backup_count = int(cfg.get("backup_count", 5))
        level_str = cfg.get("level", "INFO")
        level = getattr(logging, level_str.upper(), logging.INFO)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        formatter = logging.Formatter(LOG_FORMAT)
        handler = RotatingFileHandler(log_file, maxBytes=max_bytes, backupCount=backup_count)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self._loggers[name] = logger
        return logger


# Helper to get a configured logger
_get_logger = Logger().setup_logger