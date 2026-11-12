# Project: AI-Powered Investment/Portfolio Analysis Platform

## What This Project Is
A locally-run portfolio tracker + AI-assisted market analysis platform for NASDAQ stocks.
The user manually adds positions (ticker + quantity + purchase price), the system calculates
real-time P&L, and it auto-generates market reports twice a day using the Claude API.

**Current status: Phase 8 (Predictions + Risk Profile + Themes) is done.** Backend: FastAPI
structure, PostgreSQL via Docker, Alembic, `/health`, portfolio CRUD with real-time Finnhub prices
and P&L tracking, APScheduler pre-market/close report jobs with Claude-generated commentary cached
in `daily_reports`, the Market Pulse report (sector-ETF performance, RSP/SPY breadth signal,
SPY/QQQ 50/200-day MA positioning) cached daily at 16:50 ET, the Sentiment report (our own 0-100
fear & greed composite from Yahoo data) cached daily at 16:55 ET, a static Turkish glossary, and
the Phase 6 pure-data endpoints: `/portfolio/technical` (per-holding 52w high/low distance,
MA50/MA200 position, earnings-week flag, rule-based strong/weak label) and
`/portfolio/{ticker}/news` (Finnhub company news). Phase 7 adds two more cached daily reports:
Setups (rule-based opportunity scan over the portfolio's Yahoo closes — entry zone, stop-loss and
rationale all code-computed, Claude only narrates; 17:00 ET) and Protect (position/sector
concentration weights, rule-based 0-100 risk score, static 2026 macro calendar mapped to
sensitive holdings; 17:05 ET). Phase 8 adds the prediction engine (three rule-based direction
algorithms logged per portfolio ticker to a `predictions` table, auto-evaluated after 5 trading
days, per-algorithm accuracy stats; NO Claude anywhere in Phase 8), a risk-profile questionnaire
compared against the Protect risk level, and curated static theme lists with live Finnhub quotes.
Frontend: React dashboard under `frontend/`
(portfolio table with Trend/MA200/52W columns + ER earnings pill, row click opens a per-stock
news dialog, add/close/delete positions, realized-P&L tab, Market Pulse tab with sector heatmap,
Sentiment tab with score gauge + component breakdown + collapsible glossary, Setups tab with
per-setup cards, Protect tab with risk meter + concentration bars + macro-event list + the
risk-profile questionnaire card, Predictions tab with accuracy stat cards + track-record table +
manual run button, Discover tab with theme chips + live stock tables, 15-min auto-refresh) —
a Reports tab for premarket/close comes in a later phase.

Full phase plan and scope of each phase: `project-plan-and-prompts.md` (project root).

## Tech Stack
- **Backend:** Python 3.12+, FastAPI, SQLAlchemy 2 (async, asyncpg), Alembic (migrations)
- **DB:** PostgreSQL 16 (local via docker-compose, volume `pgdata`)
- **Config:** pydantic-settings, reads `.env`
- **External APIs:** Finnhub (real-time quotes + NASDAQ symbol validation), Claude
  (`anthropic` SDK, model `claude-sonnet-4-6` via `ANTHROPIC_MODEL`), keys in `.env`.
  Claude has two providers via `CLAUDE_PROVIDER`: `anthropic` (direct API, `AsyncAnthropic`,
  needs `ANTHROPIC_API_KEY`) or `bedrock` (Amazon Bedrock, `AsyncAnthropicBedrock`, AWS credential
  chain + `AWS_REGION`; model id is resolved to the cross-region inference profile form
  `us.anthropic.<model>` — the bare `anthropic.<model>` id 400s with "on-demand throughput isn't
  supported" for current-generation models). New AWS accounts get a very low default Bedrock
  daily-token quota (surfaces as `ClaudeRateLimitError`/429) — request an increase in
  Service Quotas if this persists. Yahoo Finance chart API (`app/services/yahoo_client.py`, free
  keyless JSON daily candles, typed `YahooError`/`YahooRateLimitError`/`YahooUnavailableError`)
  provides historical closes for Market Pulse and all three Sentiment components (incl. `^VIX` —
  Finnhub free tier has no VIX/candles/highs-lows at all) — Finnhub's `/stock/candle` is premium
  (403 on free tier) and Stooq now blocks non-browser clients with a JS challenge. Yahoo is
  unofficial: it needs a browser-like User-Agent (default UA gets 429) and fetches are sequential
  on purpose.
- **Scheduler:** APScheduler 3.x `AsyncIOScheduler` (NY timezone; cron mon-fri 09:20 premarket +
  16:45 close + 16:50 market_pulse + 16:55 sentiment + 17:00 setups + 17:05 protect +
  17:10 predictions ET), started via the FastAPI lifespan, disable with `SCHEDULER_ENABLED=false`
- **Frontend:** React 19 + TypeScript (Vite), Tailwind CSS **v4** (`@tailwindcss/vite` plugin,
  CSS-first `@theme` tokens — no tailwind.config), TanStack Query, `@fontsource-variable` fonts (offline)

## Commands
```bash
docker-compose up -d              # start PostgreSQL
alembic upgrade head              # apply migrations
uvicorn app.main:app --reload     # run API (http://localhost:8000)
pytest                            # run tests (no DB needed)
alembic revision --autogenerate -m "msg"   # create a new migration

cd frontend && npm run dev        # run frontend (http://localhost:5173, proxies API to :8000)
cd frontend && npm run build      # typecheck (tsc -b) + production build
cd frontend && npm run lint       # oxlint
```

## Architecture (key directories)
- `app/main.py` — FastAPI app; routers are included here
- `app/core/config.py` — `Settings` (env vars: `DATABASE_URL`, `FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`)
- `app/core/database.py` — async engine, session factory, `get_db` dependency
- `app/core/timeutils.py` — `NY_TZ` + `today_ny()`; use these for any "today"/date-default logic
- `app/core/scheduler.py` — `create_scheduler()`: the two report cron jobs (job bodies live in `services/reports.py`)
- `app/models/` — SQLAlchemy models (`Position`, `RealizedTrade`, `DailyReport`, `Prediction`,
  `RiskProfile`); `base.py` has `Base`.
  New models must be imported in `app/models/__init__.py` so Alembic autogenerate can see them
- `app/routers/` — FastAPI endpoints (one router file per module; `positions.py` = portfolio CRUD,
  `portfolio.py` = technical tracking + per-ticker news + setups + protect, `reports.py` = daily
  reports, `market_pulse.py` = Market Pulse, `sentiment.py` = Sentiment, `glossary.py` = static
  glossary, `predictions.py` = prediction track record, `risk_profile.py` = questionnaire,
  `themes.py` = theme scan)
- `app/schemas/` — Pydantic request/response models
- `app/services/` — external integrations (`finnhub_client.py`, `claude_client.py`, `yahoo_client.py`)
  and business logic (`pnl.py` — all P&L math; `reports.py` — report payloads + generation, shared by
  scheduler and refresh endpoint; `market_pulse.py` — sector/breadth/MA Decimal math + payload,
  reuses `reports.py`'s `_generate`/`_get_existing` caching pipeline via `extra_content`;
  `sentiment.py` — fear & greed score math + payload, same pipeline reuse; `technical.py` —
  per-stock 52w/MA math from Yahoo closes + earnings-week flag + strong/weak label rule + news
  mapping, pure data (no Claude, no DB) with an in-process per-(ticker, NY-date) closes memo
  cache — tests must call `clear_technical_cache()`; `glossary.py` — static Turkish term
  definitions as Pydantic constants, never Claude-generated; `setups.py` — rule-based opportunity
  scan (RSI/MA rules + entry/stop math, full rule spec in its module docstring), reuses the
  technical closes cache via `fetch_daily_closes_cached`; `protect.py` — concentration weights +
  0-100 risk score + macro sensitivity mapping (methodology in its docstring), per-ticker sector
  memo — tests must call `clear_protect_cache()`; `macro_calendar.py` — static editorial 2026
  FOMC/CPI/NFP dates + sector-sensitivity keywords, git-maintained like the glossary;
  `predictions.py` — the three prediction algorithms + evaluation + cycle + job (full rule spec
  in its module docstring, no Claude), reuses the technical closes cache; `risk_profile.py` —
  questionnaire scoring + profile-vs-Protect mismatch rule (spec in its docstring);
  `themes.py` — curated static theme→ticker lists (glossary-style editorial, every symbol
  NASDAQ-verified), detail endpoint reuses Protect's sector memo; `disclaimers.py` —
  `STATISTICAL_DISCLAIMER` shared by all Phase 8 responses)
- `app/prompts/` — editable Claude prompt templates (`system.txt`, `premarket.txt`, `close.txt`,
  `market_pulse.txt`, `sentiment.txt`, `setups.txt`, `protect.txt`; `string.Template` with
  `$report_date` / `$payload_json` placeholders)
- `alembic/versions/` — migrations (baseline `a1f0c9d4b7e2`; `c4d8e2f7a913` positions + realized_trades;
  `e7b3a5c2d941` daily_reports; `b9d2f6a1c358` predictions + risk_profiles)
- `tests/` — pytest tests (async via pytest-asyncio, `asyncio_mode = auto` in `pytest.ini`).
  `conftest.py` provides an in-memory SQLite DB (aiosqlite) + `FakeFinnhub` — no Postgres/network needed
- `frontend/src/types/api.ts` — TS mirrors of the Pydantic schemas (all Decimals typed as `string`)
- `frontend/src/api/` — `client.ts` (fetch wrapper, `ApiError`, handles string vs 422-array `detail`)
  + `positions.ts` (one function per endpoint)
- `frontend/src/hooks/` — TanStack Query hooks (`usePositions`, `useRealized`, `useHealth`,
  `useMutations`, `useTechnical`, `useTickerNews`, `useSetups`, `useProtect`, `usePredictions`,
  `useRiskProfile`, `useThemes`)
- `frontend/src/components/` — UI (`GlassCard`, `SummaryCard`, `PositionsTable`, `AddPositionForm`,
  `ClosePositionDialog`, `NewsDialog`, `RealizedTable`, `ErrorBanner`, …)
- `frontend/src/utils/format.ts` — display formatting for string Decimals (money, %, quantity, P&L color)
- `frontend/vite.config.ts` — Tailwind v4 plugin + dev proxy (`/positions`, `/portfolio`,
  `/health`, `/market-pulse`, `/sentiment`, `/glossary`, `/predictions`, `/risk-profile`,
  `/themes` → :8000)

## Conventions
- Every new DB table requires an Alembic migration — never hand-edit the DB schema.
- Finnhub and Claude API calls always go through the `services/` layer; routers never call external APIs directly.
- Every prompt sent to Claude must include: *"Base your answer only on the data provided, do not invent numbers, do not make definitive directional/investment claims, use conditional language."*
- Daily reports (`DailyReport`, `MarketPulse`, etc.) are always cached in the DB; the same day's report is never re-requested from Claude — check the cache first.
- New endpoints must have a Pydantic response schema in `app/schemas/` — never return raw dicts.
- Routers get a DB session via `Depends(get_db)` from `app.core.database`.
- All date/time logic uses `America/New_York` as the reference timezone (handles DST automatically),
  then converts as needed. Use `app/core/timeutils.py`, don't re-create the ZoneInfo.
- The Finnhub client is a FastAPI dependency (`Depends(get_finnhub_client)`), so tests can override it.
  It raises typed errors (`FinnhubRateLimitError`, `FinnhubUnavailableError`, `FinnhubAuthError`);
  routers map them to HTTP 429 / 503.
- The Claude client follows the same pattern: `Depends(get_claude_client)`, typed errors
  (`ClaudeRateLimitError` → 429; `ClaudeAuthError`/`ClaudeUnavailableError`/`ClaudeError` → 503).
- Reports upsert on `(report_type, report_date)` (unique constraint): the scheduler skips generation
  when today's report already exists (`force=False`); `POST /reports/refresh` regenerates in place (`force=True`).
  `report_type` values: `premarket | close | market_pulse | sentiment | setups | protect` (plain
  String(16), no DB enum — a new type needs no migration; the prompt filename must equal the
  report_type string). Market Pulse, Sentiment, Setups and Protect store their numeric sections
  under a `data` key in the content JSON next to the Claude `text`, so their GET endpoints serve
  everything from cache with zero live API calls.
- The RSP-vs-SPY breadth signal (`broad_participation | megacap_concentration | neutral`) is rule-based
  in `services/market_pulse.py` (gap thresholds ±0.25 daily / ±0.75 weekly pct-points); Claude only
  explains the label, never recomputes it. MA/weekly math uses Decimal + `pnl.money` rounding.
- Sentiment score (0 = extreme fear, 100 = extreme greed): equal-weight mean of three 0-100
  components — VIX vs its 1y mean, SPY vs its 125-day MA, and new 52-week closing highs vs lows
  across a fixed 30-stock NASDAQ basket. Each component degrades independently (missing → reweight
  over the rest; all missing → 503); the label is rule-based (`classify_sentiment`) and Claude only
  explains it. Full methodology + tunables in `app/services/sentiment.py`'s module docstring.
- The glossary (`GET /glossary`) is static editorial content in `app/services/glossary.py` —
  edited in git, no DB, never regenerated by Claude.
- Per-stock technical label (`strong | weak | neutral`) is rule-based in `services/technical.py`
  (`classify_technical`, no Claude): strong = close above MA200 AND within `NEAR_HIGH_PCT` (10%)
  below the 52w closing high; weak = below MA200 AND within `NEAR_LOW_PCT` (10%) above the 52w
  closing low; else neutral; any missing input → null. "52w high/low" = closing extreme of the
  trailing 252 sessions (Yahoo closes only, same approximation as Sentiment breadth). Each block
  degrades independently (52w ≥252 closes, MA200 ≥200, MA50 ≥50); a failed Yahoo fetch marks the
  stock `data_status: "unavailable"`; the earnings-week flag (Finnhub calendar, today→+7d NY)
  degrades to null on any Finnhub error. Yahoo fetches are sequential + memoized in-process per
  (ticker, NY date).
- Setups rules (full spec in `services/setups.py`'s docstring; entry/stop levels code-computed,
  Claude only narrates): S1 RSI(14, Wilder) oversold at MA50 support in an uptrend, S2 fresh MA200
  reclaim, S3 52w-low RSI divergence. Max one setup per ticker (S1>S2>S3), geometry guard (stop
  must sit below the entry zone). An EMPTY setups list is a valid result and Claude is still
  called — the "no setups today is normal" narration is part of the product.
- Protect scoring (methodology in `services/protect.py`'s docstring): weights from live quotes
  (per-ticker cost-basis fallback), sectors from `/stock/profile2` `finnhubIndustry` (failure →
  "Unknown" + warning), flags at >20% position / >40% sector / <5 positions, points-table score
  0-100 → low/medium/high. Macro events: static editorial 2026 FOMC/CPI/NFP dates in
  `services/macro_calendar.py` merged with Finnhub's calendar when it works (free-tier 403 → just
  a warning). Empty portfolio → valid score-0 report.
- Prediction tracking (full spec in `services/predictions.py`'s docstring; NO Claude — Phase 8
  endpoints are all pure data): three independent algorithms (`trend_ma`, `rsi_reversion`,
  `swing_breakout`) run daily (17:10 ET) over portfolio tickers; directions are `up|down` only
  (no unfalsifiable "neutral"); one row per (ticker, algorithm, prediction_date) where
  `prediction_date` = the last Yahoo candle's date (unique constraint + select-before-insert
  make reruns no-ops). Evaluation is candle-based (the 5th candle after prediction_date —
  holiday-robust); exact price equality = incorrect; `actual_return_pct` is stored on every
  evaluated row. Pending rows >30 days old that can't be evaluated become `expired` and leave
  the accuracy denominator; pending rows for tickers no longer in the portfolio are still
  fetched and evaluated until they resolve or expire.
- Risk profile (spec in `services/risk_profile.py`): 3 Literal-validated questions scored 1-3
  each → 3-9 → conservative (≤4) / balanced (≤7) / aggressive (8+); single DB row, upserted.
  Mismatch flags only when the latest Protect `risk_level` exceeds the profile's tolerance;
  no Protect report → `mismatch: null`, never an error.
- Themes (`services/themes.py`): curated static theme→ticker lists, glossary-style editorial —
  every symbol must pass `is_nasdaq_ticker` before being committed. The detail endpoint enriches
  with live Finnhub quotes + `finnhubIndustry` (shares Protect's sector memo) and returns 200
  with `warnings` even on total Finnhub blackout.
- **Disclaimer convention (Phase 8):** every prediction/score/theme response carries a
  `disclaimer` field populated from `services/disclaimers.py`'s `STATISTICAL_DISCLAIMER`
  ("istatistiksel... garanti etmez" + the standard yatırım tavsiyesi line); the frontend renders
  it via the shared `DisclaimerNote` component.
- Finnhub free tier: the calendar endpoints return 403 and real index symbols don't exist — reports use
  ETF proxies (SPY/QQQ/DIA) and record failed sections in the content's `warnings` list; a data gap
  never fails report generation.
- Report text is written in Turkish and must end with the disclaimer line
  "Bu bir yatırım tavsiyesi değildir; yalnızca eğitim amaçlıdır." (enforced via `app/prompts/system.txt`).
- P&L math lives in `app/services/pnl.py` and always uses `Decimal` (never float):
  unrealized = (current − purchase) × qty; pct = (current − purchase) / purchase × 100;
  realized = (sale − purchase) × qty. Dollar amounts and percentages round to 2 decimals.
  Pydantic serializes `Decimal` as JSON strings — that is intentional (exact precision).
- `GET /positions` degrades gracefully: if a quote can't be fetched, that position gets
  `price_status: "unavailable"` and null price/P&L fields — the endpoint never 500s because Finnhub is down.
- Closing a position (`POST /positions/{id}/close`) deletes the `Position` row and inserts a
  `RealizedTrade` in the same transaction. Plain `DELETE /positions/{id}` removes a mis-entered
  position without recording a trade.
- **Frontend:** API Decimal fields stay `string` in TS — never do money math in JS; format for
  display via `frontend/src/utils/format.ts` (null → "—").
- All frontend API calls go through `api/client.ts`; backend errors: `detail` is a string for
  400/404/429/503 but an array for 422 — `ApiError` normalizes both.
- Dev CORS is solved by the Vite proxy (`vite.config.ts`) — don't add CORS middleware to the
  backend just for dev. API base URL is `VITE_API_BASE` (empty in dev).
- Query keys: `["positions"]` (polls every 15 min = 900000 ms), `["realized"]` (staleTime
  Infinity), `["health"]` (60 s), `["market-pulse"]` and `["sentiment"]` (staleTime 55 min, hourly
  refetch — hit only the backend's DB cache; a 404 means "no report yet" and is not retried),
  `["glossary"]` (staleTime Infinity, fetched lazily when the section is opened), `["technical"]`
  (staleTime 55 min, no auto-refetch — the backend memo cache protects Yahoo), `["news", ticker]`
  (staleTime 15 min, fetched only while the news dialog is mounted), `["setups"]` and
  `["protect"]` (same 55-min/hourly/404-not-retried pattern as market-pulse), `["predictions"]`
  (55 min/hourly — DB-only backend) + `["predictions", ticker]` (404 not retried),
  `["risk-profile"]` (staleTime Infinity, 404 = not submitted yet, not retried), `["themes"]`
  (staleTime Infinity — static) + `["theme", slug]` (staleTime 15 min, fetched only while a theme
  is open — each hit costs live Finnhub calls). Mutations
  invalidate the affected keys; `refetchOnWindowFocus` is off globally (protects the Finnhub quota).

## Endpoints
- `GET /health` — app + DB status
- `POST /positions` — add position (validates ticker is NASDAQ-listed via Finnhub)
- `GET /positions` — open positions with live prices + unrealized P&L ($ and %) + totals
- `POST /positions/{id}/close` — close position (body: `sale_price`), creates `RealizedTrade`
- `DELETE /positions/{id}` — remove position without recording a trade
- `GET /positions/realized` — closed trades + `total_realized_pnl`
- `GET /reports/latest?type=premarket|close` — latest cached daily report (DB only, never calls Claude)
- `POST /reports/refresh` — regenerate today's report(s) on demand (body: `{"report_type": "premarket"|"close"|"both"}`)
- `GET /market-pulse` — latest cached Market Pulse report (DB only, never calls external APIs)
- `POST /market-pulse/refresh` — regenerate today's Market Pulse (no body); partial data gaps become
  `warnings`, total data blackout or Claude failure → 503, Claude rate limit → 429
- `GET /sentiment` — latest cached Sentiment report (DB only, never calls external APIs)
- `POST /sentiment/refresh` — regenerate today's Sentiment report (no body); same 429/503 semantics
  as Market Pulse (takes ~30-60 s: ~32 sequential Yahoo fetches + Claude)
- `GET /glossary` — static Turkish term definitions (no DB, no external APIs)
- `GET /portfolio/technical` — per-holding technical snapshot (52w high/low distance, MA50/MA200,
  earnings-week flag, strong/weak label); live Yahoo closes (memoized per NY day) + Finnhub
  earnings calendar, no Claude/DB cache; per-ticker failures degrade with `warnings`, ALL tickers
  failed → 429 (rate limit) / 503, empty portfolio → 200 `[]`
- `GET /portfolio/setups` + `POST /portfolio/setups/refresh` — cached Setups report (GET: DB only,
  404 if none; refresh: live Yahoo + Claude; all tickers failed → 429/503; empty portfolio and
  zero setups are valid 200 reports)
- `GET /portfolio/protect` + `POST /portfolio/protect/refresh` — cached Protect report (refresh:
  live Finnhub quotes/profiles + Claude; data failures degrade into `warnings`, Claude 429/503)
- `GET /portfolio/{ticker}/news` — Finnhub company news for a portfolio ticker (last 7 days,
  max 20, newest first); 404 if the ticker isn't in the portfolio, 429/503 per convention
- `GET /predictions` — all-ticker track record: per-algorithm stats + last 50 predictions
  (DB only; empty DB → 200 with empty lists, not 404)
- `GET /predictions/{ticker}` — one ticker's predictions + per-algorithm accuracy (DB only,
  404 when the ticker has no rows)
- `POST /predictions/run` — manual cycle (evaluate pending + log new); live Yahoo; all portfolio
  tickers failed → 429 (rate limit) / 503
- `POST /risk-profile` + `GET /risk-profile` — submit/read the questionnaire (single upserted
  row); GET 404 before first submit; response includes latest Protect `risk_level` + mismatch flag
- `GET /themes` — curated static theme list (no DB, no external APIs)
- `GET /themes/{slug}` — theme tickers + live Finnhub quotes/industries; failures degrade to
  `warnings` (always 200 for a known slug); unknown slug → 404

## Design System (frontend — keep future phases consistent with this)
Theme: dark Web3/fintech glassmorphism. Tokens live in `frontend/src/index.css` (`@theme`).
- **Palette:** void `#05070F` (page bg) · deep-navy `#0B1229` · nebula `#221A45` (purple glow) ·
  ocean `#0A2A43` (blue glow) · accent cyan `#22D3EE` · ink `#E6EAF2` (text; muted `#8B93A7`) ·
  profit `#34D399` · loss `#F87171`
- **Color rule:** green/red appear ONLY on P&L and market-performance values (sector %, heatmap
  tiles via `heatmapBgClass` opacity buckets) — cyan is the only decorative accent.
- **Background:** fixed layered gradient — two radial glows (nebula top-left, ocean bottom-right)
  over `linear-gradient(160deg, #0B1229, #05070F)`.
- **Glass card** (`GlassCard.tsx`): `rounded-2xl border-white/10 bg-white/[0.04] backdrop-blur-xl`
  + soft outer shadow and 1px inner top highlight.
- **Typography:** Space Grotesk (headings/tickers), Inter (body), JetBrains Mono + `tabular-nums`
  for ALL numeric data, right-aligned in tables.
- **Signature element — "Aurora Edge":** 1px top edge on every glass card,
  `bg-gradient-to-r from-transparent via-accent/60 to-transparent`; the SummaryCard adds a soft
  cyan blur glow behind it; the active tab underline reuses the same gradient.

## Boundaries
- Never hand-edit existing files in `alembic/versions/` — add a new migration instead.
- `.env` is never committed; API keys go there (`FINNHUB_API_KEY`, `ANTHROPIC_API_KEY`, `DATABASE_URL`).
  `.env.example` shows the expected keys.
- Claude-generated commentary/predictions must never overwrite or alter code-calculated numeric values (price, P&L, RSI, MA, etc.) — Claude only interprets, it never computes.

## Verification (before considering a task done)
- Backend changes: run `pytest`, fix any failing tests.
- New endpoint: hit it with `curl`, show the actual response (don't just assert success).
- Frontend changes: run `npm run lint` + `npm run build` (includes typecheck) in `frontend/`,
  then visually check in the browser (dev server + running backend).

## Keeping This File Up To Date
This file is read at the start of every session — it must stay accurate.
Whenever you add a new endpoint, table, external dependency, command, or convention that isn't
reflected here, update the relevant section of this CLAUDE.md as part of finishing the task
(not as an afterthought). Keep the file under ~200 lines — if something needs more detail than a
line or two, put it in a separate doc under `docs/` and link to it from here instead of pasting
it in.

## Notes
- This project is single-user and local for now — no auth/multi-user system yet (see the phase
  plan, "personalization" section, for when this is added).
- Every generated report/recommendation shown in the UI must include a
  "this is not investment advice, for educational purposes only" disclaimer.
- Scheduler limitations (accepted): no US-market-holiday awareness (jobs run mon-fri regardless),
  and no lock between `/reports/refresh` and a simultaneously firing job (single-user; the unique
  constraint + upsert make the worst case two sequential writes to the same row).
