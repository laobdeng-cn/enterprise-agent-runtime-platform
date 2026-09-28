.PHONY: up down ps logs build test lint typecheck clean

up:
	docker compose up --build -d

down:
	docker compose down

ps:
	docker compose ps

logs:
	docker compose logs -f

build:
	docker compose build

test:
	docker compose run --rm backend pytest

lint:
	docker compose run --rm backend ruff check app tests

typecheck:
	docker compose run --rm backend mypy app
	docker compose run --rm frontend npm run typecheck

clean:
	docker compose down -v --remove-orphans
