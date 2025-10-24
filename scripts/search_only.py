import json
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from common.metrics import MetricsCollector


def run_search(file_name: str):
    fm = FileManager(config_path="config/config.json")
    client = PeerClient("peer2", fm, MetricsCollector(), config_path="config/config.json", logger_name="peer2_search")
    payload = client.search_file(file_name)
    print("SEARCH RESULT:")
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    # Pick a file that should be replicated
    run_search("peer1_kb_0011.txt")