# ChainObserver Makefile

.PHONY: install test test-unit test-network lint format clean run

install:
	pip install -e ".[dev]"

test:
	python -m pytest tests/ -v --tb=short

test-unit:
	python -m pytest tests/ -m "not network" -v --tb=short

test-network:
	ETH_RPC_URL=https://ethereum.publicnode.com python -m pytest tests/ -m network -v --tb=short

lint:
	python -m ruff check chainobserver/ server.py --fix 2>/dev/null || python -m flake8 chainobserver/ server.py --max-line-length=100 2>/dev/null || echo "no linter found; skipping"

format:
	python -m black chainobserver/ tests/ server.py 2>/dev/null || echo "black not installed; skipping"

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null; true
	find . -name "*.pyc" -delete 2>/dev/null; true
	rm -rf .pytest_cache/ dist/ build/ *.egg-info/ 2>/dev/null; true

run:
	python server.py
