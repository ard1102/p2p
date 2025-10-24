import sys
import pathlib
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from common.metrics import MetricsCollector

fm = FileManager(config_path='/app/config/docker.peer.json')
client = PeerClient(peer_id='evaldl', file_manager=fm, metrics=MetricsCollector(), config_path='/app/config/docker.peer.json')
payload = client.search_file('peer1_kb_0001.txt')
print(json.dumps(payload, indent=2))