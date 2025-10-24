import os
import json
import argparse
import math
from typing import Dict, Optional, List


class FileManager:
    """Manages generation and IO of test files for peers based on configuration.

    Generates datasets according to the config:
      - 1000 x 1KB (txt)
      - 100 x 1MB (bin)
      - 1 x 1GB (bin)

    Filenames follow: [peerID]_[size]_[number].[extension]
    e.g., peer1_kb_0001.txt, peer2_gb_0001.bin

    Also provides helpers for listing local files and chunked IO.
    """

    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or os.path.join("config", "config.json")
        self._config = self._load_config(self.config_path)

    def _load_config(self, path: str) -> Dict:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _peer_dirs(self, peer_id: str) -> Dict[str, str]:
        peers = self._config.get("data", {}).get("peers", {})
        if peer_id not in peers:
            raise ValueError(f"Peer '{peer_id}' not found in config")
        return peers[peer_id]

    def _file_gen_config(self) -> Dict:
        return self._config.get("data", {}).get("file_generation", {})

    def _ensure_dirs(self, dirs: List[str]):
        for d in dirs:
            os.makedirs(d, exist_ok=True)

    def _chunk_size(self) -> int:
        return int(self._file_gen_config().get("chunk_size_bytes", 1024 * 1024))

    def list_shared_files(self, peer_id: str) -> Dict[str, Dict[str, int]]:
        """Return mapping of file_name -> meta (size_bytes) in the peer's shared dir."""
        dirs = self._peer_dirs(peer_id)
        shared_dir = dirs.get("shared_dir")
        self._ensure_dirs([shared_dir])
        files: Dict[str, Dict[str, int]] = {}
        for name in os.listdir(shared_dir):
            path = os.path.join(shared_dir, name)
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                    files[name] = {"size_bytes": int(size)}
                except OSError:
                    continue
        return files

    def list_downloaded_files(self, peer_id: str) -> Dict[str, Dict[str, int]]:
        """Return mapping of file_name -> meta (size_bytes) in the peer's downloaded dir."""
        dirs = self._peer_dirs(peer_id)
        download_dir = dirs.get("download_dir")
        self._ensure_dirs([download_dir])
        files: Dict[str, Dict[str, int]] = {}
        for name in os.listdir(download_dir):
            path = os.path.join(download_dir, name)
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                    files[name] = {"size_bytes": int(size)}
                except OSError:
                    continue
        return files

    def list_replicated_files(self, peer_id: str) -> Dict[str, Dict[str, int]]:
        """Return mapping of file_name -> meta (size_bytes) in the peer's replicated dir."""
        dirs = self._peer_dirs(peer_id)
        replicated_dir = dirs.get("replicated_dir")
        self._ensure_dirs([replicated_dir])
        files: Dict[str, Dict[str, int]] = {}
        for name in os.listdir(replicated_dir):
            path = os.path.join(replicated_dir, name)
            if os.path.isfile(path):
                try:
                    size = os.path.getsize(path)
                    files[name] = {"size_bytes": int(size)}
                except OSError:
                    continue
        return files

    def generate_files(self, peer_id: str, dataset_types: Optional[List[str]] = None) -> None:
        """Create files for the given peer.

        Args:
            peer_id: e.g. 'peer1' or 'peer2'
            dataset_types: subset of ['kb','mb','gb']; if None, generate all.
        """
        peer_dirs = self._peer_dirs(peer_id)
        shared_dir = peer_dirs.get("shared_dir")
        self._ensure_dirs([shared_dir])

        fg = self._file_gen_config()
        pattern = fg.get("pattern", "{peer}_{size}_{num}.{ext}")
        chunk_size = self._chunk_size()

        targets = ["kb", "mb", "gb"] if dataset_types is None else dataset_types
        for size_key in targets:
            if size_key not in fg:
                print(f"Skipping unknown dataset '{size_key}'")
                continue
            cfg = fg[size_key]
            count = int(cfg.get("count", 0))
            size_bytes = int(cfg.get("size_bytes", 0))
            ext = cfg.get("extension", "bin")

            pad_width = max(4, int(math.log10(max(1, count))) + 1)
            for i in range(1, count + 1):
                file_name = pattern.format(peer=peer_id, size=size_key, num=str(i).zfill(pad_width), ext=ext)
                file_path = os.path.join(shared_dir, file_name)
                if os.path.exists(file_path) and os.path.getsize(file_path) == size_bytes:
                    # Skip existing files with expected size
                    continue
                self._create_file(file_path, size_bytes, chunk_size)
                # Optional: basic progress output
                if i % max(1, count // 10) == 0 or i == count:
                    print(f"[{peer_id}] Generated {size_key}: {i}/{count}")

    def _create_file(self, file_path: str, size_bytes: int, chunk_size: int) -> None:
        # Efficient zero-filled file creation with buffered writes
        remaining = size_bytes
        buf = b"\0" * min(chunk_size, size_bytes or 1)
        with open(file_path, "wb") as f:
            while remaining > 0:
                n = min(chunk_size, remaining)
                if n != len(buf):
                    buf = b"\0" * n
                f.write(buf)
                remaining -= n

    def get_shared_dir(self, peer_id: str) -> str:
        return self._peer_dirs(peer_id).get("shared_dir")

    def get_download_dir(self, peer_id: str) -> str:
        return self._peer_dirs(peer_id).get("download_dir")

    def get_replicated_dir(self, peer_id: str) -> str:
        """Get the replicated directory path for a peer."""
        return self._peer_dirs(peer_id).get("replicated_dir")

    def read_file_chunks(self, peer_id: str, file_name: str, chunk_size: Optional[int] = None):
        """Yield chunks from a file in the peer's shared directory."""
        chunk_size = chunk_size or self._chunk_size()
        shared_dir = self.get_shared_dir(peer_id)
        path = os.path.join(shared_dir, file_name)
        with open(path, "rb") as f:
            while True:
                data = f.read(chunk_size)
                if not data:
                    break
                yield data

    def write_file_chunks(self, dest_path: str, chunks) -> None:
        """Write a sequence of byte chunks to dest_path."""
        os.makedirs(os.path.dirname(dest_path) or ".", exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in chunks:
                if not chunk:
                    break
                f.write(chunk)


def main():
    parser = argparse.ArgumentParser(description="Generate test files for a peer")
    parser.add_argument("--peer", required=True, help="Peer ID (e.g., peer1, peer2)")
    parser.add_argument("--config", default=os.path.join("config", "config.json"), help="Path to config JSON")
    parser.add_argument("--datasets", default="all", help="Comma-separated dataset types: kb,mb,gb or 'all'")

    args = parser.parse_args()
    datasets = None if args.datasets.lower() == "all" else [s.strip() for s in args.datasets.split(",") if s.strip()]

    fm = FileManager(config_path=args.config)
    fm.generate_files(peer_id=args.peer, dataset_types=datasets)


if __name__ == "__main__":
    main()