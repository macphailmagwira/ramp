POETRY       = poetry
ALEMBIC      = $(POETRY) run alembic
PYTEST       = $(POETRY) run pytest

.PHONY: install
install:
	$(POETRY) install


.PHONY: lock
lock:
	$(POETRY) lock --no-update

.PHONY: run
run:
	$(POETRY) run uvicorn src.main:app --reload

.PHONY: migrate
migrate:
	$(ALEMBIC) upgrade head


.PHONY: downgrade
downgrade:
	$(ALEMBIC) downgrade -1


.PHONY: revision
revision:
	$(ALEMBIC) revision --autogenerate -m "$(m)"


.PHONY: revision-empty
revision-empty:
	$(ALEMBIC) revision -m "$(m)"


.PHONY: history
history:
	$(ALEMBIC) history

.PHONY: heads
heads:
	$(ALEMBIC) heads

.PHONY: test-cov
test-cov:
	$(PYTEST) --cov=src --cov-report=html


.PHONY: lint
lint:
	poetry run ruff check .
	poetry run mypy .

.PHONY: format
format:
	poetry run ruff format .
	poetry run ruff check . --fix