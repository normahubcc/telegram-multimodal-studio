.PHONY: help install run test lint format check clean docker-build docker-up docker-down

help:
	@echo "Available commands:"
	@echo "  make install      Install dependencies"
	@echo "  make run          Run the bot"
	@echo "  make test         Run pytest tests"
	@echo "  make lint         Run ruff linter check"
	@echo "  make format       Run ruff formatter"
	@echo "  make check        Run lint + tests"
	@echo "  make docker-up    Start bot in docker-compose"
	@echo "  make docker-down  Stop bot container"

install:
	pip install -e ".[dev]"

run:
	python -m bot.main

test:
	pytest -v

lint:
	ruff check .

format:
	ruff format .
	ruff check --fix .

check: lint test

clean:
	rm -rf build/ dist/ *.egg-info .pytest_cache .ruff_cache __pycache__

docker-build:
	docker compose build

docker-up:
	docker compose up -d

docker-down:
	docker compose down
