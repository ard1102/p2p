import os
import math
import random
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


def _search_worker(worker_id: int, config_path: str, file_names: List[str], requests: int, out_times: List[float], lock: threading.Lock):
    cm = ConfigManager()
    cm.load_config(config_path)
    fm = FileManager(config_path=config_path)
    metrics = MetricsCollector()
    client = PeerClient(peer_id=f"eval{worker_id}", file_manager=fm, metrics=metrics, config_path=config_path)

    for _ in range(requests):
        fname = random.choice(file_names)
        try:
            client.search_file(fname)
        except Exception:
            # Even on failure, record that a search attempt occurred
            pass
    # Merge metrics into shared list
    with lock:
        out_times.extend(metrics.search_times)


def run_weak_scaling(config_path: str, peer_id: str = "peer1", size_key: str = "kb", concurrency_levels: List[int] = None, requests_per_thread: int = 50, max_files: int = 100) -> Dict[str, Any]:
    """
    Run weak scaling tests: increase concurrency while each thread performs a fixed number of searches.
    Returns a dict with per-level summaries.
    """
    if concurrency_levels is None:
        concurrency_levels = [1, 2, 4, 8]

    cm = ConfigManager()
    cm.load_config(config_path)

    # Build a pool of file names for the given size
    file_pool = _build_file_list(cm, peer_id, size_key, max_files)
    results: Dict[str, Any] = {"levels": [], "summaries": {}, "raw": {}}

    for level in concurrency_levels:
        times: List[float] = []
        lock = threading.Lock()
        threads: List[threading.Thread] = []

        for i in range(level):
            t = threading.Thread(target=_search_worker, args=(i, config_path, file_pool, requests_per_thread, times, lock), daemon=True)
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Summarize
        mc = MetricsCollector()
        for v in times:
            mc.record_search_time(v)
        summary = mc.get_statistics()["search_times"]
        results["levels"].append(level)
        results["summaries"][str(level)] = summary
        results["raw"][str(level)] = times
    return results

# --- New API for final weak scaling study ---

def run_test(config_path: str, num_peers: int, peer_id: str = "peer1", size_key: str = "kb", max_files: int = 100) -> Dict[str, Any]:
    """
    Final weak scaling test:
    - Simulates 10,000 * num_peers total search requests
    - Uses a thread pool with concurrency = num_peers
    - Records statistics using MetricsCollector
    """
    cm = ConfigManager()
    cm.load_config(config_path)
    file_pool = _build_file_list(cm, peer_id, size_key, max_files)

    concurrency = max(1, int(num_peers))
    total_requests = 10_000 * concurrency

    # Distribute requests across threads as evenly as possible
    base = total_requests // concurrency
    remainder = total_requests % concurrency

    times: List[float] = []
    lock = threading.Lock()
    threads: List[threading.Thread] = []

    for i in range(concurrency):
        reqs = base + (1 if i < remainder else 0)
        t = threading.Thread(target=_search_worker, args=(i, config_path, file_pool, reqs, times, lock), daemon=True)
        threads.append(t)
        t.start()

    for t in threads:
        t.join()

    mc = MetricsCollector()
    for v in times:
        mc.record_search_time(v)
    summary = mc.get_statistics()["search_times"]

    return {
        "num_peers": concurrency,
        "total_requests": total_requests,
        "concurrency": concurrency,
        "summary": {"search_times": summary},
        "raw_times": times,
        "file_pool_size": len(file_pool),
    }