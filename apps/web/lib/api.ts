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
  const res = await fetch(`${API_BASE_URL}${path}`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`Request to ${path} failed with status ${res.status}`);
  }
  return res.json() as Promise<T>;
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
