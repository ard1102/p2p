# P2P File Sharing System

A lightweight peer-to-peer file sharing system with a central Indexing Server for metadata (peer registry and file index) and multiple Peer nodes that can register, search, obtain, and replicate files. The project includes evaluation scripts and a Docker Compose setup to run a full local simulation.

## Overview
- Indexing Server: Tracks peers and the files they serve; handles search queries.
- Peer Nodes: Each peer runs a server to serve files and a client to register, search, and download.
- Data Layout: Per-peer directories `shared/`, `downloaded/`, and `replicated/` (see `config/config.json`).
- Protocol: Simple JSON messages framed over TCP sockets; file bytes are streamed after metadata on the same socket.

## Directory Structure
- `common/` — Config manager, metrics, protocol helpers.
- `indexing_server/` — Server entrypoint and services (`server.py`, `search_service.py`, `registry_service.py`).
- `peer/` — Peer server, client, CLI handler, and file manager (`peer_server.py`, `peer_client.py`, `command_handler.py`, `file_manager.py`).
- `evaluation/` — Weak and strong scaling runners plus `results/` for outputs.
- `scripts/` — Convenience scripts: quick eval, strong sweep, plotting, and ad-hoc tests.
- `config/` — `config.json` for host runs; `docker.peer.json` and `docker.server.json` for Compose runs.
- `docker-compose.yml` — Starts `indexing-server`, `peer1`, and `peer2` services.

## Prerequisites
- Python 3.11+
- Windows PowerShell (paths/examples use Windows style)
- Optional: Docker Desktop (for Compose runs)
- Optional: GNU Make (recommended for one-command workflows)

Virtual environment (optional): see `VENV_ACTIVATION_GUIDE.md` or:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```
For plotting, install `matplotlib`:
```powershell
pip install matplotlib
```

## Make-Driven Workflow (Windows)
Install GNU Make via Windows Package Manager:
```powershell
winget install -e --id GnuWin32.Make --accept-package-agreements --accept-source-agreements
```
Common targets:
- `make setup` — Create data and logs directories.
- `make generate-peer1` — Generate test files for peer1.
- `make generate-peer2` — Generate test files for peer2.
- `make docker-up` — Build and start `indexing-server`, `peer1`, `peer2` (depends on `setup`).
- `make docker-test` — Run containerized search+download test from `peer2`.
- `make docker-logs` — Tail logs for server and peers.
- `make docker-down` — Stop all Compose services.
- `make docker-clean` — Stop and remove volumes and orphans.
- `make clean` — Remove `data`, `logs`, and `evaluation/results`.

Quick start (Make):
```powershell
make generate-peer1
make docker-up
make docker-test
make docker-down
```
The test downloads `peer1_kb_0001.txt` into `data/peer2/downloaded/` and writes logs under `logs/peer1`, `logs/peer2`, and `logs/server` on the host.

## Docker Compose (Manual)
Bring up the stack manually:
```powershell
docker compose up -d --build
```
Logs:
```powershell
docker compose logs --tail=100 indexing-server peer1 peer2
```
Stop and clean up:
```powershell
docker compose down
```
Note: Docker may warn that the `version` attribute in `docker-compose.yml` is obsolete; it is safe to ignore or remove.

## Run (Locally on Host)
Start the Indexing Server:
```powershell
python -m indexing_server.server
```
Start a headless peer (generates files if empty, registers, and runs indefinitely):
```powershell
python -m peer.headless config/config.json --peer peer1
python -m peer.headless config/config.json --peer peer2
```
Start an interactive peer with CLI:
```powershell
python -m peer.peer config/config.json --peer peer1
```
Commands:
- `lookup <filename>` — Search for a file
- `download <filename>` — Download from a peer
- `list local` — List locally shared files
- `stats` — Show metrics; `exit` — Quit

Generate datasets explicitly (optional):
```powershell
python -m peer.file_manager --peer peer1
python -m peer.file_manager --peer peer2
```

## Data & Logs
- Host bind mounts persist data and logs during Compose runs:
  - `data/peer1/shared`, `data/peer1/downloaded`
  - `data/peer2/shared`, `data/peer2/downloaded`
  - `logs/peer1`, `logs/peer2`, `logs/server`
- After `docker-test`, the downloaded file is visible under `data/peer2/downloaded/` on the host.

## Quick Evaluation
Run both weak and strong scaling tests and save JSON summaries:
```powershell
python scripts/run_eval_quick.py --config config/config.json --peer peer1
```
Outputs:
- `evaluation/results/weak_scaling_quick.json`
- `evaluation/results/strong_scaling_quick.json`

## Strong Scaling Sweep and Plot
Heavier sweep and throughput plotting:
```powershell
python scripts/run_strong_sweep.py --config config/config.json --peer peer1 --kb 200 --mb 20 --concurrency 1 2 4
python scripts/plot_throughput.py --input evaluation/results/strong_scaling_sweep.json --output evaluation/results/strong_throughput.png
```

## Notes & Tips
- Peers compute ports from `peer.base_port` + index in ID (e.g., `peer2 → base_port+1`).
- If search returns no results, ensure peers have generated files (e.g., `make generate-peer1`) and registered successfully.
- Throughput may decline with increased concurrency in Docker due to shared resource limits; adjust dataset sizes and concurrency for your environment.

## Maintenance
- Use `make clean` to remove `data`, `logs`, and `evaluation/results`.
- `__pycache__/` directories contain Python bytecode; safe to remove when cleaning.

## License
No explicit license provided. Do not redistribute.