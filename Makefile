.PHONY: check
check:
	python -m ruff check .
	python -m ruff format --check .
	python -m coverage run -m pytest
	python -m coverage report
	python -m coverage json -o coverage.json
	python scripts/check_coverage.py coverage.json
