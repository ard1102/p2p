import os
import socket
import time
from typing import Any, Dict, List, Optional, Tuple

from common.config_manager import ConfigManager
from common.protocol import (
    ProtocolHandler,
    make_registry_request,
    make_search_request,
    make_obtain_request,
    REGISTRY_RESPONSE,
    SEARCH_RESPONSE,
    OBTAIN_RESPONSE,
    make_replicate_request,
    REPLICATE_RESPONSE,
)
from common.metrics import MetricsCollector
from peer.file_manager import FileManager
from peer.logger import _get_logger


class PeerClient:
    """
    Client-side component for peer operations.

    - Registers local files with the Indexing Server
    - Searches for files
    - Downloads files from other peers

    Assumptions:
    - Protocol messages are JSON framed by a trailing newline (ProtocolHandler).
    - OBTAIN_RESPONSE includes metadata: {status, file_name, file_size, chunk_size}.
      After metadata, raw file bytes are streamed on the same socket.
    """

    def __init__(
        self,
        peer_id: str,
        file_manager: FileManager,
        metrics: MetricsCollector,
        config_path: Optional[str] = None,
        logger_name: str = "peer_client",
    ) -> None:
        self.peer_id = peer_id
        self.file_manager = file_manager
        self.metrics = metrics

        # Config
        self.cm = ConfigManager()
        if config_path:
            self.cm.load_config(config_path)
        # Defaults
        self.server_host: str = self.cm.get("server.host", "127.0.0.1")
        self.server_port: int = int(self.cm.get("server.port", 7000))
        self.chunk_size: int = int(
            self.cm.get("data.file_generation.chunk_size_bytes", 1024 * 1024)
        )

        # Logger
        os.makedirs("logs", exist_ok=True)
        self.logger = _get_logger(logger_name)

    # ---- Internal helpers ----
    def _connect(self, host: str, port: int, timeout: Optional[float] = 10.0) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        if timeout:
            sock.settimeout(timeout)
        sock.connect((host, port))
        return sock

    def _safe_get(self, d: Dict[str, Any], *keys, default=None):
        cur: Any = d
        for k in keys:
            if isinstance(cur, dict) and k in cur:
                cur = cur[k]
            else:
                return default
        return cur

    # ---- Server-facing operations ----
    def register_with_server(
        self,
        peer_ip: Optional[str] = None,
        peer_port: Optional[int] = None,
        server_host: Optional[str] = None,
        server_port: Optional[int] = None,
        *,
        perform_replication: bool = True,
    ) -> Dict[str, Any]:
        """
        Register this peer and its shared file list with the Indexing Server.

        Returns the server's REGISTRY_RESPONSE payload.
        Optionally performs any replication tasks returned in the response,
        then re-registers once to update the index.
        """
        host = server_host or self.server_host
        port = int(server_port or self.server_port)
        files = self.file_manager.list_shared_files(self.peer_id)

        # Include peer network info in payload for discovery
        payload = {"files": files, "peer": {"peer_id": self.peer_id, "host": peer_ip, "port": peer_port}}
        message = ProtocolHandler.create_message("REGISTRY_REQUEST", payload, peer_id=self.peer_id)

        self.logger.info(
            f"Registering peer_id={self.peer_id} with server {host}:{port} (files={len(files)})"
        )
        with self._connect(host, port) as sock:
            ProtocolHandler.send_message(sock, message)
            resp = ProtocolHandler.receive_message(sock)

        if resp.get("type") != REGISTRY_RESPONSE:
            raise RuntimeError(f"Unexpected response type: {resp.get('type')}")
        payload = resp.get("payload", {})
        status = payload.get("status")
        if status != "ok":
            self.logger.error(f"Registration failed: {payload}")
        else:
            self.logger.info(
                f"Registration success: registered_files={payload.get('registered_files', 0)}"
            )

        # Handle replication tasks if provided
        if perform_replication:
            tasks = payload.get("replication_tasks", [])
            if tasks:
                self.logger.info(f"Performing {len(tasks)} replication task(s)")
                for t in tasks:
                    fname = t.get("file_name")
                    src = t.get("source", {})
                    src_host = src.get("host")
                    src_port = src.get("port")
                    if not fname or not src_host or not src_port:
                        continue
                    # Replicate into replicated directory
                    dest_dir = self.file_manager.get_replicated_dir(self.peer_id)
                    try:
                        self.replicate_file(src_host, int(src_port), fname, dest_dir=dest_dir)
                    except Exception as e:
                        self.logger.warning(f"Replication failed for '{fname}': {e}")
                # Re-register once to update index with newly replicated files
                try:
                    self.logger.info("Re-registering after replication to update index")
                    return self.register_with_server(peer_ip, peer_port, server_host, server_port, perform_replication=False)
                except Exception as e:
                    self.logger.warning(f"Re-registration failed after replication: {e}")

        return payload

    def search_file(
        self,
        file_name: str,
        server_host: Optional[str] = None,
        server_port: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Send SEARCH_REQUEST and return payload with results.
        Also records search duration in metrics.
        """
        host = server_host or self.server_host
        port = int(server_port or self.server_port)

        message = make_search_request(self.peer_id, file_name)
        self.logger.info(f"Searching for file '{file_name}' at {host}:{port}")

        start = time.time()
        with self._connect(host, port) as sock:
            ProtocolHandler.send_message(sock, message)
            resp = ProtocolHandler.receive_message(sock)
        duration = time.time() - start
        self.metrics.record_search_time(duration)

        if resp.get("type") != SEARCH_RESPONSE:
            raise RuntimeError(f"Unexpected response type: {resp.get('type')}")
        payload = resp.get("payload", {})
        status = payload.get("status")
        if status != "ok":
            self.logger.warning(f"Search error: {payload}")
        else:
            self.logger.info(f"Search results: {len(payload.get('results', []))} peers")
        return payload

    # ---- Peer-facing operations ----
    def download_file(
        self,
        peer_ip: str,
        peer_port: int,
        file_name: str,
        dest_dir: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> Tuple[str, int, float]:
        """
        Download a file from a target peer.

        Returns a tuple: (dest_path, bytes_count, duration_seconds).
        Records download metrics (bytes, duration, instantaneous speed).
        """
        dest_dir = dest_dir or self.file_manager.get_download_dir(self.peer_id)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_name)

        self.logger.info(f"Downloading '{file_name}' from {peer_ip}:{peer_port} -> {dest_path}")

        start = time.time()
        with self._connect(peer_ip, int(peer_port), timeout=timeout) as sock:
            # Request the file
            req = make_obtain_request(self.peer_id, file_name)
            ProtocolHandler.send_message(sock, req)

            # Expect an OBTAIN_RESPONSE metadata message
            meta_msg = ProtocolHandler.receive_message(sock)
            if meta_msg.get("type") != OBTAIN_RESPONSE:
                raise RuntimeError(f"Unexpected response type: {meta_msg.get('type')}")
            meta = meta_msg.get("payload", {})
            status = meta.get("status")
            if status != "ok":
                raise RuntimeError(f"OBTAIN failed: {meta}")

            file_size = int(meta.get("file_size", 0))
            chunk_size = int(meta.get("chunk_size", self.chunk_size))

            # Receive raw bytes that follow and stream to disk
            bytes_remaining = file_size if file_size > 0 else None

            def _chunk_stream():
                nonlocal bytes_remaining
                while True:
                    # Decide read size
                    read_n = chunk_size if not bytes_remaining else min(chunk_size, bytes_remaining)
                    data = sock.recv(read_n)
                    if not data:
                        break
                    yield data
                    if bytes_remaining is not None:
                        bytes_remaining -= len(data)
                        if bytes_remaining <= 0:
                            break

            # Write chunks to destination
            self.file_manager.write_file_chunks(dest_path, _chunk_stream())

        duration = time.time() - start
        bytes_count = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        speed = (bytes_count / duration) if duration > 0 else 0.0

        # Metrics
        self.metrics.record_download(bytes_count, duration)
        self.metrics.record_download_speed(speed)

        self.logger.info(
            f"Download complete: {bytes_count} bytes in {duration:.2f}s ({speed/1024:.2f} KB/s)"
        )
        return dest_path, bytes_count, duration

    def replicate_file(
        self,
        source_ip: str,
        source_port: int,
        file_name: str,
        dest_dir: Optional[str] = None,
        timeout: Optional[float] = 30.0,
    ) -> Tuple[str, int, float]:
        """Download a file using REPLICATE_REQUEST into the peer's replicated directory by default."""
        dest_dir = dest_dir or self.file_manager.get_replicated_dir(self.peer_id)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, file_name)

        self.logger.info(f"Replicating '{file_name}' from {source_ip}:{source_port} -> {dest_path}")

        start = time.time()
        with self._connect(source_ip, int(source_port), timeout=timeout) as sock:
            # Request the file via REPLICATE
            req = make_replicate_request(self.peer_id, file_name)
            ProtocolHandler.send_message(sock, req)

            # Expect a REPLICATE_RESPONSE metadata message
            meta_msg = ProtocolHandler.receive_message(sock)
            if meta_msg.get("type") != REPLICATE_RESPONSE:
                raise RuntimeError(f"Unexpected response type: {meta_msg.get('type')}")
            meta = meta_msg.get("payload", {})
            status = meta.get("status")
            if status != "ok":
                raise RuntimeError(f"REPLICATE failed: {meta}")

            file_size = int(meta.get("file_size", 0))
            chunk_size = int(meta.get("chunk_size", self.chunk_size))

            # Receive raw bytes that follow and stream to disk
            bytes_remaining = file_size if file_size > 0 else None

            def _chunk_stream():
                nonlocal bytes_remaining
                while True:
                    read_n = chunk_size if not bytes_remaining else min(chunk_size, bytes_remaining)
                    data = sock.recv(read_n)
                    if not data:
                        break
                    yield data
                    if bytes_remaining is not None:
                        bytes_remaining -= len(data)
                        if bytes_remaining <= 0:
                            break

            self.file_manager.write_file_chunks(dest_path, _chunk_stream())

        duration = time.time() - start
        bytes_count = os.path.getsize(dest_path) if os.path.exists(dest_path) else 0
        speed = (bytes_count / duration) if duration > 0 else 0.0

        self.metrics.record_download(bytes_count, duration)
        self.metrics.record_download_speed(speed)

        self.logger.info(
            f"Replication complete: {bytes_count} bytes in {duration:.2f}s ({speed/1024:.2f} KB/s)"
        )
        return dest_path, bytes_count, duration