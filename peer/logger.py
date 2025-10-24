import logging
import os
from logging.handlers import RotatingFileHandler
from typing import Dict

from common.config_manager import ConfigManager


LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s"


class Logger:
    """Singleton Logger for peer components."""

    _instance = None

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
            cls._instance._loggers = {}
        return cls._instance

    def setup_logger(self, name: str = "peer") -> logging.Logger:
        if name in self._loggers:
            return self._loggers[name]

        cm = ConfigManager()
        cfg: Dict = cm.get("logging.peer", default={})
        log_file = cfg.get("log_file", "logs/peer.log")
        max_bytes = int(cfg.get("max_bytes", 1048576))
        backup_count = int(cfg.get("backup_count", 5))
        level_str = cfg.get("level", "INFO")
        level = getattr(logging, level_str.upper(), logging.INFO)

        logger = logging.getLogger(name)
        logger.setLevel(level)
        logger.propagate = False

        formatter = logging.Formatter(LOG_FORMAT)
        # Build a unique log file per logger and process to avoid cross-process rotation conflicts
        base, ext = os.path.splitext(log_file)
        pid = os.getpid()
        if ext:
            unique_log_file = f"{base}.{name}.{pid}{ext}"
        else:
            unique_log_file = f"{log_file}.{name}.{pid}.log"
        os.makedirs(os.path.dirname(unique_log_file) or "logs", exist_ok=True)
        handler = RotatingFileHandler(unique_log_file, maxBytes=max_bytes, backupCount=backup_count, delay=True)
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        self._loggers[name] = logger
        return logger


# Helper to get a configured logger
_get_logger = Logger().setup_logger