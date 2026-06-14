# ============================================================
# Kavalx Advanced Fraud Detection & Banking Security
# Makefile
# ============================================================

.PHONY: up down build logs test migrate clean help

COMPOSE := docker compose
COMPOSE_FILE := docker-compose.yml

# Default target
.DEFAULT_GOAL := help

## ── Docker Compose ────────────────────────────────────────

up: ## Start all services in detached mode
	$(COMPOSE) -f $(COMPOSE_FILE) up -d --build
	@echo "✓ Kavalx stack is running. Use 'make logs' to view output."

down: ## Stop and remove all containers
	$(COMPOSE) -f $(COMPOSE_FILE) down
	@echo "✓ All services stopped."

build: ## Rebuild all service images without cache
	$(COMPOSE) -f $(COMPOSE_FILE) build --no-cache
	@echo "✓ All images rebuilt."

logs: ## Tail logs for all services
	$(COMPOSE) -f $(COMPOSE_FILE) logs -f --tail=100

## ── Testing ───────────────────────────────────────────────

test: ## Run the full test suite
	@echo "Running shared library tests..."
	python -m pytest services/shared/ -v --tb=short
	@echo "Running service integration tests..."
	python -m pytest tests/ -v --tb=short
	@echo "✓ All tests passed."

## ── Database ──────────────────────────────────────────────

migrate: ## Re-run database initialization scripts
	@echo "Applying PostgreSQL schema..."
	$(COMPOSE) exec -T postgres psql -U kavalx -d kavalx -f /docker-entrypoint-initdb.d/init.sql
	@echo "Applying Memgraph schema..."
	$(COMPOSE) exec -T memgraph mgconsole < schema/memgraph/init.cypher
	@echo "Initializing Milvus collections..."
	python schema/milvus/init.py
	@echo "✓ All schemas applied."

kafka-topics: ## Create Kafka topics
	$(COMPOSE) exec kafka bash /scripts/create-topics.sh || \
		docker cp infra/kafka/create-topics.sh kavalx-kafka:/scripts/create-topics.sh && \
		$(COMPOSE) exec kafka bash /scripts/create-topics.sh
	@echo "✓ Kafka topics created."

## ── Cleanup ───────────────────────────────────────────────

clean: ## Stop containers, remove volumes, prune images
	$(COMPOSE) -f $(COMPOSE_FILE) down -v --remove-orphans
	docker image prune -f --filter "label=com.kavalx=true"
	@echo "✓ Cleaned up containers, volumes, and dangling images."

## ── Help ──────────────────────────────────────────────────

help: ## Show this help message
	@echo ""
	@echo "Kavalx Makefile Targets:"
	@echo "────────────────────────────────────────────────────"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'
	@echo ""
