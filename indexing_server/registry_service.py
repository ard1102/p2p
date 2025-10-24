from typing import Dict, Any, Tuple

from common.protocol import ProtocolHandler, REGISTRY_RESPONSE
from .file_index import FileIndex
from .replication_service import ReplicationService


class RegistryService:
    """Handles peer registration and file catalog updates."""

    def __init__(self, index: FileIndex, replication_service: ReplicationService, logger=None) -> None:
        self.index = index
        self.replication = replication_service
        self.logger = logger

    def register_peer(self, message: Dict[str, Any], client_addr: Tuple[str, int]) -> Dict[str, Any]:
        # Expecting message with type REGISTRY_REQUEST and payload {"files": {file_name: meta?}, "peer": optional}
        peer_id = message.get("peer_id")
        payload = message.get("payload", {})
        files = payload.get("files", {})
        peer_info = payload.get("peer", {})
        client_host, client_port = client_addr

        if not peer_id:
            return ProtocolHandler.create_message(
                REGISTRY_RESPONSE,
                {"status": "error", "error": "missing peer_id"},
                peer_id=peer_id,
            )

        # Prefer peer-provided host/port over socket's ephemeral address
        intended_host = peer_info.get("host")
        intended_port = peer_info.get("port")
        try:
            final_port = int(intended_port) if intended_port is not None else int(client_port)
        except Exception:
            final_port = int(client_port)
        final_host = intended_host if intended_host else client_host

        peer_record = {**peer_info, "host": final_host, "port": final_port}
        self.index.add_peer(peer_id, peer_record)

        # Register files
        registered = 0
        if isinstance(files, dict):
            for fname, meta in files.items():
                self.index.add_file(peer_id, fname, meta if isinstance(meta, dict) else {})
                registered += 1
        elif isinstance(files, list):
            for item in files:
                if isinstance(item, dict):
                    fname = item.get("name") or item.get("file_name")
                    meta = {k: v for k, v in item.items() if k not in ("name", "file_name")}
                    if fname:
                        self.index.add_file(peer_id, fname, meta)
                        registered += 1

        if self.logger:
            self.logger.info(f"Registered peer={peer_id} files={registered} from {final_host}:{final_port}")

        # Build replication tasks for this peer if needed
        tasks = self.replication.build_replication_tasks_for_peer(peer_id, max_tasks=5)
        resp_payload = {"status": "ok", "registered_files": registered}
        if tasks:
            resp_payload["replication_tasks"] = tasks
            resp_payload["replication_required"] = True
            if self.logger:
                self.logger.info(f"Replication suggested for peer={peer_id}: {len(tasks)} task(s)")
        else:
            resp_payload["replication_required"] = False

        return ProtocolHandler.create_message(
            REGISTRY_RESPONSE,
            resp_payload,
            peer_id=peer_id,
        )