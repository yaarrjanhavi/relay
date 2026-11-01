/**
 * API client library for Relay FastAPI backend.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface RouteResponse {
  request_id: string;
  category: string;
  confidence: float;
  tier: "small" | "medium" | "large";
  model_id: string;
  fallback_used: boolean;
  cache_hit: boolean;
  cost_usd: number;
  latency_ms: number;
  response: string;
}

export interface PosteriorArmStat {
  category: string;
  tier: "small" | "medium" | "large";
  alpha: number;
  beta: number;
  mean: number;
  variance: number;
  ci90: [number, number];
  evidence: number;
  cold_start: boolean;
}

export interface StatsResponse {
  posteriors: PosteriorArmStat[];
  request_count: number;
  total_cost_usd: number;
}

export interface HistoryPoint {
  ts: number;
  category: string;
  tier: string;
  alpha: number;
  beta: number;
  mean: number;
}

export interface SystemMetricsResponse {
  cache_hit_rate: number;
  p50_latency_ms: number;
  p95_latency_ms: number;
  fallback_rate: number;
  rate_limited_count: number;
  total_cost: number;
  estimated_savings_vs_always_large: number;
  total_requests: number;
}

export interface DeadLetterItem {
  id: string;
  payload: any;
  error: string;
  created_at: number;
}

export interface BenchmarkMetrics {
  mean_quality: number;
  std_quality: number;
  mean_cost: number;
  std_cost: number;
  mean_cost_saved_pct: number;
  std_cost_saved_pct: number;
}

export interface BenchmarkResult {
  mode: string;
  seeds: number;
  train_size: number;
  test_size: number;
  strategies: Record<string, BenchmarkMetrics>;
  raw_results: any;
}

type float = number;

export async function routePrompt(prompt: string, idempotencyKey?: string): Promise<RouteResponse> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (idempotencyKey) {
    headers["Idempotency-Key"] = idempotencyKey;
  }

  const res = await fetch(`${API_BASE}/v1/route`, {
    method: "POST",
    headers,
    body: JSON.stringify({ prompt }),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP ${res.status}: Failed to route prompt`);
  }

  return res.json();
}

export async function submitFeedback(requestId: string, thumbsUp: boolean): Promise<{ status: string }> {
  const res = await fetch(`${API_BASE}/v1/feedback`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ request_id: requestId, thumbs_up: thumbsUp }),
  });

  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP ${res.status}: Feedback submission failed`);
  }

  return res.json();
}

export async function fetchStats(): Promise<StatsResponse> {
  const res = await fetch(`${API_BASE}/v1/stats`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch posteriors and stats");
  return res.json();
}

export async function fetchHistory(limit: number = 500): Promise<{ history: HistoryPoint[] }> {
  const res = await fetch(`${API_BASE}/v1/history?limit=${limit}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch posterior history");
  return res.json();
}

export async function fetchMetrics(): Promise<SystemMetricsResponse> {
  const res = await fetch(`${API_BASE}/v1/system/metrics`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch system metrics");
  return res.json();
}

export async function fetchDeadLetters(): Promise<{ dead_letters: DeadLetterItem[]; total_count: number }> {
  const res = await fetch(`${API_BASE}/v1/admin/dead-letters`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to fetch dead-letters");
  return res.json();
}

export async function runBenchmarkReplay(mode: "simulated" | "real", seeds: number = 10): Promise<BenchmarkResult> {
  const res = await fetch(`${API_BASE}/v1/benchmark/replay?mode=${mode}&seeds=${seeds}`, {
    method: "POST",
    cache: "no-store",
  });
  if (!res.ok) {
    const errorBody = await res.json().catch(() => ({}));
    throw new Error(errorBody.detail || `HTTP ${res.status}: Benchmark replay failed`);
  }
  return res.json();
}
