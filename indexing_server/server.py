import os
import socket
import threading
from typing import Tuple, Dict, Any

from common.config_manager import ConfigManager
from common.protocol import (
    ProtocolHandler,
    REGISTRY_REQUEST,
    SEARCH_REQUEST,
    REGISTRY_RESPONSE,
    SEARCH_RESPONSE,
)
from indexing_server.logger import _get_logger
from .file_index import FileIndex
from .registry_service import RegistryService
from .search_service import SearchService
from .replication_service import ReplicationService


class IndexingServer:
    def __init__(self, config_path: str = os.path.join("config", "config.json")) -> None:
        # Load config
        self.config_path = config_path
        self.cm = ConfigManager()
        self.cm.load_config(self.config_path)

        # Logger
        os.makedirs("logs", exist_ok=True)
        self.logger = _get_logger("indexing_server")

        # Services
        self.index = FileIndex()
        repl_factor = int(self.cm.get("replication.replication_factor", 2))
        self.replication_service = ReplicationService(self.index, replication_factor=repl_factor, logger=self.logger)
        self.registry_service = RegistryService(self.index, self.replication_service, logger=self.logger)
        self.search_service = SearchService(self.index, logger=self.logger)

        # Server socket
        self.host = self.cm.get("server.host", "127.0.0.1")
        self.port = int(self.cm.get("server.port", 7000))
        self.sock = None
        self.running = False

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(128)
        self.running = True
        self.logger.info(f"IndexingServer listening on {self.host}:{self.port}")

        try:
            while self.running:
                conn, addr = self.sock.accept()
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
        except KeyboardInterrupt:
            self.logger.info("Shutting down server (KeyboardInterrupt)")
        finally:
            self.stop()

    def stop(self) -> None:
        self.running = False
        try:
            if self.sock:
                self.sock.close()
        except Exception:
            pass

    def handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        self.logger.info(f"Accepted connection from {addr[0]}:{addr[1]}")
        try:
            while True:
                try:
                    message = ProtocolHandler.receive_message(conn)
                except Exception as e:
                    self.logger.warning(f"Receive error from {addr}: {e}")
                    break

                mtype = message.get("type")
                response: Dict[str, Any]

                if mtype == REGISTRY_REQUEST:
                    response = self.registry_service.register_peer(message, addr)
                elif mtype == SEARCH_REQUEST:
                    response = self.search_service.search(message)
                else:
                    # Unknown message types
                    response = ProtocolHandler.create_message(
                        REGISTRY_RESPONSE,  # using response schema format
                        {"status": "error", "error": f"unknown message type: {mtype}"}
                    )

                try:
                    ProtocolHandler.send_message(conn, response)
                except Exception as e:
                    self.logger.warning(f"Send error to {addr}: {e}")
                    break
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self.logger.info(f"Closed connection from {addr[0]}:{addr[1]}")


if __name__ == "__main__":
    server = IndexingServer()
    server.start()