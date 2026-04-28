.PHONY: help dev build test lint typecheck frontend backend pytests test-affordability test-compliance test-scraper test-services

help:
	@echo "Available targets:"
	@echo "  make dev            # Start frontend + backend via start.sh"
	@echo "  make build          # Build monorepo workspaces"
	@echo "  make test           # Run Python package tests used by CI"
	@echo "  make lint           # Run frontend lint"
	@echo "  make typecheck      # Run frontend TypeScript checks"
	@echo "  make frontend       # Run Next.js dev server only"
	@echo "  make backend        # Run FastAPI dev server only"


dev:
	bash start.sh

build:
	npm run build


test: pytests

pytests: test-affordability test-compliance test-scraper test-services

test-affordability:
	cd packages/affordability && PYTHONPATH=.:../ python3 -m pytest test_engine.py -v

test-compliance:
	cd packages/compliance && PYTHONPATH=.:../ python3 -m pytest test_scorer.py -v

test-scraper:
	cd packages/scraper && PYTHONPATH=.:../ python3 -m pytest test_vertical_stack.py -v

test-services:
	PYTHONPATH=. python3 -m pytest services/test_vmc_validator.py -v

lint:
	cd apps/web && npm run lint

typecheck:
	cd apps/web && npm run type-check

frontend:
	cd apps/web && npm run dev

backend:
	cd backend && uvicorn main:app --host 0.0.0.0 --port 8000 --reload
