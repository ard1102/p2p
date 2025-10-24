import os
import re
import threading
import argparse
from typing import Optional

from common.config_manager import ConfigManager
from common.metrics import MetricsCollector
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from peer.command_handler import CommandHandler
from peer.logger import _get_logger
from peer.peer_server import PeerServer


class Peer:
    """
    Main peer class
    Orchestrates file generation, server startup, registration, and CLI.
    """

    def __init__(self, peer_id: str, config_path: Optional[str] = None) -> None:
        self.peer_id = peer_id
        self.config_path = config_path or os.path.join("config", "config.json")

        # Config
        self.cm = ConfigManager()
        self.cm.load_config(self.config_path)

        # Logger
        os.makedirs("logs", exist_ok=True)
        self.logger = _get_logger("peer_main")

        # Components
        self.file_manager = FileManager(config_path=self.config_path)
        self.metrics = MetricsCollector()
        self.client = PeerClient(
            peer_id,
            self.file_manager,
            self.metrics,
            config_path=self.config_path,
            logger_name="peer_client",
        )
        self.command_handler = CommandHandler(
            peer_id,
            self.client,
            self.file_manager,
            self.metrics,
            config_path=self.config_path,
            logger_name="command_handler",
        )

        # Network settings
        self.host = self.cm.get("peer.host", "0.0.0.0")
        base_port = int(self.cm.get("peer.base_port", 7100))
        self.port = self._compute_port(peer_id, base_port)

        # Peer server
        self.server = PeerServer(peer_id, self.host, self.port, self.file_manager)
        self._server_thread: Optional[threading.Thread] = None

    @staticmethod
    def _compute_port(peer_id: str, base_port: int) -> int:
        """
        Compute port from base_port and numeric suffix of peer_id.
        Examples:
          - peer1 -> base_port + 0
          - peer2 -> base_port + 1
          - peerN -> base_port + (N-1)
        If no numeric suffix, returns base_port.
        """
        m = re.search(r"(\d+)$", peer_id)
        if m:
            try:
                idx = int(m.group(1))
                return base_port + max(idx - 1, 0)
            except ValueError:
                return base_port
        return base_port

    def start(self) -> None:
        """
        Start peer operations:
        1. Ensure directories; generate files if none exist
        2. Start peer server (background thread)
        3. Register with indexing server
        4. Start CLI loop
        """
        self.logger.info(f"Starting peer '{self.peer_id}' on {self.host}:{self.port}")

        # Ensure directories and optionally generate files
        try:
            files_map = self.file_manager.list_shared_files(self.peer_id)
        except Exception as e:
            self.logger.warning(f"List shared files error: {e}")
            files_map = {}

        if not files_map:
            self.logger.info("No files found in shared dir; generating datasets...")
            try:
                self.file_manager.generate_files(self.peer_id)
            except Exception as e:
                self.logger.warning(f"File generation error: {e}")

        # Start server in background
        self._server_thread = threading.Thread(
            target=self.server.start, name=f"{self.peer_id}-server", daemon=True
        )
        self._server_thread.start()
        self.logger.info(f"PeerServer started on {self.host}:{self.port}")

        # Register with Indexing Server (provide configured port)
        try:
            payload = self.client.register_with_server(peer_ip=None, peer_port=self.port)
            self.logger.info(f"Registry response: {payload}")
        except Exception as e:
            self.logger.error(f"Registration failed: {e}")

        # Start interactive CLI loop
        try:
            self.command_handler.run_loop()
        finally:
            self.stop()

    def stop(self) -> None:
        """Graceful shutdown of the peer server."""
        self.logger.info("Shutting down peer...")
        try:
            if hasattr(self.server, "stop"):
                self.server.stop()
        except Exception:
            pass
        if self._server_thread and self._server_thread.is_alive():
            try:
                self._server_thread.join(timeout=1.0)
            except Exception:
                pass
        self.logger.info("Peer stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Peer node entry point")
    parser.add_argument(
        "config",
        nargs="?",
        default=os.path.join("config", "config.json"),
        help="Path to configuration JSON",
    )
    parser.add_argument("--peer", default="peer1", help="Peer ID (e.g., peer1, peer2)")
    args = parser.parse_args()

    peer = Peer(peer_id=args.peer, config_path=args.config)
    peer.start()


if __name__ == "__main__":
    main()