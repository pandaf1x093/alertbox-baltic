# AlertBox Baltic (FastAPI + APScheduler + SQLAlchemy + LLM fallback)

Минимальное приложение для аналитических отчётов по новостям региона (Baltics).

## Установка

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .
cp .env.example .env && nano .env
```

## Запуск

```bash
make run
# или отдельно:
make api
make scheduler
```

## Эндпойнты
- `GET /health`
- `POST /report`
- `GET /reports`
- `POST /sources/bootstrap`
