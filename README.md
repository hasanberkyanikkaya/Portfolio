# Portfolio Analysis Platform — Backend

FastAPI + PostgreSQL backend for a local portfolio tracker and AI-assisted market analysis platform.
Current state: **Phase 1** — portfolio CRUD, real-time prices from Finnhub, and P&L tracking.

## Requirements

- Python 3.12+
- Docker Desktop (for PostgreSQL)

## Run Locally

### 1. Start PostgreSQL

```bash
docker-compose up -d
```

This starts Postgres 16 on `localhost:5434` (user/password/db: `portfolio`).
Port 5434 is used because this machine already runs a local PostgreSQL on 5432 and 5433.
Data is kept in a Docker volume (`pgdata`), so it survives restarts.

### 2. Set up Python

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux

pip install -r requirements.txt
```

### 3. Configure .env

Copy the example file and fill in keys later (only `DATABASE_URL` is used for now):

```bash
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Start the API

```bash
uvicorn app.main:app --reload
```

API: http://localhost:8000 — interactive docs: http://localhost:8000/docs

### 6. Check health

```bash
curl http://localhost:8000/health
```

Expected: `{"status":"ok","database":"ok"}` (returns 503 with `"database":"error"` if Postgres is down).

## Portfolio Endpoints (Phase 1)

> Adding a position checks the ticker against Finnhub (must be NASDAQ-listed),
> so `FINNHUB_API_KEY` must be set in `.env`. Get a free key at https://finnhub.io.
> Money values are returned as **strings** (e.g. `"150.2500"`) to keep exact precision.

### Add a position

```bash
curl -X POST http://localhost:8000/positions \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "quantity": 10, "purchase_price": 150.25}'
```

`purchase_date` is optional (defaults to today, New York time):

```bash
curl -X POST http://localhost:8000/positions \
  -H "Content-Type: application/json" \
  -d '{"ticker": "NVDA", "quantity": 2.5, "purchase_price": 900, "purchase_date": "2026-06-15"}'
```

Errors: `400` ticker is not NASDAQ-listed - `429` Finnhub rate limit - `503` Finnhub unreachable or no API key.

### List open positions (with live prices + unrealized P&L)

```bash
curl http://localhost:8000/positions
```

Each position includes `current_price`, `market_value`, `unrealized_pnl` ($),
`unrealized_pnl_pct` (%) and `price_status`. If Finnhub is down or rate-limited,
the endpoint still works: that position gets `"price_status": "unavailable"` and
`null` price/P&L fields.

### Close a position (records realized P&L)

```bash
curl -X POST http://localhost:8000/positions/1/close \
  -H "Content-Type: application/json" \
  -d '{"sale_price": 180.50}'
```

This deletes the open position and creates a `RealizedTrade` record.
`sale_date` is optional (defaults to today, New York time).

### List realized trades

```bash
curl http://localhost:8000/positions/realized
```

Returns all closed trades plus `total_realized_pnl`.

### Delete a mis-entered position (no trade recorded)

```bash
curl -X DELETE http://localhost:8000/positions/1
```

## Tests

```bash
pytest
```

Tests do not need a running database.

## Project Structure

```
app/
  main.py          # FastAPI app
  core/            # config (.env) + database session
  models/          # SQLAlchemy models
  routers/         # API endpoints
  schemas/         # Pydantic request/response models
  services/        # external integrations (finnhub_client.py) + business logic (pnl.py)
alembic/           # DB migrations
tests/             # pytest tests
```
