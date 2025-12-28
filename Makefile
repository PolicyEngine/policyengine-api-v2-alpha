.PHONY: install dev format lint test integration-test clean seed up down logs start-supabase stop-supabase reset rebuild create-state-bucket deploy-local init db-reset-prod modal-deploy modal-serve docs

# AWS Configuration
AWS_REGION ?= us-east-1
STATE_BUCKET = policyengine-api-v2-terraform-state

install:
	uv pip install -e .

dev:
	docker compose up

format:
	ruff format .

lint:
	ruff check --fix .

test:
	pytest tests/test_models.py -v

integration-test:
	@echo "Starting integration tests..."
	@echo "1. Starting Supabase..."
	@supabase start || true
	@echo "2. Initialising database..."
	@echo "yes" | uv run python scripts/init.py
	@echo "3. Running seed script..."
	@uv run python scripts/seed.py
	@echo "4. Running integration tests..."
	@pytest tests/test_integration.py -v --tb=short
	@echo "✓ Integration tests complete!"

init:
	@echo "Initialising Supabase (tables, buckets, permissions)..."
	uv run python scripts/init.py

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

create-state-bucket:
	@echo "Creating Terraform state bucket..."
	@aws s3api head-bucket --bucket $(STATE_BUCKET) --region $(AWS_REGION) 2>/dev/null || \
		(aws s3api create-bucket \
			--bucket $(STATE_BUCKET) \
			--region $(AWS_REGION) \
			--create-bucket-configuration LocationConstraint=$(AWS_REGION) && \
		aws s3api put-bucket-versioning \
			--bucket $(STATE_BUCKET) \
			--versioning-configuration Status=Enabled \
			--region $(AWS_REGION) && \
		echo "✓ Terraform state bucket created with versioning enabled")

deploy-local:
	@echo "Deploying infrastructure locally..."
	cd terraform && ./deploy.sh plan
	@read -p "Apply changes? [y/N] " -n 1 -r; \
	echo; \
	if [[ $$REPLY =~ ^[Yy]$$ ]]; then \
		cd terraform && ./deploy.sh apply -auto-approve; \
	fi

db-reset-prod:
	@echo "⚠️  WARNING: This will reset the PRODUCTION database ⚠️"
	@echo "This will:"
	@echo "  1. Drop all tables and storage in production"
	@echo "  2. Recreate tables, buckets, and permissions"
	@echo "  3. Seed all data (UK and US models, parameters, datasets)"
	@echo ""
	@read -p "Are you sure you want to continue? Type 'yes' to confirm: " -r CONFIRM; \
	echo; \
	if [ "$$CONFIRM" = "yes" ]; then \
		echo "Resetting production database..."; \
		set -a && . .env.prod && set +a && \
		echo "yes" | uv run python scripts/init.py && \
		uv run python scripts/seed.py; \
	else \
		echo "Aborted."; \
		exit 1; \
	fi

modal-deploy:
	@echo "Deploying Modal functions..."
	@set -a && . .env.prod && set +a && \
	uv run modal secret create policyengine-db \
		"DATABASE_URL=$$SUPABASE_POOLER_URL" \
		"SUPABASE_URL=$$SUPABASE_URL" \
		"SUPABASE_KEY=$$SUPABASE_KEY" \
		"STORAGE_BUCKET=$$STORAGE_BUCKET" \
		--force
	uv run modal deploy src/policyengine_api/modal_app.py

modal-serve:
	@echo "Running Modal functions locally..."
	uv run modal serve src/policyengine_api/modal_app.py

docs:
	@echo "Building docs site..."
	cd docs && bun install && bun run build
	@echo "✓ Docs built to docs/out/"
