import os
import json
import argparse
import sys
import pathlib

# Ensure project root is on sys.path so sibling packages import correctly
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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
    parser = argparse.ArgumentParser(description="Run heavier strong scaling sweep")
    parser.add_argument("--config", default=os.path.join("config", "config.json"), help="Path to config.json")
    parser.add_argument("--peer", default="peer1", help="Source peer ID for file lists")
    parser.add_argument("--kb", type=int, default=200, help="Number of KB files to include")
    parser.add_argument("--mb", type=int, default=20, help="Number of MB files to include")
    parser.add_argument("--concurrency", nargs="+", type=int, default=[1, 2, 4], help="Concurrency levels to test")
    args = parser.parse_args()

    sizes = {"kb": args.kb, "mb": args.mb, "gb": 0}

    strong = run_strong_scaling(
        config_path=args.config,
        source_peer_id=args.peer,
        sizes=sizes,
        concurrency_levels=args.concurrency,
    )
    out_path = save_json(strong, "strong_scaling_sweep")

    # Print summary path for convenience
    print(json.dumps({
        "strong_results": out_path,
        "levels": strong.get("levels", []),
    }, indent=2))


if __name__ == "__main__":
    main()