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