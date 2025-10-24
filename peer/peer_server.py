import os
import socket
import threading
from typing import Tuple, Optional

from common.protocol import (
    ProtocolHandler,
    OBTAIN_REQUEST,
    OBTAIN_RESPONSE,
    REPLICATE_REQUEST,
    REPLICATE_RESPONSE,
)
from peer.file_manager import FileManager
from peer.logger import _get_logger


class PeerServer:
    """
    Serves files to other peers.

    Listens for OBTAIN_REQUEST and REPLICATE_REQUEST and responds with a metadata
    message followed by raw file bytes streamed on the same socket.
    """

    def __init__(self, peer_id: str, host: str, port: int, file_manager: FileManager, logger_name: str = "peer_server") -> None:
        self.peer_id = peer_id
        self.host = host
        self.port = int(port)
        self.file_manager = file_manager

        self.logger = _get_logger(logger_name)
        self.sock: Optional[socket.socket] = None
        self.running: bool = False

    def start(self) -> None:
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.bind((self.host, self.port))
        self.sock.listen(64)
        self.running = True
        self.logger.info(f"PeerServer listening on {self.host}:{self.port}")

        try:
            while self.running:
                conn, addr = self.sock.accept()
                t = threading.Thread(target=self.handle_client, args=(conn, addr), daemon=True)
                t.start()
        except KeyboardInterrupt:
            self.logger.info("PeerServer shutdown (KeyboardInterrupt)")
        finally:
            self.stop()

    def stop(self) -> None:
        self.running = False
        try:
            if self.sock:
                try:
                    self.sock.shutdown(socket.SHUT_RDWR)
                except Exception:
                    pass
                self.sock.close()
        except Exception:
            pass
        self.logger.info("PeerServer stopped")

    def handle_client(self, conn: socket.socket, addr: Tuple[str, int]) -> None:
        self.logger.info(f"Accepted peer connection from {addr[0]}:{addr[1]}")
        try:
            try:
                message = ProtocolHandler.receive_message(conn)
            except Exception as e:
                self.logger.warning(f"Receive error from {addr}: {e}")
                return

            mtype = message.get("type")
            if mtype not in (OBTAIN_REQUEST, REPLICATE_REQUEST):
                # Reply with error in OBTAIN_RESPONSE schema
                resp = ProtocolHandler.create_message(
                    OBTAIN_RESPONSE,
                    {"status": "error", "error": f"unexpected message type: {mtype}"},
                    peer_id=self.peer_id,
                )
                try:
                    ProtocolHandler.send_message(conn, resp)
                except Exception:
                    pass
                return

            payload = message.get("payload", {})
            file_name = payload.get("file_name")
            if not file_name:
                resp_type = REPLICATE_RESPONSE if mtype == REPLICATE_REQUEST else OBTAIN_RESPONSE
                resp = ProtocolHandler.create_message(
                    resp_type,
                    {"status": "error", "error": "missing file_name"},
                    peer_id=self.peer_id,
                )
                try:
                    ProtocolHandler.send_message(conn, resp)
                except Exception:
                    pass
                return

            shared_dir = self.file_manager.get_shared_dir(self.peer_id)
            path = os.path.join(shared_dir, file_name)
            if not os.path.isfile(path):
                resp_type = REPLICATE_RESPONSE if mtype == REPLICATE_REQUEST else OBTAIN_RESPONSE
                resp = ProtocolHandler.create_message(
                    resp_type,
                    {"status": "error", "error": "file_not_found", "file_name": file_name},
                    peer_id=self.peer_id,
                )
                try:
                    ProtocolHandler.send_message(conn, resp)
                except Exception:
                    pass
                self.logger.info(f"File not found: {file_name} requested by {addr}")
                return

            # Prepare metadata
            try:
                file_size = os.path.getsize(path)
            except OSError:
                file_size = 0
            # Use configured chunk size from FileManager
            try:
                chunk_size = self.file_manager._chunk_size()  # type: ignore[attr-defined]
            except Exception:
                chunk_size = 1024 * 1024

            resp_type = REPLICATE_RESPONSE if mtype == REPLICATE_REQUEST else OBTAIN_RESPONSE
            meta = ProtocolHandler.create_message(
                resp_type,
                {
                    "status": "ok",
                    "file_name": file_name,
                    "file_size": int(file_size),
                    "chunk_size": int(chunk_size),
                },
                peer_id=self.peer_id,
            )

            # Send metadata first
            try:
                ProtocolHandler.send_message(conn, meta)
            except Exception as e:
                self.logger.warning(f"Send metadata error to {addr}: {e}")
                return

            # Stream file data
            try:
                for chunk in self.file_manager.read_file_chunks(self.peer_id, file_name, chunk_size):
                    if not chunk:
                        break
                    conn.sendall(chunk)
                self.logger.info(
                    f"Completed transfer '{file_name}' to {addr[0]}:{addr[1]} ({file_size} bytes)"
                )
            except Exception as e:
                self.logger.warning(f"Transfer error to {addr}: {e}")
        finally:
            try:
                conn.close()
            except Exception:
                pass
            self.logger.info(f"Closed peer connection from {addr[0]}:{addr[1]}")