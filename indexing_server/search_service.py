from typing import Dict, Any

from common.protocol import ProtocolHandler, SEARCH_RESPONSE
from .file_index import FileIndex


class SearchService:
    """Search for files across registered peers."""

    def __init__(self, index: FileIndex, logger=None) -> None:
        self.index = index
        self.logger = logger

    def search(self, message: Dict[str, Any]) -> Dict[str, Any]:
        payload = message.get("payload", {})
        query = payload.get("query", {})
        file_name = query if isinstance(query, str) else query.get("file_name")
        if not file_name:
            # Return empty results on malformed query
            resp = {"status": "error", "error": "missing file_name", "results": []}
        else:
            peers = self.index.get_peers_for_file(file_name)
            resp = {"status": "ok", "file_name": file_name, "results": peers}
            if self.logger:
                self.logger.info(f"Search '{file_name}' -> {len(peers)} peers")

        return ProtocolHandler.create_message(
            SEARCH_RESPONSE,
            resp,
            peer_id=message.get("peer_id"),
        )