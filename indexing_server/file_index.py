import threading
from typing import Dict, List, Optional, Any


class FileIndex:
    """Thread-safe file index and peer registry.

    - file_index: {file_name: [ {peer_id: str, meta: dict} ]}
    - peer_registry: {peer_id: {peer_id, host, port, extra}}
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self.file_index: Dict[str, List[Dict[str, Any]]] = {}
        self.peer_registry: Dict[str, Dict[str, Any]] = {}

    # Peer operations
    def add_peer(self, peer_id: str, peer_info: Dict[str, Any]) -> None:
        with self._lock:
            self.peer_registry[peer_id] = {"peer_id": peer_id, **peer_info}

    def remove_peer(self, peer_id: str) -> None:
        with self._lock:
            # Remove peer from registry
            self.peer_registry.pop(peer_id, None)
            # Remove peer from any files they were serving
            for fname, peers in list(self.file_index.items()):
                self.file_index[fname] = [p for p in peers if p.get("peer_id") != peer_id]
                if not self.file_index[fname]:
                    del self.file_index[fname]

    def get_peer(self, peer_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            return self.peer_registry.get(peer_id)

    # File operations
    def add_file(self, peer_id: str, file_name: str, meta: Optional[Dict[str, Any]] = None) -> None:
        with self._lock:
            entry = {"peer_id": peer_id, "meta": meta or {}}
            peers = self.file_index.setdefault(file_name, [])
            # Avoid duplicates for the same peer
            if not any(p.get("peer_id") == peer_id for p in peers):
                peers.append(entry)

    def remove_file(self, peer_id: str, file_name: str) -> None:
        with self._lock:
            peers = self.file_index.get(file_name)
            if not peers:
                return
            self.file_index[file_name] = [p for p in peers if p.get("peer_id") != peer_id]
            if not self.file_index[file_name]:
                del self.file_index[file_name]

    def get_peers_for_file(self, file_name: str) -> List[Dict[str, Any]]:
        with self._lock:
            peers = self.file_index.get(file_name, [])
            # enrich with peer registry info
            enriched: List[Dict[str, Any]] = []
            for p in peers:
                pid = p.get("peer_id")
                reg = self.peer_registry.get(pid, {})
                enriched.append({"peer_id": pid, "peer": reg, "meta": p.get("meta", {})})
            return enriched

    def list_files(self) -> List[str]:
        with self._lock:
            return list(self.file_index.keys())