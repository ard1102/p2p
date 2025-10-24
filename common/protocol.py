import json
import time
from typing import Any, Dict, Optional


# Message type constants
REGISTRY_REQUEST = "REGISTRY_REQUEST"
REGISTRY_RESPONSE = "REGISTRY_RESPONSE"
SEARCH_REQUEST = "SEARCH_REQUEST"
SEARCH_RESPONSE = "SEARCH_RESPONSE"
REGISTER_FILE = "REGISTER_FILE"
FILE_LIST = "FILE_LIST"
DOWNLOAD_REQUEST = "DOWNLOAD_REQUEST"
DOWNLOAD_RESPONSE = "DOWNLOAD_RESPONSE"
HEARTBEAT = "HEARTBEAT"

# Peer-to-peer obtain/replicate
OBTAIN_REQUEST = "OBTAIN_REQUEST"
OBTAIN_RESPONSE = "OBTAIN_RESPONSE"
REPLICATE_REQUEST = "REPLICATE_REQUEST"
REPLICATE_RESPONSE = "REPLICATE_RESPONSE"


class ProtocolError(Exception):
    pass


class ProtocolHandler:
    """Static helpers for creating, parsing, and sending protocol messages.

    Messages are JSON objects with structure:
    {
      "type": <message_type>,
      "timestamp": <epoch_ms>,
      "version": "1.0",
      "peer_id": <optional>,
      "request_id": <optional>,
      "payload": { ... }
    }

    Serialization uses UTF-8 JSON with a trailing newline for framing.
    """

    @staticmethod
    def create_message(message_type: str, payload: Dict[str, Any], *, peer_id: Optional[str] = None,
                       request_id: Optional[str] = None, version: str = "1.0") -> Dict[str, Any]:
        return {
            "type": message_type,
            "timestamp": int(time.time() * 1000),
            "version": version,
            "peer_id": peer_id,
            "request_id": request_id,
            "payload": payload or {},
        }

    @staticmethod
    def serialize(message: Dict[str, Any]) -> bytes:
        try:
            return (json.dumps(message) + "\n").encode("utf-8")
        except Exception as e:
            raise ProtocolError(f"Serialization error: {e}")

    @staticmethod
    def parse_message(data: str) -> Dict[str, Any]:
        try:
            return json.loads(data)
        except Exception as e:
            raise ProtocolError(f"Parse error: {e}")

    @staticmethod
    def send_message(sock, message: Dict[str, Any]) -> None:
        payload = ProtocolHandler.serialize(message)
        sock.sendall(payload)

    @staticmethod
    def receive_message(sock, *, timeout: Optional[float] = None) -> Dict[str, Any]:
        chunks = []
        while True:
            data = sock.recv(4096)
            if not data:
                raise ProtocolError("Connection closed while reading message")
            chunks.append(data)
            joined = b"".join(chunks)
            if b"\n" in joined:
                line, _rest = joined.split(b"\n", 1)
                return ProtocolHandler.parse_message(line.decode("utf-8"))


# Preset message builders for convenience

def make_registry_request(peer_id: str, files: Dict[str, Any]) -> Dict[str, Any]:
    return ProtocolHandler.create_message(REGISTRY_REQUEST, {"files": files}, peer_id=peer_id)


def make_search_request(peer_id: str, query: Dict[str, Any] | str) -> Dict[str, Any]:
    q = query if isinstance(query, dict) else {"file_name": query}
    return ProtocolHandler.create_message(SEARCH_REQUEST, {"query": q}, peer_id=peer_id)


def make_download_request(peer_id: str, file_info: Dict[str, Any]) -> Dict[str, Any]:
    return ProtocolHandler.create_message(DOWNLOAD_REQUEST, {"file": file_info}, peer_id=peer_id)


def make_obtain_request(peer_id: str, file_name: str) -> Dict[str, Any]:
    return ProtocolHandler.create_message(OBTAIN_REQUEST, {"file_name": file_name}, peer_id=peer_id)


def make_replicate_request(peer_id: str, file_name: str) -> Dict[str, Any]:
    return ProtocolHandler.create_message(REPLICATE_REQUEST, {"file_name": file_name}, peer_id=peer_id)