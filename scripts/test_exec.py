import json
from peer.file_manager import FileManager
from peer.peer_client import PeerClient
from common.metrics import MetricsCollector


def main():
    file_name = "peer1_kb_0001.txt"
    fm = FileManager(config_path="config/config.json")
    client = PeerClient("peer2", fm, MetricsCollector(), config_path="config/config.json", logger_name="peer2_exec")

    payload = client.search_file(file_name)
    print("SEARCH RESULT:")
    print(json.dumps(payload, indent=2))

    results = payload.get("results", [])
    if results:
        peer_info = results[0].get("peer", {})
        host = peer_info.get("host") or peer_info.get("ip") or "127.0.0.1"
        port = int(peer_info.get("port") or 7100)
        print(f"DOWNLOADING from {host}:{port} ...")
        dest_path, bytes_count, duration = client.download_file(host, port, file_name)
        print(f"DOWNLOADED: {dest_path} ({bytes_count} bytes in {duration:.2f}s)")
    else:
        print("No peers found for test file")


if __name__ == "__main__":
    main()