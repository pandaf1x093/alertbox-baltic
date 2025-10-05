.PHONY: dev run fmt lint test api scheduler

dev:
\tpython -m venv .venv && . .venv/bin/activate && pip install -U pip && pip install -e .[dev]

run:
\t. .venv/bin/activate; python -m app.scheduler & uvicorn app.main:app --host 0.0.0.0 --port 8000

api:
\t. .venv/bin/activate; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

scheduler:
\t. .venv/bin/activate; python -m app.scheduler

fmt:
\t. .venv/bin/activate; black app tests; isort app tests; ruff check app tests --fix

lint:
\t. .venv/bin/activate; ruff check app tests

test:
\t. .venv/bin/activate; pytest -q
