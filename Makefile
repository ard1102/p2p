PYTHON=python
COMPOSE=docker compose

.PHONY: setup clean help generate-peer1 generate-peer2 run-peer1 run-peer2 run-server \
        docker-build docker-up docker-ps docker-test docker-logs docker-down docker-clean

help:
	@echo "Available targets:"
	@echo "  setup            - Create data and logs directories"
	@echo "  clean            - Remove generated data and logs"
	@echo "  generate-peer1   - Generate test files for peer1"
	@echo "  generate-peer2   - Generate test files for peer2"
	@echo "  run-peer1        - Start peer1 (server + CLI)"
	@echo "  run-peer2        - Start peer2 (server + CLI)"
	@echo "  run-server       - Start indexing server"
	@echo "  docker-build     - Build Docker images"
	@echo "  docker-up        - Start indexing-server, peer1, peer2 with Docker Compose"
	@echo "  docker-ps        - Show Docker Compose service status"
	@echo "  docker-test      - Run containerized search+download test (peer2)"
	@echo "  docker-logs      - Tail Compose logs (server and peers)"
	@echo "  docker-down      - Stop Compose services"
	@echo "  docker-clean     - Stop and remove volumes and orphans"

setup:
	$(PYTHON) -c "import os; [os.makedirs(p, exist_ok=True) for p in ['data/peer1/shared','data/peer1/downloaded','data/peer1/replicated','data/peer2/shared','data/peer2/downloaded','data/peer2/replicated','logs/peer1','logs/peer2','logs/server','evaluation/results']]"

clean:
	$(PYTHON) -c "import shutil, os; [shutil.rmtree(p, ignore_errors=True) for p in ['data','logs','evaluation/results']]"

generate-peer1: setup
	$(PYTHON) -m peer.file_manager --peer peer1 --config config/config.json

generate-peer2: setup
	$(PYTHON) -m peer.file_manager --peer peer2 --config config/config.json

run-peer1: setup generate-peer1
	$(PYTHON) -m peer.peer --peer peer1 config/config.json

run-peer2: setup generate-peer2
	$(PYTHON) -m peer.peer --peer peer2 config/config.json

run-server: setup
	$(PYTHON) -m indexing_server.server

# Docker targets

docker-build:
	$(COMPOSE) build

docker-up: setup
	$(COMPOSE) up -d --build

docker-ps:
	$(COMPOSE) ps

docker-test:
	$(COMPOSE) exec peer2 python scripts/container_download_test.py

docker-logs:
	$(COMPOSE) logs --tail=100 indexing-server peer1 peer2

docker-down:
	$(COMPOSE) down

docker-clean:
	$(COMPOSE) down --volumes --remove-orphans