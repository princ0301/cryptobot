# CryptoAgent

CryptoAgent is a crypto trading dashboard and backend agent built for Crypto markets on CoinDCX. It combines:

- A `FastAPI` backend for market ingestion, scheduling, trade simulation, performance tracking, and API endpoints
- A `React + Vite` frontend for portfolio monitoring, trade history, market exploration, and coin-universe management
- A `Supabase` database for portfolio, trades, logs, and performance metrics
- A `Groq`-powered decision layer that sits on top of rule-based technical filters

The system supports both paper-trading and live-trading workflows, with paper mode used as the safer default path for strategy validation and promotion gating.

## Current Status

The project already supports:

- Scheduled market scans
- Technical indicator analysis
- Sentiment-aware filtering
- Paper trade execution
- Position monitoring with stop loss, TP1, TP2, profit lock, and trailing stop logic
- Performance tracking and promotion criteria
- A frontend dashboard for monitoring the agent
- Dynamic management of the trading universe

The project includes live-trading support, CoinDCX private API integration, live-mode routes, database support for live trades, and frontend live-mode UX. Paper trading is the most clearly wired and verifiable automated execution path in the current codebase, while live mode is present as a supported operating mode with stricter activation gating.

## Repository Structure

```text
cryptoagent/
├─ backend/
│  ├─ agents/          # Trading logic, scheduler, LLM integration, risk, execution, performance
│  ├─ data/            # CoinDCX adapters, sentiment sources, coin registry
│  ├─ models/          # Supabase bootstrap and SQL schema
│  ├─ routes/          # FastAPI route modules
│  ├─ main.py          # FastAPI app entry point
│  ├─ config.py        # Environment-backed settings
│  ├─ requirements.txt
│  └─ test_connections.py
├─ frontend/
│  ├─ src/
│  │  ├─ components/   # Dashboard UI blocks
│  │  ├─ hooks/        # Polling hook
│  │  ├─ utils/        # API client
│  │  └─ App.jsx       # Frontend entry composition
│  ├─ public/
│  ├─ package.json
│  └─ vite.config.js
└─ README.md
```

## How It Works

### 1. Application startup

When the backend starts:

- Logging is configured for console and rotating file output
- Settings are loaded from `backend/.env`
- Supabase connectivity is initialized
- The scheduler is started
- An optional startup scan is queued

Main entry point:

- `backend/main.py`

### 2. Trading universe

The list of watched and tradable INR pairs is stored locally in:

- `backend/data/coins.json`

This file controls:

- Which coins appear in the dashboard
- Which coins are considered by the scanner
- Which coins are allowed to be traded by the agent

The backend exposes endpoints to:

- Search active INR markets from CoinDCX
- Add a coin to the watchlist
- Toggle whether a coin is watched
- Toggle whether a coin is tradable
- Remove a coin if it has no open position

Before a coin can become tradable, the backend validates:

- 24h notional volume
- Bid/ask spread
- Minimum candle history

### 3. Market scan and ranking

On each main cycle, the scheduler:

- Fetches live tickers from CoinDCX
- Loads the configured tradable pairs
- Ranks them by:
  - Notional volume
  - 24h momentum
  - Spread penalty
- Builds a shortlist for analysis

### 4. Technical analysis

For each shortlisted pair, the backend fetches hourly candles and computes indicators:

- EMA 50
- EMA 200
- RSI 14
- MACD
- ATR
- Bollinger Bands
- 30-period volume average and volume ratio
- Recent support and resistance

From these, it derives signals such as:

- Trend direction
- Price vs EMA50
- RSI zone
- MACD crossover state
- ATR percentage volatility
- Bollinger position
- Distance to support/resistance

### 5. Rule-based scoring

The agent scores the setup using a weighted ruleset:

- EMA/trend quality
- RSI quality
- MACD quality
- Volume quality
- Support/resistance quality

The score is then used to determine whether the setup is:

- Strong enough to consider
- Blocked by weak volume
- Good enough to override some raw volume weakness
- Strong enough to send to the LLM

Weak setups are filtered early to reduce unnecessary model calls.

### 6. Sentiment overlay

The backend also pulls sentiment from:

- Fear & Greed Index
- CoinGecko global market dominance
- Reddit RSS feeds

These are combined into a sentiment regime that can:

- Add caution
- Trigger a temporary pause on new entries
- Label the market as bullish, neutral, or bearish

### 7. LLM decision layer

If a setup passes the rule-based prefilter, the backend asks LLM for a structured JSON decision:

- `BUY`
- `HOLD`
- `SELL` is allowed by schema

The model is instructed to:

- Stay conservative
- Respect minimum confidence
- Account for tax drag
- Avoid buying weak or contradictory setups

If LLM fails or returns invalid JSON, a fallback rules-based decision is used instead.

### 8. Trade execution modes

If the decision is `BUY` and confidence is high enough, the system is structured to support trading in different modes.

#### Paper mode

In paper mode:

- Position size is calculated from risk and stop distance
- Capital caps are enforced
- A simulated paper trade is inserted into Supabase
- An open position is created
- A new paper portfolio snapshot is stored

#### Live mode

For live mode, the codebase also includes:

- CoinDCX authenticated account balance access
- CoinDCX order placement helpers
- CoinDCX order cancellation helpers
- CoinDCX order status helpers
- Live-mode status and activation routes
- Database schema support for trades stored with `mode = 'live'`

This means the project is not paper-only. It has real live-trading infrastructure built in, alongside the paper-trading engine.

### 9. Open position monitoring

Open positions are monitored on a faster schedule than the main scan.

The monitor can:

- Close at stop loss
- Realize 50% at TP1
- Move stop to breakeven after TP1
- Lock some profit before TP1 in favorable conditions
- Advance a trailing stop after enough progress
- Fully exit at TP2

### 10. Performance and promotion criteria

Performance is recalculated from closed paper trades and portfolio history.

Metrics include:

- Total trades
- Win rate
- Profit factor
- Max drawdown
- Total P&L
- Best/worst trade
- Average win/loss
- Average confidence

The agent is considered eligible for live promotion only after meeting configured thresholds and minimum trade count.

## Backend Stack

- `FastAPI`
- `Uvicorn`
- `Supabase`
- `httpx`
- `pandas`
- `pandas-ta`
- `numpy`
- `APScheduler`
- `Groq`
- `pydantic-settings`

## Frontend Stack

- `React`
- `Vite`
- `Tailwind CSS`
- `Axios`
- `Recharts`
- `lucide-react`

## Environment Variables

Create `backend/.env` with values for the following keys as needed.

### Exchange and trading

```env
COINDCX_API_KEY=
COINDCX_API_SECRET=
```

### Supabase

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_KEY=
```

### Groq

```env
GROQ_API_KEY=
GROQ_API_KEY_1=
GROQ_API_KEY_2=
GROQ_MODEL=llama-3.3-70b-versatile
```

### App and strategy configuration

Examples of important settings already supported by `backend/config.py`:

```env
PAPER_STARTING_BALANCE=100000
RISK_PER_TRADE_PERCENT=2
MAX_POSITION_PERCENT=25
MAX_OPEN_POSITIONS=5
MIN_CONFIDENCE_THRESHOLD=65
TRADE_INTERVAL_MINUTES=60
POSITION_MONITOR_INTERVAL_MINUTES=5
SCAN_TOP_N=8
STARTUP_SCAN_ENABLED=true
STARTUP_TRADE_ENABLED=false
FRONTEND_URL=http://localhost:5173
BACKEND_PORT=8000
MIN_WIN_RATE=60
MIN_TRADES_REQUIRED=30
MAX_DRAWDOWN_ALLOWED=15
MIN_PROFIT_FACTOR=1.5
```

## Database Setup

The backend expects the Supabase schema defined in:

- `backend/models/schema.sql`

Apply that SQL in your Supabase project before starting the app.

Main tables:

- `paper_portfolio`
- `trades`
- `open_positions`
- `performance_metrics`
- `agent_logs`
- `coin_performance`
- `daily_summary`

## Local Development

### 1. Backend setup

From the `backend` directory:

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Start the backend:

```powershell
python main.py
```

The API will run on:

- `http://localhost:8000`

Docs:

- `http://localhost:8000/docs`

### 2. Frontend setup

From the `frontend` directory:

```powershell
npm install
npm run dev
```

The frontend will run on:

- `http://localhost:5173`

The frontend API base URL defaults to:

- `http://localhost:8000`

You can override it with:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## API Overview

### System

- `GET /`
- `GET /health`

### Agent

- `GET /agent/status`
- `GET /agent/last-analysis`
- `GET /agent/scan-shortlist`
- `POST /agent/run-now`
- `POST /agent/start`
- `POST /agent/stop`

### Market

- `GET /market/prices`
- `GET /market/sentiment`

### Trades

- `GET /trades/history`
- `GET /trades/open`
- `GET /trades/{trade_id}`

### Portfolio

- `GET /portfolio/balance`
- `GET /portfolio/history`

### Performance

- `GET /performance/metrics`
- `GET /performance/criteria`
- `GET /performance/coins`

### Coins

- `GET /coins`
- `GET /coins/search`
- `POST /coins`
- `PATCH /coins/{symbol}`
- `DELETE /coins/{symbol}`

### Live Mode

- `GET /live/status`
- `POST /live/activate`
- `GET /live/prices`
- `GET /live/sentiment`

## Frontend Features

The frontend is organized around a dashboard with several tabs.

### Dashboard

- Live price cards for selected pairs
- Portfolio summary
- Latest agent analyses
- Latest buy card
- Open positions
- Criteria tracker
- Sentiment bar

### Trades

- Trade history table
- Filters for all, open, win, and loss trades
- Expandable trade reasoning details

### Portfolio

- Summary cards
- Portfolio history chart
- Open positions
- Promotion metrics

### Market

- Ranked shortlist visibility
- Searchable market explorer
- Favorite pinning in local storage
- Coin universe management

### Live Mode

- Promotion gate UI
- Real-money warning UX
- Activation placeholders

## Testing and Diagnostics

A helper script exists at:

- `backend/test_connections.py`

It checks:

- Environment variable presence
- CoinDCX public API access
- Fear & Greed API
- CoinGecko API
- Groq connectivity
- Supabase connectivity

Run it from `backend`:

```powershell
python test_connections.py
```

## Important Design Notes

### The project supports both paper and live trading

The repository includes:

- Paper-trading execution and monitoring logic
- Live-mode API routes
- CoinDCX private exchange helpers for authenticated actions
- Schema support for live trades and promotion unlocking
- Frontend live-mode activation UX

Paper trading is the easiest path to verify from the code because the scheduler and executor flow are explicitly wired around it. Live trading is also part of the project design and implementation, but it is more tightly gated and should be validated carefully before real-money use.

### Supabase is the operational data store

Trades, logs, portfolio snapshots, and performance metrics all live in Supabase. The local JSON registry only manages the configured coin universe.

### The strategy is long-biased

Although some response schemas mention `SELL`, the actual implemented trading flow is designed around opening long paper trades and managing those positions.

### Tax-aware targets are built in

The backend adjusts target logic using Indian tax and TDS assumptions. That affects how take-profit levels are computed and how net P&L is recorded.

### The UI is polling-based

The frontend uses repeated polling instead of websockets, which keeps the architecture simple but means data freshness depends on poll intervals.

 