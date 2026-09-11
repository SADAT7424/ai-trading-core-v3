/**
 * Thin API client. The web app has no business logic of its own — it only
 * calls the FastAPI backend. See AGENTS.md: "web — thin client".
 *
 * Two different URLs are needed:
 * - INTERNAL_API_URL: used when this code runs on the server (inside the
 *   Docker network), where the API is reachable at http://api:8000.
 * - NEXT_PUBLIC_API_URL: used if this code ever runs in the browser, where
 *   the API must be reached via its public/forwarded URL instead.
 */
const API_BASE_URL =
  process.env.INTERNAL_API_URL ??
  process.env.NEXT_PUBLIC_API_URL ??
  "http://localhost:8000";

export interface HealthResponse {
  status: string;
  environment: string;
  time: string;
}

export interface ReadyResponse {
  status: string;
  dependencies: {
    database: string;
    redis: string;
  };
}

export interface GoldScore {
  real_yield_contribution: number;
  inflation_contribution: number;
  policy_contribution: number;
  usd_contribution: number;
  total: number;
  bias: "BULLISH" | "NEUTRAL" | "BEARISH";
}

export interface MacroRegimeResponse {
  as_of: string;
  inflation_yoy_pct: number;
  inflation_level: "LOW" | "MODERATE" | "HIGH";
  inflation_trend: "RISING" | "FALLING" | "FLAT";
  unemployment_rate_pct: number;
  employment_condition: "STRENGTHENING" | "STABLE" | "WEAKENING";
  fed_funds_rate_pct: number;
  policy_stance: "DOVISH" | "NEUTRAL" | "HAWKISH";
  real_yield_10y_pct: number;
  real_yield_level: "NEGATIVE" | "LOW" | "HIGH";
  breakeven_inflation_10y_pct: number;
  breakeven_inflation_note: string;
  usd_index_level: number;
  usd_condition: "STRENGTHENING" | "STABLE" | "WEAKENING";
  regime: "REFLATION" | "STAGFLATION" | "GOLDILOCKS" | "DEFLATIONARY";
  gold_score: GoldScore;
}

async function getJson<T>(path: string): Promise<T> {
  return fetchWithRetry(async () => {
    const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
    if (!res.ok) {
      throw new Error(`Request to ${path} failed with status ${res.status}`);
    }
    return res.json() as Promise<T>;
  });
}

/**
 * Retries once after a short delay, but ONLY for network-level failures
 * (e.g. "fetch failed" — the API process not accepting connections yet,
 * which happens for a few seconds right after `docker compose up`). A
 * normal HTTP error response (400, 404, etc.) is a real answer from a
 * running API and is never retried — retrying those would just mask
 * genuine errors instead of fixing a timing issue.
 */
async function fetchWithRetry<T>(attempt: () => Promise<T>): Promise<T> {
  try {
    return await attempt();
  } catch (err) {
    const isNetworkError = err instanceof TypeError || /fetch failed/i.test(String(err));
    if (!isNetworkError) throw err;
    await new Promise((resolve) => setTimeout(resolve, 800));
    return attempt();
  }
}

export function getHealth(): Promise<HealthResponse> {
  return getJson<HealthResponse>("/api/v1/system/health");
}

export function getReady(): Promise<ReadyResponse> {
  return getJson<ReadyResponse>("/api/v1/system/ready");
}

export function getMacroRegime(): Promise<MacroRegimeResponse> {
  return getJson<MacroRegimeResponse>("/api/v1/macro/regime");
}

export interface MarketStateResponse {
  symbol: string;
  interval: string;
  as_of: string;
  latest_close: number;
  sma_fast: number;
  sma_slow: number;
  trend: "BULLISH" | "BEARISH" | "NEUTRAL";
  roc_pct: number;
  momentum: "POSITIVE" | "NEGATIVE" | "FLAT";
  atr: number;
  atr_pct_of_price: number;
  volatility: "HIGH" | "NORMAL" | "LOW";
  rsi: number;
  rsi_condition: "OVERBOUGHT" | "OVERSOLD" | "NEUTRAL";
  regime: "TRENDING" | "RANGING" | "HIGH_VOLATILITY";
}

export function getMarketState(symbol: string, interval = "1day"): Promise<MarketStateResponse> {
  return getJson<MarketStateResponse>(
    `/api/v1/market/state/${symbol}?interval=${interval}`
  );
}

export interface OpportunityResponse {
  symbol: string;
  interval: string;
  as_of: string;
  latest_close: number;
  setup: {
    direction: "LONG" | "SHORT" | "NONE";
    distance_to_fast_sma_pct: number;
    technical_score: number;
  };
  classification:
    | "MACRO_ALIGNED_LONG"
    | "MACRO_ALIGNED_SHORT"
    | "COUNTER_MACRO_LONG"
    | "COUNTER_MACRO_SHORT"
    | "MACRO_NEUTRAL";
  gold_macro_score: number;
  score: {
    technical_score: number;
    macro_alignment_score: number;
    overall_score: number;
    quality: "A" | "B" | "C" | "D";
  } | null;
}

export function getOpportunity(symbol: string, interval = "1day"): Promise<OpportunityResponse> {
  return getJson<OpportunityResponse>(`/api/v1/opportunities/${symbol}?interval=${interval}`);
}

export interface TradeEvaluationResponse {
  symbol: string;
  direction: "LONG" | "SHORT" | "NONE";
  entry_price: number;
  stop_price: number | null;
  quality: "A" | "B" | "C" | "D" | null;
  kill_switch_state: "NORMAL" | "ALERT" | "SAFE_MODE" | "EMERGENCY_STOP";
  approved: boolean;
  reasons: string[];
  notes: string[];
  position: {
    risk_pct: number;
    risk_amount: number;
    units: number;
    exposure_pct: number;
  } | null;
}

async function postJson<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, { method: "POST", cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export function evaluateTrade(symbol: string, interval = "1day"): Promise<TradeEvaluationResponse> {
  // Safe to retry on a network-level failure: this only computes and
  // returns a decision, it never writes anything. Unlike monitorPosition
  // below (which can close a trade), a retried duplicate call here is
  // harmless — it would just recompute the identical answer.
  return fetchWithRetry(() =>
    postJson<TradeEvaluationResponse>(
      `/api/v1/risk/evaluate-trade/${symbol}?interval=${interval}`
    )
  );
}

export interface OrderResponse {
  id: string;
  symbol: string;
  direction: string;
  status: "REJECTED" | "FILLED" | "CANCELLED";
  broker: string;
  requested_price: number;
  filled_price: number | null;
  stop_price: number;
  units: number;
  risk_amount: number;
  risk_pct: number;
  quality_grade: string | null;
  classification: string | null;
  rejection_reasons: string | null;
  created_at: string;
  filled_at: string | null;
}

export function getOrders(symbol?: string, limit = 10): Promise<OrderResponse[]> {
  const params = new URLSearchParams({ limit: String(limit) });
  if (symbol) params.set("symbol", symbol);
  return getJson<OrderResponse[]>(`/api/v1/execution/orders?${params.toString()}`);
}

export interface PositionResponse {
  id: string;
  symbol: string;
  direction: string;
  status: "OPEN" | "CLOSED";
  entry_price: number;
  initial_stop_price: number;
  current_stop_price: number;
  target_price: number;
  units: number;
  entry_classification: string | null;
  entry_quality_grade: string | null;
  entry_gold_macro_score: number | null;
  entry_thesis: string;
  close_price: number | null;
  close_reason: string | null;
  realized_pnl: number | null;
  opened_at: string;
  closed_at: string | null;
}

export interface MonitorResponse {
  position: PositionResponse;
  current_price: number;
  thesis_health_score: number;
  thesis_health_status: "STRONG" | "HEALTHY" | "WEAKENING" | "CRITICAL" | "INVALIDATED";
  thesis_reasons: string[];
  exit_action: "HOLD" | "EXIT";
  exit_reason: "NONE" | "STOP_LOSS" | "TAKE_PROFIT" | "THESIS_INVALIDATED";
  notes: string[];
}

export function getOpenPositions(symbol?: string): Promise<PositionResponse[]> {
  const params = symbol ? `?symbol=${symbol}` : "";
  return getJson<PositionResponse[]>(`/api/v1/positions${params}`);
}

export function monitorPosition(positionId: string): Promise<MonitorResponse> {
  return postJson<MonitorResponse>(`/api/v1/positions/${positionId}/monitor`);
}

export interface PerformanceSummaryResponse {
  total_trades: number;
  wins: number;
  losses: number;
  win_rate_pct: number;
  total_realized_pnl: number;
  average_win: number;
  average_loss: number;
  profit_factor: number | null;
  expectancy: number;
}

export function getPerformanceSummary(symbol?: string): Promise<PerformanceSummaryResponse> {
  const params = symbol ? `?symbol=${symbol}` : "";
  return getJson<PerformanceSummaryResponse>(`/api/v1/performance/summary${params}`);
}
