build:
	docker compose build
up:
	docker compose up
shell:
	docker compose run --rm demo bash
test:
	docker compose run --rm demo python -m pytest -q
