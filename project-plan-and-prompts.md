# AI-Powered Investment/Analysis Platform — Phase Plan and Claude Code Prompts

**Tech Stack:** Python (FastAPI) + PostgreSQL + React (Vite/Tailwind) + Finnhub API + Anthropic Claude API
**How to use this:** Open a new Claude Code chat for each phase. Paste the prompt as-is. Each prompt
starts with a short context recap of what was built in previous phases, since a new chat won't see
prior conversations — but it will see the codebase and CLAUDE.md.

---

## Phase 0 — Project Foundation (Backend Skeleton + PostgreSQL)

**Goal:** FastAPI project, PostgreSQL connection, local Postgres via Docker, basic folder structure, health-check endpoint.

```
I'm building the backend for an investment/portfolio tracking platform. This is the first phase: project skeleton.

Tech stack: Python + FastAPI + PostgreSQL (SQLAlchemy ORM + Alembic migrations) + Finnhub API (later) + Anthropic Claude API (later).

What I need in this phase:
1. Set up a FastAPI project structure (under app/: main.py, models/, routers/, services/, core/config.py — a sensible layout).
2. Define a local PostgreSQL service in docker-compose.yml (with a persistent volume).
3. Set up SQLAlchemy + Alembic, prepare the initial migration setup.
4. Config management via .env (DATABASE_URL, and placeholders for FINNHUB_API_KEY and ANTHROPIC_API_KEY for later).
5. A simple /health endpoint — check both that the API is up and that the DB connection works.
6. requirements.txt / pyproject.toml with properly pinned versions.

Don't get into business logic yet (portfolio, stocks, reports) — just build a solid, extensible skeleton.
In README.md, document how to run this locally (docker-compose up, running migrations, starting uvicorn).

Also create a CLAUDE.md file at the project root following the standard best-practice structure
(project summary, tech stack, commands, architecture, conventions, boundaries, verification steps,
and a "keep this file updated" section). Fill it in based on what you actually built in this phase.
```

---

## Phase 1 — Portfolio Module (CRUD + Finnhub Integration + P&L)

**Goal:** Add/remove positions, purchase price input, real-time price fetching from Finnhub, P&L calculation, realized P&L tracking.

```
In Phase 0 we set up the FastAPI + PostgreSQL skeleton (docker-compose, SQLAlchemy, Alembic, /health endpoint).
Review the project folder and CLAUDE.md to understand the current structure, then continue with this phase.

This phase: Portfolio module.

Database models:
- `Position`: ticker, quantity, purchase_price, purchase_date, created_at
- `RealizedTrade`: ticker, quantity, purchase_price, sale_price, sale_date, realized_pnl (a record is created here when a position is closed)

What I need:
1. Create these tables via an Alembic migration.
2. A service layer for Finnhub integration (app/services/finnhub_client.py) — read the API key from
   .env, use the quote endpoint for real-time prices. Handle rate limits and failure cases (what
   happens if Finnhub doesn't respond).
3. REST endpoints:
   - POST /positions — add a new position (ticker, quantity, purchase price)
   - GET /positions — return all open positions with current Finnhub prices merged in, and computed
     unrealized P&L (% and $)
   - DELETE /positions/{id} or POST /positions/{id}/close — close a position, take a sale price,
     automatically create a RealizedTrade record
   - GET /positions/realized — list of closed trades (including total realized P&L)
4. Add basic validation that the ticker actually trades on NASDAQ (via Finnhub's symbol lookup).
5. Use Pydantic schemas to clearly define request/response models.

Add a few example curl commands to the README so I can test this.

Update CLAUDE.md: add the new endpoints, the finnhub_client service, and any new conventions
(e.g. how P&L is computed) to the relevant sections.
```

---

## Phase 2 — Frontend Dashboard (Portfolio Table + 15-Minute Auto-Refresh)

**Goal:** React UI, portfolio table, add-position form, auto price refresh every 15 minutes.

```
Backend Phases 0-1 are done: FastAPI + PostgreSQL + Finnhub-integrated portfolio CRUD endpoints are
ready (/positions, /positions/realized, etc.). Review the project folder and CLAUDE.md to learn the
API schema.

This phase: React frontend.

Tech: React (Vite) + Tailwind CSS + TanStack Query (React Query).

What I need:
1. Set up a new React project with Vite (under frontend/, separate from the backend).
2. A portfolio table component: for each position show ticker, quantity, purchase price, current
   price, P&L (% and $, green if profitable / red if at a loss).
3. An "Add Position" form — ticker, quantity, purchase price inputs, POSTs to the backend.
4. A realized P&L history table (separate tab/section).
5. Fetch data with TanStack Query, auto-refetch every 15 minutes (refetchInterval: 900000ms).
6. A clean, simple dashboard layout — a summary card at the top (total portfolio value, total P&L),
   the table below.
7. Handle loading and error states properly (if Finnhub doesn't respond, the user should see that).

Focus only on the portfolio view for now — don't touch daily reports/market pulse/other modules yet.

Update CLAUDE.md: add the frontend structure (key directories under frontend/src), the dev/build/lint
commands, and any new conventions to the relevant sections.
```

---

## Phase 3 — Scheduler + Claude API Integration (Pre-Market & Close Reports)

**Goal:** Two automated daily reports (pre-market + after-close), send data to Claude for commentary, cache in DB.

```
The portfolio module (Phase 1) and frontend dashboard (Phase 2) are done. Review the project folder
and CLAUDE.md to learn the current structure.

This phase: Automated daily reports + Claude API integration.

What I need:
1. Set up APScheduler with two jobs, timed against the US market schedule
   (America/New_York timezone, using pytz or zoneinfo):
   - Pre-market job: ~10 minutes before NASDAQ open
   - Close job: ~45 minutes after NASDAQ close (so data settles)
2. A `DailyReport` table: id, report_type ('premarket' / 'close'), report_date, content (JSON or
   text), created_at. The same report type shouldn't be regenerated for the same day (update if it
   exists, create if not).
3. Anthropic Claude API integration (app/services/claude_client.py) — read ANTHROPIC_API_KEY from
   .env, use claude-sonnet-4-6 as the model.
4. Pre-market job content: fetch futures/index data from Finnhub + that day's economic calendar
   (Finnhub economic calendar endpoint), structure it as JSON, send it to Claude. The prompt must
   clearly instruct: "Base your answer only on the data provided, do not invent numbers not in the
   data set, do not make definitive directional predictions, use conditional scenario language (if
   X happens, Y may follow)." Output: a 3-sentence summary + today's key events + a simple scenario
   analysis (if a data point like CPI/FOMC comes in high/in-line/low, what might happen).
5. Close job content: fetch actual closing data (S&P/Nasdaq/Dow % change, how the portfolio's
   holdings did that day), send to Claude. Output has two sections: "What happened today" (based on
   realized data, factual) + "Tomorrow's agenda" (tomorrow's economic calendar/earnings calendar +
   conditional scenarios, no certainty claims).
6. GET /reports/latest?type=premarket|close endpoint — when the user opens the app, return the
   already-cached report from the DB; don't call Claude on the fly.
7. POST /reports/refresh endpoint — manual trigger as a fallback (in case a scheduled job failed to run).

Keep the prompt templates sent to Claude in a separate directory (app/prompts/) so they're easy to
edit later.

Update CLAUDE.md: add the scheduler setup, the claude_client service, the report caching rule, and
the prompt-safety instruction to the relevant sections.
```

---

## Phase 4 — Market Pulse (Sector Rotation + Technical Positioning)

**Goal:** Sector ETF comparison, RSP vs S&P (real rotation vs. broad decline), 200/50-day MA positioning, heatmap.

```
The portfolio, dashboard, and daily report modules (Phases 0-3) are done. Review the project folder
and CLAUDE.md to learn the current structure.

This phase: the "Market Pulse" report — market-structure/technical focused, independent of macro data.

What I need:
1. A service that fetches daily/weekly performance from Finnhub for the major sector ETFs (XLK, XLF,
   XLV, XLE, XLI, XLY, XLP, XLU, XLB, XLRE, SMH, XBI, etc.).
2. RSP (equal-weight S&P) vs SPY (cap-weight S&P) comparison — a simple rule-based read on what the
   gap indicates (broad-based rally vs. a few mega-caps carrying the index), then have Claude explain
   this in plain language.
3. Where the major indices (S&P, Nasdaq) sit relative to their 200-day and 50-day moving averages
   (above/below, how far).
4. GET /market-pulse endpoint — combine the above data with Claude's commentary. Generate and cache
   this once a day (tied to the close job), reusing the caching pattern from Phase 3's DailyReport.
5. Add a "Market Pulse" tab to the frontend: a sector performance table, an RSP/SPY comparison card,
   and a simple heatmap visualization (sectors as color-coded tiles, green/red shading).

Reuse the Claude client and caching logic from Phase 3 — don't duplicate it.

Update CLAUDE.md: add the new endpoint, the sector-ETF service, and the caching pattern reuse note
to the relevant sections.
```

---

## Phase 5 — Sentiment & Volatility Report

**Goal:** Our own computed fear & greed score, a bull/bear-style indicator, commentary layer, glossary.

```
Market Pulse and the previous phases (0-4) are done. Review the project folder and CLAUDE.md to
learn the current structure.

This phase: the "Volatility and Sentiment" report.

Note: CNN doesn't offer a public/official Fear & Greed API, so we'll compute our own composite
sentiment score.

What I need:
1. A composite sentiment score service, built from components available via Finnhub:
   - VIX level relative to its historical average
   - Market momentum relative to its 125-day moving average
   - Ratio of stocks making new 52-week highs vs. new lows (a breadth indicator)
   Normalize these into a 0-100 score (0 = extreme fear, 100 = extreme greed) — document the
   methodology clearly in code comments so it can be tuned later.
2. GET /sentiment endpoint — return the score plus a breakdown of its components.
3. Send this score to Claude for commentary: "is the market showing extreme fear (a potential
   opportunity) or extreme greed (a risk signal)" — again, explanatory tone, not a directive.
4. A static "Glossary" endpoint (GET /glossary) — return short educational definitions of terms
   like VIX, RSI, MA200, breadth, RSP, sector rotation, as JSON. Don't have Claude regenerate this
   each time — write it once and store it in the DB or a static file.
5. Add a "Sentiment" tab to the frontend: a score gauge, component breakdown, Claude's commentary,
   and a link to the glossary.

Update CLAUDE.md: add the new endpoints and the sentiment scoring methodology note to the relevant
sections.
```

---

## Phase 6 — Portfolio Technical Tracking + Port News

**Goal:** Per-stock technical status (52-week high/low, MA200/50 position), earnings calendar alerts, per-stock news feed.

```
Sentiment and Market Pulse (Phases 0-5) are done. Review the project folder and CLAUDE.md to learn
the current structure.

This phase covers two modules: "Portfolio Technical Tracking" and "Port News".

Portfolio Technical Tracking:
1. For every stock in the portfolio, fetch historical price data from Finnhub and compute: distance
   from the 52-week high/low (%), and whether it's above or below its 200-day and 50-day moving
   averages.
2. Use Finnhub's earnings calendar endpoint to flag any portfolio holdings reporting earnings that week.
3. GET /portfolio/technical endpoint — return the above data per stock, with a simple
   "technically strong/weak" label (rule: above MA200 + close to the high = strong, the reverse = weak).

Port News:
4. A service using Finnhub's company-news endpoint to fetch current news for each stock in the portfolio.
5. GET /portfolio/{ticker}/news endpoint — return news specific to that ticker (headline, source,
   link, date).

Frontend:
6. Add technical-status columns to the portfolio table (MA200 status, distance to high/low, earnings
   alert icon).
7. Clicking a stock opens a modal/panel listing its news with source links.

Update CLAUDE.md: add the new endpoints, the earnings-calendar and news services, and the
"strong/weak" labeling rule to the relevant sections.
```

---

## Phase 7 — Setups (Opportunity Scanning) + Protect (Risk Report)

**Goal:** Technical opportunity detection (entry/exit/stop-loss suggestions), portfolio risk level and concentration analysis.

```
Technical tracking and news modules (Phases 0-6) are done. Review the project folder and CLAUDE.md
to learn the current structure.

This phase covers two modules: "Setups" and "Protect".

Setups:
1. Build an opportunity-scanning service using simple, explicitly defined rule sets (e.g. RSI
   oversold + price testing support near MA50 — 2-3 clear rules). Document the logic clearly in
   code comments so it can be adjusted later.
2. For each detected opportunity: an entry zone, a stop-loss level (e.g. below the last swing low),
   and a rationale.
3. GET /portfolio/setups endpoint, returning detected opportunities. If there are none, return an
   empty list — don't force a result.
4. Send this raw technical data to Claude to phrase the rationale in more readable language (but
   don't let Claude invent the numbers — entry/stop levels are computed by code, Claude only narrates).

Protect:
5. A portfolio risk-scoring service: concentration analysis (flag if a single position exceeds ~20%
   of the portfolio, similarly at the sector level), classify overall risk as low/medium/high.
6. Simple logic mapping that week's key macro events (CPI, FOMC, etc.) to which sectors/holdings in
   the portfolio are likely most sensitive (e.g. a rate decision → higher sensitivity for
   high-growth/tech names).
7. GET /portfolio/protect endpoint — return the risk score, the reasoning, and Claude's
   plain-language summary of it.

Frontend:
8. Add separate tabs/cards for "Setups" and "Protect".

Update CLAUDE.md: add the new endpoints, the rule-based setup logic, and the risk-scoring
methodology to the relevant sections.
```

---

## Phase 8 — Prediction Center + Risk Profile + Personalization (Advanced)

**Goal:** Simple prediction algorithms, historical accuracy tracking, a user risk-profile questionnaire, theme-based scanning.

```
Phases 0-7 are done (portfolio, reports, market pulse, sentiment, technical tracking, setups,
protect). Review the project folder and CLAUDE.md to learn the current structure.

This is the most ambitious part of the plan — proceed carefully, and don't claim certainty without
real statistical validation.

What I need:
1. A few simple, explicitly defined rule-based "prediction algorithms" (e.g. trend check — is price
   above/below N-day moving averages and in what direction; swing analysis — structure relative to
   the last N swing highs/lows). Don't build a complex ML model yet.
2. Log every prediction to a `Prediction` table (ticker, prediction_date, predicted_direction,
   algorithm_name). Add a job that, after a set period (e.g. 5 trading days), compares the
   prediction against the actual price and automatically marks it correct/incorrect.
3. GET /predictions/{ticker} — return past predictions and the historical accuracy rate (%) per
   algorithm. Transparency matters here: the user should be able to see the algorithm's actual track record.
4. A simple risk-profile questionnaire: a few questions (investment horizon, loss tolerance, capital
   amount) → classify the user as conservative/balanced/aggressive, compare that against the
   portfolio's current risk level (from Phase 7's Protect score), and flag any mismatch.
5. A simple theme-based scan: given a theme keyword (e.g. "space", "AI"), list relevant stocks
   using Finnhub's sector/industry classification or news search.

For every prediction/score produced in this phase, include in the API response a note that "this is
a statistical, historically-based indicator and does not guarantee outcomes."

Update CLAUDE.md: add the new endpoints, the prediction-tracking mechanism, and the disclaimer
convention to the relevant sections.
```

---

## General Notes (Keep In Mind For Every Phase)

- **In every Claude API prompt:** always keep the instruction "rely only on the given data, don't
  invent numbers, don't make definitive advice/directional claims."
- **Caching:** never let Claude be called more than a couple of times a day for the same thing —
  store in the DB, read from there.
- **Timezone:** use `America/New_York` as the reference for US market hours, convert to local time
  from there (handles DST automatically).
- **Disclaimer:** every report/recommendation screen in the frontend should carry a small note:
  "This content is not investment advice; it is for educational and informational purposes only." —
  worth adding as early as Phase 2/3.
- **CLAUDE.md maintenance:** each prompt above ends with an explicit reminder to update CLAUDE.md.
  If Claude Code skips it, just say "update CLAUDE.md for what you just built" before ending the session.
