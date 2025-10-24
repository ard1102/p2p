import json
import csv
import os
from typing import Dict, Any, List

from common.config_manager import ConfigManager
from common.metrics import MetricsCollector
from evaluation.weak_scaling import run_weak_scaling, run_test as run_weak_test
from evaluation.strong_scaling import run_strong_scaling, run_small_files_test, run_medium_files_test, run_large_files_test
from peer.peer_client import PeerClient
from peer.file_manager import FileManager


RESULTS_DIR = os.path.join("evaluation", "results")


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def save_json(data: Dict[str, Any], name: str):
    ensure_results_dir()
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def save_csv_from_summary(summary: Dict[str, Any], name: str):
    ensure_results_dir()
    path = os.path.join(RESULTS_DIR, f"{name}.csv")
    # Flatten summary dict-of-dicts
    # Expect structure like {level: {metric: {count, min, max, mean}}}
    header = ["level", "metric", "count", "min", "max", "mean"]
    rows: List[List[Any]] = []
    for level, metrics in summary.items():
        for metric_name, stats in metrics.items():
            if not isinstance(stats, dict):
                # Skip scalar metrics like 'throughput_bytes_per_sec'
                continue
            rows.append([
                level,
                metric_name,
                int(stats.get("count", 0)),
                float(stats.get("min", 0.0)),
                float(stats.get("max", 0.0)),
                float(stats.get("mean", 0.0)),
            ])
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        writer.writerows(rows)
    return path


def generate_text_report(weak_results: Dict[str, Any], strong_results: Dict[str, Any], projections: Dict[str, Any], replication_results: Dict[str, Any] = None) -> str:
    lines: List[str] = []
    lines.append("P2P System Scaling Report")
    lines.append("=")
    lines.append("")
    lines.append("Weak Scaling Summary:")
    for level in weak_results.get("levels", []):
        stats = weak_results["summaries"].get(str(level), {})
        st = stats.get("search_times", {})
        lines.append(f"- Concurrency {level}: searches count={st.get('count',0)}, mean={st.get('mean',0):.4f}s, min={st.get('min',0):.4f}s, max={st.get('max',0):.4f}s")
    lines.append("")
    lines.append("Strong Scaling Summary:")
    for level in strong_results.get("levels", []):
        stats = strong_results["summaries"].get(str(level), {})
        thr_val = stats.get("throughput_bytes_per_sec")
        thr_text = f"{thr_val:.2f} B/s" if isinstance(thr_val, (int, float)) else "n/a"
        sp = stats.get("download_speeds", {})
        lines.append(f"- Concurrency {level}: throughput={thr_text}; speed count={sp.get('count',0)}, mean={sp.get('mean',0):.2f} B/s")
    lines.append("")
    lines.append("Replication Summary:")
    if replication_results:
        tasks_count = int(replication_results.get("tasks_count", 0))
        replicated = replication_results.get("replicated_files", [])
        missing = replication_results.get("missing_files", [])
        ds = replication_results.get("stats", {}).get("download_speeds", {})
        lines.append(f"- Tasks suggested: {tasks_count}; replicated: {len(replicated)}; missing: {len(missing)}")
        lines.append(f"- Download speeds: count={ds.get('count',0)}, mean={ds.get('mean',0):.2f} B/s")
    else:
        lines.append("- No replication data collected.")
    lines.append("")
    lines.append("Projections:")
    lines.append(f"- 1K peers: {projections.get('1k_peers','N/A')}")
    lines.append(f"- 1B peers: {projections.get('1b_peers','N/A')}")
    lines.append("")
    lines.append("Assumptions and Notes:")
    lines.append("- Metrics are aggregated via client-side observations using MetricsCollector.")
    lines.append("- Network/setup overhead is assumed homogeneous across concurrency levels.")
    lines.append("- For projections, we apply simple linear scaling with contention factor.")
    return "\n".join(lines)


# --- New: Final report writer including Weak(1,2), Strong(sizes), Replication, Projections ---

def _write_text_report(path: str, weak_1: Dict[str, Any], weak_2: Dict[str, Any], strong_small: Dict[str, Any], strong_medium: Dict[str, Any], strong_large: Dict[str, Any], replication_results: Dict[str, Any], projections: Dict[str, Any]) -> str:
    def _fmt_search(summary: Dict[str, Any]) -> str:
        st = summary.get("search_times", {})
        return f"count={st.get('count',0)}, mean={st.get('mean',0):.4f}s, min={st.get('min',0):.4f}s, max={st.get('max',0):.4f}s"

    def _fmt_speed(summary: Dict[str, Any]) -> str:
        sp = summary.get("download_speeds", {})
        return f"count={sp.get('count',0)}, mean={sp.get('mean',0):.2f} B/s, min={sp.get('min',0):.2f}, max={sp.get('max',0):.2f}"

    lines: List[str] = []
    lines.append("P2P System Scaling Report")
    lines.append("=")
    lines.append("")

    lines.append("Weak Scaling (1 vs 2 Peers):")
    lines.append(f"- 1 Peer: {_fmt_search(weak_1.get('summary', {}))}")
    lines.append(f"- 2 Peers: {_fmt_search(weak_2.get('summary', {}))}")
    m1 = weak_1.get('summary', {}).get('search_times', {}).get('mean', 0.0)
    m2 = weak_2.get('summary', {}).get('search_times', {}).get('mean', 0.0)
    ratio = (m1 / m2) if m2 else 0.0
    lines.append(f"- Scalability to 2 nodes: mean latency ratio ~ {ratio:.2f} (higher is better)")
    lines.append("")

    lines.append("Strong Scaling Across File Sizes (2 Peers):")
    lines.append(f"- Small (10K × 1KB): {_fmt_speed(strong_small.get('summary', {}))}")
    lines.append(f"- Medium (1K × 1MB): {_fmt_speed(strong_medium.get('summary', {}))}")
    lines.append(f"- Large (8 × 1GB): {_fmt_speed(strong_large.get('summary', {}))}")
    lines.append("")

    lines.append("Replication Summary:")
    if replication_results:
        tasks_count = int(replication_results.get("tasks_count", 0))
        replicated = replication_results.get("replicated_files", [])
        missing = replication_results.get("missing_files", [])
        ds = replication_results.get("stats", {}).get("download_speeds", {})
        lines.append(f"- Tasks suggested: {tasks_count}; replicated: {len(replicated)}; missing: {len(missing)}")
        lines.append(f"- Download speeds: count={ds.get('count',0)}, mean={ds.get('mean',0):.2f} B/s")
    else:
        lines.append("- No replication data collected.")
    lines.append("")

    lines.append("Scalability Analysis:")
    lines.append("- Up to 2 nodes: Compare mean search latencies; ratio indicates coordination overhead vs concurrency benefit.")
    lines.append("- Across file sizes: Small files show higher ops/sec, large files emphasize throughput; medium typically balances I/O and protocol overhead.")
    lines.append("")

    lines.append("Projections:")
    lines.append(f"- 1K peers: {projections.get('1k_peers','N/A')}")
    lines.append(f"- 1B peers: {projections.get('1b_peers','N/A')}")

    ensure_results_dir()
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    return path


def project_scaling(weak_results: Dict[str, Any], strong_results: Dict[str, Any]) -> Dict[str, Any]:
    # Very simple projections based on observed mean latencies and throughput
    # This is a placeholder; adjust with real model once data is available
    proj = {}
    # Take last level as representative
    if weak_results.get("levels"):
        last_level = weak_results["levels"][ -1]
        mean_search = weak_results["summaries"].get(str(last_level), {}).get("search_times", {}).get("mean", 0.0)
    else:
        mean_search = 0.0
    if strong_results.get("levels"):
        last_level_s = strong_results["levels"][ -1]
        mean_speed = strong_results["summaries"].get(str(last_level_s), {}).get("download_speeds", {}).get("mean", 0.0)
    else:
        mean_speed = 0.0
    # Projection formulas
    proj["1k_peers"] = f"Estimated mean search latency: {mean_search:.4f}s; mean download speed: {mean_speed:.2f} B/s (assuming proportional concurrency and constant per-peer capacity)."
    proj["1b_peers"] = f"At extreme scale, expect directory service contention and network saturation; naive extrapolation: mean latency ~ {mean_search*10:.4f}s; mean speed ~ {mean_speed/10:.2f} B/s (requires hierarchical indexing and CDN-like replication)."
    return proj


# New projections based on final tests

def project_scaling_final(weak_1: Dict[str, Any], weak_2: Dict[str, Any], strong_small: Dict[str, Any], strong_medium: Dict[str, Any], strong_large: Dict[str, Any]) -> Dict[str, Any]:
    m_search = weak_2.get('summary', {}).get('search_times', {}).get('mean', 0.0)
    # Prefer medium file speed if available
    m_speed = strong_medium.get('summary', {}).get('download_speeds', {}).get('mean', 0.0)
    if not m_speed:
        m_speed = strong_small.get('summary', {}).get('download_speeds', {}).get('mean', 0.0)
    if not m_speed:
        m_speed = strong_large.get('summary', {}).get('download_speeds', {}).get('mean', 0.0)
    proj = {}
    proj["1k_peers"] = f"Estimated mean search latency: {m_search:.4f}s; mean download speed: {m_speed:.2f} B/s (assuming proportional concurrency and constant per-peer capacity)."
    proj["1b_peers"] = f"At extreme scale, expect directory service contention and network saturation; naive extrapolation: mean latency ~ {m_search*10:.4f}s; mean speed ~ {m_speed/10:.2f} B/s (requires hierarchical indexing and CDN-like replication)."
    return proj


def run_replication_test(config_path: str, new_peer_id: str = "peer_eval_replica") -> Dict[str, Any]:
    cm = ConfigManager()
    cm.load_config(config_path)
    fm = FileManager(config_path=config_path)
    metrics = MetricsCollector()
    client = PeerClient(peer_id=new_peer_id, file_manager=fm, metrics=metrics, config_path=config_path)

    # Ensure clean shared directory for the test peer
    shared_dir = fm.get_shared_dir(new_peer_id)
    os.makedirs(shared_dir, exist_ok=True)
    try:
        for name in os.listdir(shared_dir):
            path = os.path.join(shared_dir, name)
            if os.path.isfile(path):
                os.remove(path)
    except Exception:
        pass

    # Register and (client will) auto-run replication tasks if suggested
    payload = client.register_with_server(peer_ip=None, peer_port=None)
    tasks = payload.get("replication_tasks", [])

    # Verify replicated files exist
    file_names = [t.get("file_name") for t in tasks if isinstance(t, dict) and t.get("file_name")]
    replicated = []
    missing = []
    for fn in file_names:
        if os.path.isfile(os.path.join(shared_dir, fn)):
            replicated.append(fn)
        else:
            missing.append(fn)

    stats = metrics.get_statistics()
    return {
        "peer_id": new_peer_id,
        "tasks_count": len(tasks),
        "replicated_files": replicated,
        "missing_files": missing,
        "stats": stats,
    }


def run_all(config_path: str) -> Dict[str, Any]:
    cm = ConfigManager()
    cm.load_config(config_path)

    # Final Weak Scaling: 1 peer and 2 peers
    weak_1 = run_weak_test(config_path=config_path, num_peers=1)
    weak_2 = run_weak_test(config_path=config_path, num_peers=2)

    # Final Strong Scaling: small/medium/large tests (use 2 peers)
    strong_small = run_small_files_test(config_path=config_path, num_peers=2)
    strong_medium = run_medium_files_test(config_path=config_path, num_peers=2)
    strong_large = run_large_files_test(config_path=config_path, num_peers=2)

    # Replication Test
    replication = run_replication_test(config_path=config_path)

    # Projections based on final tests
    proj = project_scaling_final(weak_1, weak_2, strong_small, strong_medium, strong_large)

    # Persist JSON
    save_json(weak_1, "weak_test_1_peer")
    save_json(weak_2, "weak_test_2_peers")
    save_json(strong_small, "strong_small")
    save_json(strong_medium, "strong_medium")
    save_json(strong_large, "strong_large")
    save_json(replication, "replication")
    save_json(proj, "projections_final")

    # Persist CSV summaries
    save_csv_from_summary({"1_peer": weak_1.get("summary", {})}, "weak_test_1_peer_summary")
    save_csv_from_summary({"2_peers": weak_2.get("summary", {})}, "weak_test_2_peers_summary")
    save_csv_from_summary({"small": strong_small.get("summary", {})}, "strong_small_summary")
    save_csv_from_summary({"medium": strong_medium.get("summary", {})}, "strong_medium_summary")
    save_csv_from_summary({"large": strong_large.get("summary", {})}, "strong_large_summary")
    save_csv_from_summary(replication.get("stats", {}), "replication_summary")

    # Final Report
    ensure_results_dir()
    report_path = os.path.join(RESULTS_DIR, "report.txt")
    _write_text_report(report_path, weak_1, weak_2, strong_small, strong_medium, strong_large, replication, proj)

    return {
        "weak_1": weak_1,
        "weak_2": weak_2,
        "strong_small": strong_small,
        "strong_medium": strong_medium,
        "strong_large": strong_large,
        "replication": replication,
        "projections": proj,
        "report_path": report_path,
    }


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run P2P evaluation tests")
    parser.add_argument("config", help="Path to config.json")
    args = parser.parse_args()
    res = run_all(args.config)
    print(json.dumps({"report": res["report_path"]}, indent=2))