import os
import math
import threading
from typing import List, Dict, Any

from common.config_manager import ConfigManager
from common.metrics import MetricsCollector
from peer.peer_client import PeerClient
from peer.file_manager import FileManager


def _build_file_list(cm: ConfigManager, peer_id: str, size_key: str, max_count: int) -> List[str]:
    fg = cm.get("data.file_generation", {})
    pattern = fg.get("pattern", "{peer}_{size}_{num}.{ext}")
    cfg = fg.get(size_key, {})
    count = int(cfg.get("count", 0))
    ext = cfg.get("extension", "bin")
    pad_width = max(4, int(math.log10(max(1, count))) + 1)
    n = min(count, max_count)
    return [
        pattern.format(peer=peer_id, size=size_key, num=str(i).zfill(pad_width), ext=ext)
        for i in range(1, n + 1)
    ]


def _download_worker(worker_id: int, config_path: str, files: List[str], out_downloads: List[Dict[str, float]], out_speeds: List[float], lock: threading.Lock, sink_peer_id: str = "peer2"):
    cm = ConfigManager()
    cm.load_config(config_path)
    fm = FileManager(config_path=config_path)
    metrics = MetricsCollector()
    # Use a sink peer ID that exists in config to resolve download dir
    client = PeerClient(peer_id=sink_peer_id, file_manager=fm, metrics=metrics, config_path=config_path)

    for fname in files:
        try:
            payload = client.search_file(fname)
            results = payload.get("results", [])
            if not results:
                print(f"[worker {worker_id}] No search results for {fname}")
                continue
            target = results[0]
            peer = target.get("peer", {})
            host = peer.get("host") or peer.get("ip") or "127.0.0.1"
            port = int(peer.get("port") or int(cm.get("peer.base_port", 7100)))
            dest_path, bytes_count, duration = client.download_file(host, port, fname)
            print(f"[worker {worker_id}] OK {fname} -> {dest_path} ({bytes_count} bytes in {duration:.4f}s)")
        except Exception as e:
            print(f"[worker {worker_id}] ERR {fname}: {e}")
            continue

    # Merge metrics into shared collectors
    with lock:
        out_downloads.extend(metrics.downloads)
        out_speeds.extend(metrics.download_speeds)


def run_strong_scaling(config_path: str, source_peer_id: str = "peer1", sizes: Dict[str, int] = None, concurrency_levels: List[int] = None) -> Dict[str, Any]:
    """
    Run strong scaling tests: fixed total workload while varying concurrency.
    sizes: dict of {"kb": small_count, "mb": medium_count, "gb": large_count}
    Returns dict with per-level throughput and download speed summaries.
    """
    if sizes is None:
        sizes = {"kb": 50, "mb": 20, "gb": 1}
    if concurrency_levels is None:
        concurrency_levels = [1, 2, 4]

    cm = ConfigManager()
    cm.load_config(config_path)

    # Prepare workload (list of files to download)
    workload: List[str] = []
    for size_key, count in sizes.items():
        workload.extend(_build_file_list(cm, source_peer_id, size_key, count))
    print(f"[strong] Built workload of {len(workload)} files from sizes={sizes}")

    results: Dict[str, Any] = {"levels": [], "summaries": {}, "raw": {}}

    for level in concurrency_levels:
        # Partition workload across threads
        partitions: List[List[str]] = [[] for _ in range(level)]
        for idx, fname in enumerate(workload):
            partitions[idx % level].append(fname)
        print(f"[strong] Starting level={level}, partitions={[len(p) for p in partitions]}")

        downloads: List[Dict[str, float]] = []
        speeds: List[float] = []
        lock = threading.Lock()
        threads: List[threading.Thread] = []

        for i in range(level):
            t = threading.Thread(target=_download_worker, args=(i, config_path, partitions[i], downloads, speeds, lock, "peer2"), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Summarize
        mc = MetricsCollector()
        for d in downloads:
            mc.record_download(d.get("bytes", 0.0), d.get("duration", 0.0))
        for s in speeds:
            mc.record_download_speed(s)
        stats = mc.get_statistics()
        results["levels"].append(level)
        results["summaries"][str(level)] = stats
        results["raw"][str(level)] = {"downloads": downloads, "speeds": speeds}
    return results

# --- New APIs for final strong scaling studies ---

def _build_repeated_workload(cm: ConfigManager, source_peer_id: str, size_key: str, count: int) -> List[str]:
    base = _build_file_list(cm, source_peer_id, size_key, max_count=count)
    if not base:
        return []
    # Repeat the available files to reach the requested count
    workload: List[str] = []
    idx = 0
    for _ in range(count):
        workload.append(base[idx])
        idx = (idx + 1) % len(base)
    return workload


def _run_fixed_workload(config_path: str, workload: List[str], concurrency: int) -> Dict[str, Any]:
    partitions: List[List[str]] = [[] for _ in range(concurrency)]
    for i, fname in enumerate(workload):
        partitions[i % concurrency].append(fname)

    downloads: List[Dict[str, float]] = []
    speeds: List[float] = []
    lock = threading.Lock()
    threads: List[threading.Thread] = []

    for i in range(concurrency):
        t = threading.Thread(target=_download_worker, args=(i, config_path, partitions[i], downloads, speeds, lock, "peer2"), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    mc = MetricsCollector()
    for d in downloads:
        mc.record_download(d.get("bytes", 0.0), d.get("duration", 0.0))
    for s in speeds:
        mc.record_download_speed(s)
    stats = mc.get_statistics()

    return {
        "concurrency": concurrency,
        "summary": stats,
        "raw": {"downloads": downloads, "speeds": speeds},
    }


def run_small_files_test(config_path: str, num_peers: int, source_peer_id: str = "peer1") -> Dict[str, Any]:
    """
    10,000 files of size ~1KB; each file is searched then downloaded.
    Concurrency equals num_peers.
    """
    cm = ConfigManager()
    cm.load_config(config_path)
    workload = _build_repeated_workload(cm, source_peer_id, "kb", 10_000)
    result = _run_fixed_workload(config_path, workload, max(1, int(num_peers)))
    result.update({"total_files": 10_000, "size": "kb", "num_peers": max(1, int(num_peers))})
    return result


def run_medium_files_test(config_path: str, num_peers: int, source_peer_id: str = "peer1") -> Dict[str, Any]:
    """
    1,000 files of size ~1MB; each file is searched then downloaded.
    Concurrency equals num_peers.
    """
    cm = ConfigManager()
    cm.load_config(config_path)
    workload = _build_repeated_workload(cm, source_peer_id, "mb", 1_000)
    result = _run_fixed_workload(config_path, workload, max(1, int(num_peers)))
    result.update({"total_files": 1_000, "size": "mb", "num_peers": max(1, int(num_peers))})
    return result


def run_large_files_test(config_path: str, num_peers: int, source_peer_id: str = "peer1") -> Dict[str, Any]:
    """
    8 files of size ~1GB; each file is searched then downloaded.
    Concurrency equals num_peers.
    """
    cm = ConfigManager()
    cm.load_config(config_path)
    workload = _build_repeated_workload(cm, source_peer_id, "gb", 8)
    result = _run_fixed_workload(config_path, workload, max(1, int(num_peers)))
    result.update({"total_files": 8, "size": "gb", "num_peers": max(1, int(num_peers))})
    return result