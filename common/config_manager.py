import json
import threading
from typing import Any, Dict


class ConfigManager:
    """Singleton configuration manager with dot-notation access."""

    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._config = {}
        return cls._instance

    def load_config(self, config_path: str) -> None:
        with open(config_path, "r", encoding="utf-8") as f:
            self._config = json.load(f)

    def get(self, key_path: str, default: Any = None) -> Any:
        """Access nested config values via dot notation.

        Example: get('server.port') -> 7000
        """
        if not key_path:
            return default
        node: Any = self._config
        for key in key_path.split('.'):
            if isinstance(node, dict) and key in node:
                node = node[key]
            else:
                return default
        return node

    def as_dict(self) -> Dict:
        return self._config