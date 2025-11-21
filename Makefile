.PHONY: install dev format lint test clean seed up down logs start-supabase stop-supabase reset rebuild create-state-bucket deploy-local

# AWS Configuration
AWS_REGION ?= us-east-1
STATE_BUCKET = policyengine-api-v2-terraform-state

install:
	uv pip install -e .

dev:
	uv pip install -e ".[dev]"

format:
	ruff format .

lint:
	ruff check --fix .

test:
	docker compose --profile test up --build --exit-code-from test test

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
