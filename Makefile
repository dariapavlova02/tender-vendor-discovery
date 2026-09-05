.PHONY: demo test check dashboard

demo:
	poetry run tender-vendor-discovery demo

test:
	poetry run pytest -q

check: test
	poetry run python scripts/check_repository.py
	poetry check
	poetry build
	poetry run python scripts/check_distribution.py

dashboard:
	./scripts/run_dashboard.sh
