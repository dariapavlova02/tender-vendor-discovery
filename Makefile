.PHONY: demo test check dashboard

demo:
	poetry run tender-vendor-discovery demo

test:
	poetry run pytest -q

check: test
	poetry run python scripts/check_repository.py
	poetry check
	poetry build

dashboard:
	./scripts/run_dashboard.sh
