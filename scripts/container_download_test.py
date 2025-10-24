import sys
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from common.metrics import MetricsCollector

CONFIG = '/app/config/docker.peer.json'
TEST_FILE = 'peer1_kb_0001.txt'

fm = FileManager(config_path=CONFIG)
metrics = MetricsCollector()
client = PeerClient(peer_id='peer2', file_manager=fm, metrics=metrics, config_path=CONFIG)

print('Searching for', TEST_FILE)
payload = client.search_file(TEST_FILE)
print(json.dumps(payload, indent=2))

results = payload.get('results', [])
if not results:
    print('No search results found; aborting download test.')
    raise SystemExit(0)

peer = results[0].get('peer', {})
host = peer.get('host') or peer.get('ip') or '127.0.0.1'
port = int(peer.get('port') or 7100)
print(f'Downloading from {host}:{port}')

path, bytes_count, duration = client.download_file(host, port, TEST_FILE)
print('Downloaded:', path, 'bytes:', bytes_count, 'duration:', duration)
print('Metrics:', json.dumps(metrics.get_statistics(), indent=2))