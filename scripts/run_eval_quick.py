import os
import json
import argparse
import sys
import pathlib

# Ensure project root is on sys.path so sibling packages import correctly
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.weak_scaling import run_weak_scaling
from evaluation.strong_scaling import run_strong_scaling

RESULTS_DIR = os.path.join("evaluation", "results")


def ensure_results_dir():
    os.makedirs(RESULTS_DIR, exist_ok=True)


def save_json(data, name):
    ensure_results_dir()
    path = os.path.join(RESULTS_DIR, f"{name}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    return path


def main():
    parser = argparse.ArgumentParser(description="Quick runner for weak and strong scaling tests")
    parser.add_argument("--config", default=os.path.join("config", "config.json"), help="Path to config.json")
    parser.add_argument("--peer", default="peer1", help="Source peer ID for file lists")
    args = parser.parse_args()

    # Weak scaling: lightweight settings for a quick run
    weak = run_weak_scaling(
        config_path=args.config,
        peer_id=args.peer,
        size_key="kb",
        concurrency_levels=[1, 2],
        requests_per_thread=100,
        max_files=200,
    )
    weak_path = save_json(weak, "weak_scaling_quick")

    # Strong scaling: modest workload sizes; skip GB to avoid heavy I/O
    strong = run_strong_scaling(
        config_path=args.config,
        source_peer_id=args.peer,
        sizes={"kb": 50, "mb": 10, "gb": 0},
        concurrency_levels=[1, 2],
    )
    strong_path = save_json(strong, "strong_scaling_quick")

    # Print summary paths for convenience
    print(json.dumps({
        "weak_results": weak_path,
        "strong_results": strong_path,
    }, indent=2))


if __name__ == "__main__":
    main()