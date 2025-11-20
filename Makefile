.PHONY: install dev format lint test clean seed up down logs start-supabase stop-supabase reset rebuild

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

format:
	ruff format .

lint:
	ruff check --fix .

test:
	pytest

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true

reset:
	@echo "Resetting Supabase database..."
	supabase db reset

rebuild:
	@echo "Rebuilding Docker containers..."
	docker compose down
	docker compose build --no-cache
	docker compose up -d
	@echo "✓ Rebuild complete!"

seed:
	@echo "Seeding database with UK and US models..."
	uv run python scripts/seed.py

start-supabase:
	@echo "Starting Supabase..."
	supabase start

stop-supabase:
	@echo "Stopping Supabase..."
	supabase stop

up:
	docker compose up -d

down:
	docker compose down

logs:
	docker compose logs -f
