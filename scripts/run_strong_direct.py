import sys, pathlib, json
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evaluation.strong_scaling import run_strong_scaling

CONFIG = '/app/config/docker.peer.json'
results = run_strong_scaling(config_path=CONFIG, source_peer_id='peer1', sizes={'kb':5, 'mb':2, 'gb':0}, concurrency_levels=[1,2])
print(json.dumps(results, indent=2))