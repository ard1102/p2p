import os
from typing import Any, Dict, Optional

from common.config_manager import ConfigManager
from common.metrics import MetricsCollector
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from peer.logger import _get_logger


class CommandHandler:
    """
    Maps CLI commands to actions using the PeerClient and FileManager.

    Supported commands:
      - lookup <file>
      - download <file>
      - list local
      - stats
      - exit
    """

    def __init__(
        self,
        peer_id: str,
        peer_client: PeerClient,
        file_manager: FileManager,
        metrics: MetricsCollector,
        config_path: Optional[str] = None,
        logger_name: str = "command_handler",
    ) -> None:
        self.peer_id = peer_id
        self.client = peer_client
        self.fm = file_manager
        self.metrics = metrics

        self.cm = ConfigManager()
        if config_path:
            self.cm.load_config(config_path)
        self.logger = _get_logger(logger_name)

    def handle_command(self, line: str) -> str:
        line = (line or "").strip()
        if not line:
            return ""
        parts = line.split()
        cmd = parts[0].lower()
        args = parts[1:]

        if cmd in ("help", "h", "?"):
            return self._help_text()
        if cmd == "lookup":
            if not args:
                return "Usage: lookup <filename>"
            return self._lookup(args[0])
        if cmd == "download":
            if not args:
                return "Usage: download <filename>"
            return self._download(args[0])
        if cmd == "list":
            if not args:
                return "Usage: list <local|downloaded|replicated>"
            sub = args[0].lower()
            if sub == "local":
                return self._list_local()
            if sub == "downloaded":
                return self._list_downloaded()
            if sub == "replicated":
                return self._list_replicated()
            return "Unknown list target. Try: list local, list downloaded, or list replicated"
        if cmd == "stats":
            return self._stats()
        if cmd == "exit":
            return "EXIT"

        return "Unknown command. Type 'help' for available commands."

    # ---- Command implementations ----
    def _help_text(self) -> str:
        return (
            "Commands:\n"
            "  lookup <filename>        - Search for file\n"
            "  download <filename>      - Download file from a discovered peer\n"
            "  list local               - List files in shared directory\n"
            "  list downloaded          - List files in downloaded directory\n"
            "  list replicated          - List files in replicated directory\n"
            "  stats                    - Show performance statistics\n"
            "  exit                     - Quit CLI\n"
        )

    def _lookup(self, file_name: str) -> str:
        payload = self.client.search_file(file_name)
        status = payload.get("status")
        if status != "ok":
            return f"Search error: {payload.get('error', 'unknown')}"
        results = payload.get("results", [])
        if not results:
            return f"No peers found for '{file_name}'"

        out_lines = [f"Peers serving '{file_name}':"]
        for r in results:
            pid = r.get("peer_id")
            peer = r.get("peer", {})
            host = peer.get("host") or peer.get("ip") or "?"
            port = peer.get("port") or "?"
            out_lines.append(f"  - {pid} @ {host}:{port}")
        return "\n".join(out_lines)

    def _download(self, file_name: str) -> str:
        # Choose a peer from lookup results
        payload = self.client.search_file(file_name)
        results = payload.get("results", [])
        if not results:
            return f"No peers found for '{file_name}'"
        target = results[0]
        peer = target.get("peer", {})
        host = peer.get("host") or peer.get("ip") or "127.0.0.1"
        port = int(peer.get("port") or int(self.cm.get("peer.base_port", 7100)))

        try:
            dest_path, bytes_count, duration = self.client.download_file(host, port, file_name)
            kbps = (bytes_count / duration / 1024) if duration > 0 else 0.0
            return (
                f"Downloaded '{file_name}' from {host}:{port} -> {dest_path} "
                f"({bytes_count} bytes in {duration:.2f}s, {kbps:.2f} KB/s)"
            )
        except Exception as e:
            self.logger.error(f"Download error: {e}")
            return f"Download failed: {e}"

    def _list_local(self) -> str:
        files = self.fm.list_shared_files(self.peer_id)
        if not files:
            return "No local files in shared directory."
        out_lines = [f"Local shared files ({len(files)}):"]
        for name, meta in files.items():
            out_lines.append(f"  - {name} ({meta.get('size_bytes', '?')} bytes)")
        return "\n".join(out_lines)

    def _list_downloaded(self) -> str:
        """List files in the downloaded directory."""
        files = self.fm.list_downloaded_files(self.peer_id)
        if not files:
            return "No downloaded files."
        out_lines = [f"Downloaded files ({len(files)}):"]
        for name, meta in files.items():
            out_lines.append(f"  - {name} ({meta.get('size_bytes', '?')} bytes)")
        return "\n".join(out_lines)

    def _list_replicated(self) -> str:
        """List files in the replicated directory."""
        files = self.fm.list_replicated_files(self.peer_id)
        if not files:
            return "No replicated files."
        out_lines = [f"Replicated files ({len(files)}):"]
        for name, meta in files.items():
            out_lines.append(f"  - {name} ({meta.get('size_bytes', '?')} bytes)")
        return "\n".join(out_lines)

    def _stats(self) -> str:
        stats = self.metrics.get_statistics()
        st = stats.get("search_times", {})
        dl = stats.get("download_speeds", {})
        thr = stats.get("throughput_bytes_per_sec")
        lines = ["Performance stats:"]
        lines.append(
            f"  Search time: mean={st.get('mean')} stdev={st.get('stdev')} min={st.get('min')} max={st.get('max')}"
        )
        lines.append(
            f"  Download speed (B/s): mean={dl.get('mean')} stdev={dl.get('stdev')} min={dl.get('min')} max={dl.get('max')}"
        )
        lines.append(f"  Throughput: {thr} B/s" if thr is not None else "  Throughput: n/a")
        return "\n".join(lines)

    # Optional interactive loop (the main Peer class may use this)
    def run_loop(self) -> None:
        print("Type 'help' to see commands. 'exit' to quit.")
        while True:
            try:
                line = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break
            result = self.handle_command(line)
            if not result:
                continue
            if result == "EXIT":
                break
            print(result)