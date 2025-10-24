import os
import re
import time
import threading
import argparse
from typing import Optional

from common.config_manager import ConfigManager
from common.metrics import MetricsCollector
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from peer.peer_server import PeerServer
from peer.logger import _get_logger


def _compute_port(peer_id: str, base_port: int) -> int:
    m = re.search(r"(\d+)$", peer_id)
    if m:
        try:
            idx = int(m.group(1))
            return base_port + max(idx - 1, 0)
        except ValueError:
            return base_port
    return base_port


def main() -> None:
    parser = argparse.ArgumentParser(description="Headless peer entry point (no CLI)")
    parser.add_argument(
        "config",
        nargs="?",
        default=os.path.join("config", "config.json"),
        help="Path to configuration JSON",
    )
    parser.add_argument("--peer", default="peer1", help="Peer ID (e.g., peer1, peer2)")
    args = parser.parse_args()

    peer_id = args.peer
    config_path = args.config

    cm = ConfigManager()
    cm.load_config(config_path)

    os.makedirs("logs", exist_ok=True)
    logger = _get_logger("peer_headless")

    file_manager = FileManager(config_path=config_path)
    metrics = MetricsCollector()
    client = PeerClient(peer_id, file_manager, metrics, config_path=config_path, logger_name="peer_client")

    host = cm.get("peer.host", "0.0.0.0")
    base_port = int(cm.get("peer.base_port", 7100))
    port = _compute_port(peer_id, base_port)
    server = PeerServer(peer_id, host, port, file_manager)

    # Ensure data exists; generate if empty
    try:
        files_map = file_manager.list_shared_files(peer_id)
    except Exception:
        files_map = {}
    if not files_map:
        logger.info("No files found in shared dir; generating datasets...")
        try:
            file_manager.generate_files(peer_id)
        except Exception as e:
            logger.warning(f"File generation error: {e}")

    # Start server in background
    t = threading.Thread(target=server.start, name=f"{peer_id}-server", daemon=True)
    t.start()
    logger.info(f"PeerServer started headless on {host}:{port}")

    # Register with indexing server
    try:
        payload = client.register_with_server(peer_ip=None, peer_port=port)
        logger.info(f"Registry response: {payload}")
    except Exception as e:
        logger.error(f"Registration failed: {e}")

    # Keep the container alive
    logger.info("Headless peer running. Sleeping indefinitely...")
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass
    finally:
        try:
            server.stop()
        except Exception:
            pass


if __name__ == "__main__":
    main()