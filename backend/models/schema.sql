 CREATE TABLE IF NOT EXISTS paper_portfolio (
    id              BIGSERIAL PRIMARY KEY,
    inr_balance     NUMERIC(15, 2) NOT NULL DEFAULT 100000.00,
    total_value     NUMERIC(15, 2) NOT NULL DEFAULT 100000.00,
    invested_value  NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    pnl_total       NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    pnl_today       NUMERIC(15, 2) NOT NULL DEFAULT 0.00,
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
  
INSERT INTO paper_portfolio (inr_balance, total_value)
VALUES (100000.00, 100000.00)
ON CONFLICT DO NOTHING;
  
CREATE TABLE IF NOT EXISTS trades (
    id              BIGSERIAL PRIMARY KEY,
    mode            TEXT NOT NULL CHECK (mode IN ('paper', 'live')),
    coin            TEXT NOT NULL,
    action          TEXT NOT NULL CHECK (action IN ('BUY', 'SELL')),
    status          TEXT NOT NULL DEFAULT 'OPEN'
                        CHECK (status IN ('OPEN', 'CLOSED_TP1', 'CLOSED_TP2',
                                          'CLOSED_SL', 'CLOSED_MANUAL', 'CANCELLED')),
    entry_price     NUMERIC(20, 2) NOT NULL,
    exit_price      NUMERIC(20, 2),
    stop_loss       NUMERIC(20, 2) NOT NULL,
    take_profit_1   NUMERIC(20, 2) NOT NULL,
    take_profit_2   NUMERIC(20, 2) NOT NULL,
    quantity        NUMERIC(20, 8) NOT NULL,
    position_inr    NUMERIC(15, 2) NOT NULL,
    risk_inr        NUMERIC(15, 2) NOT NULL,
    pnl_gross       NUMERIC(15, 2) DEFAULT 0,
    pnl_after_tax   NUMERIC(15, 2) DEFAULT 0,
    tax_provision   NUMERIC(15, 2) DEFAULT 0,
    tds_deducted    NUMERIC(15, 2) DEFAULT 0,
    confidence      NUMERIC(5, 2) NOT NULL,
    risk_reward     TEXT,
    reasoning       TEXT,
    signals         JSONB,
    sentiment       JSONB,
    coindcx_order_id TEXT,
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    closed_at       TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
  
CREATE TABLE IF NOT EXISTS open_positions (
    id              BIGSERIAL PRIMARY KEY,
    trade_id        BIGINT REFERENCES trades(id),
    coin            TEXT NOT NULL,
    action          TEXT NOT NULL,
    entry_price     NUMERIC(20, 2) NOT NULL,
    current_price   NUMERIC(20, 2),
    stop_loss       NUMERIC(20, 2) NOT NULL,
    take_profit_1   NUMERIC(20, 2) NOT NULL,
    take_profit_2   NUMERIC(20, 2) NOT NULL,
    quantity        NUMERIC(20, 8) NOT NULL,
    position_inr    NUMERIC(15, 2) NOT NULL,
    unrealized_pnl  NUMERIC(15, 2) DEFAULT 0,
    tp1_hit         BOOLEAN DEFAULT FALSE,
    mode            TEXT NOT NULL,
    opened_at       TIMESTAMPTZ DEFAULT NOW(),
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
 
  
CREATE TABLE IF NOT EXISTS performance_metrics (
    id              BIGSERIAL PRIMARY KEY,
    total_trades    INTEGER DEFAULT 0,
    winning_trades  INTEGER DEFAULT 0,
    losing_trades   INTEGER DEFAULT 0,
    win_rate        NUMERIC(5, 2) DEFAULT 0,
    profit_factor   NUMERIC(8, 4) DEFAULT 0,
    max_drawdown    NUMERIC(5, 2) DEFAULT 0,
    total_pnl       NUMERIC(15, 2) DEFAULT 0,
    best_trade_pnl  NUMERIC(15, 2) DEFAULT 0,
    worst_trade_pnl NUMERIC(15, 2) DEFAULT 0,
    avg_win         NUMERIC(15, 2) DEFAULT 0,
    avg_loss        NUMERIC(15, 2) DEFAULT 0,
    avg_confidence  NUMERIC(5, 2) DEFAULT 0,
  
    criteria_win_rate_pass      BOOLEAN DEFAULT FALSE,
    criteria_drawdown_pass      BOOLEAN DEFAULT FALSE,
    criteria_profit_factor_pass BOOLEAN DEFAULT FALSE,
    all_criteria_met            BOOLEAN DEFAULT FALSE,
    live_mode_unlocked          BOOLEAN DEFAULT FALSE,
 
    calculated_at   TIMESTAMPTZ DEFAULT NOW()
);
  
INSERT INTO performance_metrics DEFAULT VALUES;
  
CREATE TABLE IF NOT EXISTS agent_logs (
    id              BIGSERIAL PRIMARY KEY,
    coin            TEXT NOT NULL,
    action_taken    TEXT NOT NULL CHECK (action_taken IN ('BUY', 'SELL', 'HOLD', 'SKIPPED')),
    skip_reason     TEXT,
    confidence      NUMERIC(5, 2),
    indicators      JSONB,
    sentiment       JSONB,
    gemini_response JSONB,
    current_price   NUMERIC(20, 2),
    cycle_time      TIMESTAMPTZ DEFAULT NOW()
);
  
CREATE TABLE IF NOT EXISTS coin_performance (
    id              BIGSERIAL PRIMARY KEY,
    coin            TEXT UNIQUE NOT NULL,
    total_trades    INTEGER DEFAULT 0,
    winning_trades  INTEGER DEFAULT 0,
    win_rate        NUMERIC(5, 2) DEFAULT 0,
    total_pnl       NUMERIC(15, 2) DEFAULT 0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);
 
INSERT INTO coin_performance (coin) VALUES
    ('BTC/INR'), ('ETH/INR'), ('BNB/INR')
ON CONFLICT DO NOTHING;
  
CREATE TABLE IF NOT EXISTS daily_summary (
    id              BIGSERIAL PRIMARY KEY,
    date            DATE UNIQUE NOT NULL DEFAULT CURRENT_DATE,
    trades_taken    INTEGER DEFAULT 0,
    wins            INTEGER DEFAULT 0,
    losses          INTEGER DEFAULT 0,
    pnl_gross       NUMERIC(15, 2) DEFAULT 0,
    pnl_after_tax   NUMERIC(15, 2) DEFAULT 0,
    tax_provision   NUMERIC(15, 2) DEFAULT 0,
    portfolio_value NUMERIC(15, 2) DEFAULT 100000,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
  
CREATE INDEX IF NOT EXISTS idx_trades_coin ON trades(coin);
CREATE INDEX IF NOT EXISTS idx_trades_status ON trades(status);
CREATE INDEX IF NOT EXISTS idx_trades_mode ON trades(mode);
CREATE INDEX IF NOT EXISTS idx_trades_opened_at ON trades(opened_at DESC);
CREATE INDEX IF NOT EXISTS idx_agent_logs_cycle ON agent_logs(cycle_time DESC);
CREATE INDEX IF NOT EXISTS idx_open_positions_coin ON open_positions(coin);
  
ALTER TABLE trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_portfolio ENABLE ROW LEVEL SECURITY;
ALTER TABLE performance_metrics ENABLE ROW LEVEL SECURITY;
ALTER TABLE agent_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE open_positions ENABLE ROW LEVEL SECURITY;
ALTER TABLE coin_performance ENABLE ROW LEVEL SECURITY;
ALTER TABLE daily_summary ENABLE ROW LEVEL SECURITY;
  
CREATE POLICY "service_role_all" ON trades FOR ALL USING (true);
CREATE POLICY "service_role_all" ON paper_portfolio FOR ALL USING (true);
CREATE POLICY "service_role_all" ON performance_metrics FOR ALL USING (true);
CREATE POLICY "service_role_all" ON agent_logs FOR ALL USING (true);
CREATE POLICY "service_role_all" ON open_positions FOR ALL USING (true);
CREATE POLICY "service_role_all" ON coin_performance FOR ALL USING (true);
CREATE POLICY "service_role_all" ON daily_summary FOR ALL USING (true);