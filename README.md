# P2P File Sharing System

A lightweight peer-to-peer file sharing system with a central Indexing Server for metadata (peer registry and file index) and multiple Peer nodes that can register, search, obtain, and replicate files. The project includes evaluation scripts and a Docker Compose setup to run a full local simulation.

## Overview
- Indexing Server: Tracks peers and the files they serve; handles search queries.
- Peer Nodes: Each peer runs a server to serve files and a client to register, search, and download.
- Data Layout: Per-peer directories `shared/`, `downloaded/`, and `replicated/` (see `config/config.json`).
- Protocol: Simple JSON messages framed over TCP sockets; file bytes are streamed after metadata on the same socket.

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              Indexing Server (Port 7000)                     │
│  ┌────────────────────────────────────────────────────────┐ │
│  │ • File Index: Maps filenames → peer locations          │ │
│  │ • Peer Registry: Tracks active peers                   │ │
│  │ • Replication Coordinator: Ensures RF=2                │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────┬───────────────────────────────────────────┘
                  │ TCP/Socket Communication
        ┌─────────┴─────────┐
        │                   │
┌───────▼────────┐   ┌──────▼────────┐
│  Peer 1        │   │  Peer 2       │
│  Port: 7100    │◄─┤  Port: 7101   │ P2P File Transfer
├────────────────┤   ├───────────────┤
│ Components:    │   │ Components:   │
│ • Peer Server  │   │ • Peer Server │
│ • Peer Client  │   │ • Peer Client │
│ • File Manager │   │ • File Manager│
├────────────────┤   ├───────────────┤
│ Directories:   │   │ Directories:  │
│ • shared/      │   │ • shared/     │
│ • downloaded/  │   │ • downloaded/ │
│ • replicated/  │   │ • replicated/ │
└────────────────┘   └───────────────┘
```

**Data Flow:**
1. **Registration**: Peer → Indexing Server (list of files)
2. **Search**: Peer → Indexing Server (query) → Response (peer list)
3. **Download**: Peer ↔ Peer (direct file transfer)
4. **Replication**: Server suggests → Target Peer fetches → Updates Server

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
## Interactive CLI Commands

Start an interactive peer with:
```powershell
python -m peer.peer config/config.json --peer peer1
```

### Available Commands

| Command | Description | Example |
|---------|-------------|---------|
| `lookup <filename>` | Search for a file across all registered peers | `lookup peer2_kb_0050.txt` |
| `download <filename>` | Download file from a discovered peer | `download peer2_kb_0050.txt` |
| `list local` | List files in the shared directory | `list local` |
| `list downloaded` | List files in the downloaded directory | `list downloaded` |
| `list replicated` | List files in the replicated directory | `list replicated` |
| `stats` | Display performance statistics (search times, download speeds) | `stats` |
| `help` | Show available commands | `help` |
| `exit` | Quit the peer CLI | `exit` |

### Example Session

```powershell
> lookup peer2_kb_0050.txt
Peers serving 'peer2_kb_0050.txt':
  - peer2 @ 127.0.0.1:7101

> download peer2_kb_0050.txt
Downloaded 'peer2_kb_0050.txt' from 127.0.0.1:7101 -> data/peer1/downloaded/peer2_kb_0050.txt 
(1024 bytes in 0.05s, 20.48 KB/s)

> list downloaded
Downloaded files (1):
  - peer2_kb_0050.txt (1024 bytes)

> list replicated
Replicated files (5):
  - peer2_kb_0010.txt (1024 bytes)
  - peer2_kb_0025.txt (1024 bytes)
  - peer2_mb_0001.bin (1048576 bytes)
  - peer2_mb_0002.bin (1048576 bytes)
  - peer2_mb_0003.bin (1048576 bytes)

> stats
Performance stats:
  Search time: mean=0.0123s stdev=0.0045s min=0.0089s max=0.0201s
  Download speed (B/s): mean=204800.0 stdev=15234.5 min=180000.0 max=230000.0
  Throughput: 198450.5 B/s

> exit
Shutting down peer...
Peer stopped.
```

### Headless Mode (No CLI)

For server deployments or Docker containers:
```powershell
python -m peer.headless config/config.json --peer peer1
```
Runs indefinitely, automatically registers, and serves files without user interaction.

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

## Design Patterns

This project implements professional software engineering patterns for maintainability, scalability, and thread safety:

### 1. Singleton Pattern
**Used in**: `ConfigManager`, `Logger`

**Purpose**: Ensure only one instance exists across all threads
```python
class ConfigManager:
    _instance = None
    _lock = threading.Lock()
    
    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
        return cls._instance
```

**Benefits**:
- Thread-safe configuration access
- Centralized logging across components
- Prevents configuration conflicts

---

### 2. Command Pattern
**Used in**: `CommandHandler` (CLI interface)

**Purpose**: Encapsulate each user command as an object
```python
# Each CLI command is mapped to a handler method
commands = {
    "lookup": self._lookup,
    "download": self._download,
    "list": self._list_handler,
    "stats": self._stats
}
```

**Benefits**:
- Easy to add new commands without modifying core logic
- Separation of concerns (UI vs business logic)
- Testable command handlers

---

### 3. Strategy Pattern
**Used in**: File transfer (chunked streaming)

**Purpose**: Handle different file sizes with appropriate strategies
```python
# Small files: Single chunk
# Large files: Streaming chunks to avoid memory overflow
def read_file_chunks(file_path, chunk_size=8192):
    with open(file_path, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk
```

**Benefits**:
- Memory-efficient for large files (1GB+)
- Constant memory usage regardless of file size
- Supports files larger than available RAM

---

### 4. Observer Pattern (Implicit)
**Used in**: Replication notifications

**Purpose**: Notify peers when replication tasks are available
```python
# Server notifies peer during registration
if replication_needed:
    response["replication_tasks"] = tasks
    # Peer observes and acts on tasks
```

**Benefits**:
- Loose coupling between server and peers
- Asynchronous replication
- Scalable notification mechanism

---

### 5. Thread-Safe Data Structures
**Used in**: `FileIndex`

**Purpose**: Protect shared data from race conditions
```python
class FileIndex:
    def __init__(self):
        self._lock = threading.Lock()
        self.file_index = {}
    
    def add_file(self, file_name, peer_id):
        with self._lock:  # Thread-safe access
            self.file_index[file_name].append(peer_id)
```

**Benefits**:
- Prevents data corruption in concurrent environment
- Safe multi-threaded server operation
- Consistent index state across all operations

---

### Design Pattern Summary

| Pattern | Location | Key Benefit |
|---------|----------|-------------|
| **Singleton** | Config, Logger | Single source of truth |
| **Command** | CLI Handler | Extensible commands |
| **Strategy** | File Transfer | Memory efficiency |
| **Observer** | Replication | Loose coupling |
| **Thread-Safe** | File Index | Data integrity |

These patterns enable the system to handle:
- ✅ Concurrent peer connections (100+ simultaneous)
- ✅ Files of any size (KB to GB+)
- ✅ Multiple threads per component
- ✅ Easy feature additions
- ✅ Production-grade reliability

## Maintenance
- Use `make clean` to remove `data`, `logs`, and `evaluation/results`.
- `__pycache__/` directories contain Python bytecode; safe to remove when cleaning.

## License
No explicit license provided. Do not redistribute.