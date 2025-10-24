import sys, pathlib, json, traceback
ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from common.config_manager import ConfigManager
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from common.metrics import MetricsCollector
from evaluation.strong_scaling import _build_file_list

CONFIG = '/app/config/docker.peer.json'
SOURCE_PEER = 'peer1'

cm = ConfigManager(); cm.load_config(CONFIG)
fm = FileManager(config_path=CONFIG)
metrics = MetricsCollector()
client = PeerClient(peer_id='peer2', file_manager=fm, metrics=metrics, config_path=CONFIG)

kb_list = _build_file_list(cm, SOURCE_PEER, 'kb', 5)
mb_list = _build_file_list(cm, SOURCE_PEER, 'mb', 2)
print('KB files:', kb_list)
print('MB files:', mb_list)

success = 0
errors = []
for fname in kb_list + mb_list:
    try:
        payload = client.search_file(fname)
        results = payload.get('results', [])
        if not results:
            raise RuntimeError('No search results')
        peer = results[0].get('peer', {})
        host = peer.get('host') or peer.get('ip') or '127.0.0.1'
        port = int(peer.get('port') or 7100)
        dest, bytes_count, duration = client.download_file(host, port, fname)
        print('OK', fname, bytes_count, 'bytes in', duration, 'sec ->', dest)
        success += 1
    except Exception as e:
        print('ERR', fname, str(e))
        errors.append({'file': fname, 'error': str(e), 'trace': traceback.format_exc()})

print('Summary:', {'success': success, 'errors': len(errors)})
print(json.dumps({'errors': errors, 'metrics': metrics.get_statistics()}, indent=2))