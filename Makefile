.PHONY: setup setup-backend setup-frontend dev dev-backend dev-frontend test test-backend clean help

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

setup: setup-backend setup-frontend ## Full setup (backend + frontend)

setup-backend: ## Set up Python virtual environment and install dependencies
	cd backend && python3 -m venv venv
	cd backend && ./venv/bin/pip install --upgrade pip
	cd backend && ./venv/bin/pip install -r requirements.txt
	@if [ ! -f backend/.env ]; then cp backend/.env.example backend/.env; echo "Created backend/.env — edit with your settings"; fi
	cd backend && ./venv/bin/python -c "from app.database import init_db; init_db()"
	@echo "\n✅ Backend setup complete"

setup-frontend: ## Install frontend dependencies
	cd frontend && npm install
	@echo "\n✅ Frontend setup complete"

dev: ## Start both backend and frontend
	@echo "Starting Groww Trading Lab..."
	@echo "Backend:  http://localhost:8000"
	@echo "Frontend: http://localhost:3000"
	@echo ""
	$(MAKE) dev-backend &
	$(MAKE) dev-frontend &
	wait

dev-backend: ## Start FastAPI backend
	cd backend && ./venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

dev-frontend: ## Start Next.js frontend
	cd frontend && npm run dev

test: test-backend ## Run all tests

test-backend: ## Run backend tests
	cd backend && ./venv/bin/python -m pytest tests/ -v

clean: ## Remove generated files
	rm -rf backend/venv backend/__pycache__ backend/*.db
	rm -rf frontend/node_modules frontend/.next
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Cleaned"
