from typing import List, Dict, Optional

from .file_index import FileIndex


class ReplicationService:
    """Replication coordinator depending on FileIndex and replication_factor.

    Provides helpers to check replication level, select target peers, and
    build replication tasks for a target peer. Actual replication execution
    is delegated to peers via client-side actions.
    """

    def __init__(self, index: FileIndex, replication_factor: int = 2, logger=None) -> None:
        self.index = index
        self.replication_factor = int(replication_factor)
        self.logger = logger

    def check_replication(self, file_name: str) -> bool:
        """Return True if file meets the replication factor, False otherwise."""
        peers = self.index.get_peers_for_file(file_name)
        ok = len(peers) >= self.replication_factor
        if self.logger:
            self.logger.debug(
                f"Replication check for '{file_name}': {len(peers)}/{self.replication_factor} -> {'OK' if ok else 'NEEDS_REPLICATION'}"
            )
        return ok

    def select_target_peers(self, file_name: str, count: int = 1, exclude_peer_ids: Optional[List[str]] = None) -> List[Dict]:
        """Select peers that do not currently have the file to become replication targets.

        Returns a list of peer registry entries: {peer_id, host, port, ...}
        """
        exclude_peer_ids = exclude_peer_ids or []
        serving = {p.get("peer_id") for p in self.index.get_peers_for_file(file_name)}
        serving.update(exclude_peer_ids)

        # Choose from registry peers that are not serving this file
        candidates: List[Dict] = []
        for pid, info in self.index.peer_registry.items():  # type: ignore[attr-defined]
            if pid not in serving:
                candidates.append({"peer_id": pid, **info})
        # Simple selection: first N
        selected = candidates[:max(0, count)]
        if self.logger and selected:
            self.logger.info(f"Selected {len(selected)} target peer(s) for '{file_name}': {[p['peer_id'] for p in selected]}")
        return selected

    def build_replication_tasks_for_peer(self, target_peer_id: str, max_tasks: int = 5) -> List[Dict]:
        """Build replication tasks for target peer to help reach replication factor.

        Task format:
          {
            "file_name": str,
            "source": {"peer_id": str, "host": str, "port": int},
          }
        """
        tasks: List[Dict] = []
        for fname in self.index.list_files():
            if len(self.index.get_peers_for_file(fname)) >= self.replication_factor:
                continue
            # Skip if target already has the file
            if any(p.get("peer_id") == target_peer_id for p in self.index.get_peers_for_file(fname)):
                continue
            sources = self.index.get_peers_for_file(fname)
            if not sources:
                # No available source yet
                continue
            source = sources[0]  # simple choice: first source
            peer_info = source.get("peer", {})
            host = peer_info.get("host") or peer_info.get("ip")
            port = peer_info.get("port")
            if not host or not port:
                continue
            tasks.append({
                "file_name": fname,
                "source": {"peer_id": source.get("peer_id"), "host": host, "port": int(port)},
            })
            if len(tasks) >= max_tasks:
                break
        if self.logger:
            if tasks:
                self.logger.info(f"Built {len(tasks)} replication task(s) for target '{target_peer_id}'")
            else:
                self.logger.debug(f"No replication tasks for target '{target_peer_id}'")
        return tasks

    def trigger_replication_scan(self) -> None:
        """Scan all files and log those under-replicated (diagnostic)."""
        for fname in self.index.list_files():
            if not self.check_replication(fname) and self.logger:
                self.logger.warning(f"Under-replicated file: {fname}")