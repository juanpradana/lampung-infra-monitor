.PHONY: setup run init-db docker-build docker-run clean test

# Setup virtual environment and install dependencies
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
	@echo "✅ Setup complete. Run 'make run' to start."

# Initialize database and create default admin
init-db:
	python3 -m backend.init_db

# Run development server
run:
	python3 -m backend.main

# Run with uvicorn directly
serve:
	uvicorn backend.main:app --host 0.0.0.0 --port 8032 --reload

# Docker commands
docker-build:
	docker compose build

docker-run:
	docker compose up -d

docker-stop:
	docker compose down

docker-logs:
	docker compose logs -f

# Run tests
test:
	python3 -m pytest tests/ -v

# Backup database
backup:
	cp data/lampung_monitor.db data/backup_$$(date +%Y%m%d_%H%M%S).db

# Clean
clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

# Help
help:
	@echo "Available commands:"
	@echo "  make setup       - Setup virtual environment"
	@echo "  make init-db     - Initialize database"
	@echo "  make run         - Run development server"
	@echo "  make serve       - Run with uvicorn (hot reload)"
	@echo "  make docker-build - Build Docker image"
	@echo "  make docker-run  - Run with Docker"
	@echo "  make test        - Run tests"
	@echo "  make backup      - Backup database"
	@echo "  make clean       - Clean cache files"
