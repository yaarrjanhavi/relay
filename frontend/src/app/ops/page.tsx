"use client";

import { useEffect, useState } from "react";
import { fetchMetrics, fetchDeadLetters, SystemMetricsResponse, DeadLetterItem } from "@/lib/api";
import { Check } from "lucide-react";

export default function OpsPage() {
  const [metrics, setMetrics] = useState<SystemMetricsResponse | null>(null);
  const [deadLetters, setDeadLetters] = useState<DeadLetterItem[]>([]);
  const [loading, setLoading] = useState(true);

  const loadOpsData = async () => {
    setLoading(true);
    try {
      const m = await fetchMetrics();
      setMetrics(m);
      const dl = await fetchDeadLetters();
      setDeadLetters(dl.dead_letters);
    } catch (err) {
      console.error("Failed to load ops data:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOpsData();
  }, []);

  return (
    <div className="space-y-8">
      {/* Top Controls */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl sm:text-6xl text-black uppercase tracking-tight leading-none">
            UNDER THE HOOD
          </h1>
          <p className="font-mono text-sm sm:text-base text-black mt-2 font-medium">
            Real-time infrastructure health: token bucket rate limits, response caching, fallbacks, and dead-letter events.
          </p>
        </div>

        <button
          onClick={loadOpsData}
          disabled={loading}
          aria-label="Refresh ops telemetry"
          className="self-start md:self-auto px-5 py-3 bg-white text-black font-heading text-sm uppercase border-[3px] border-black brutalist-shadow-button brutalist-button-press transition-all flex items-center space-x-2 cursor-pointer disabled:opacity-50"
        >
          {loading ? (
            <div className="brutalist-spinner" />
          ) : (
            <span className="w-3 h-3 bg-black inline-block" />
          )}
          <span>{loading ? "REFRESHING..." : "REFRESH"}</span>
        </button>
      </div>

      {/* 4 Operational Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Cache Hit Ratio */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#35F28A] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              CACHE HIT RATIO
            </span>
            <div className="my-3">
              <span className="font-heading text-4xl sm:text-5xl text-black block">
                {((metrics?.cache_hit_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Exact-match SHA-256 (30m TTL)
            </span>
          </div>
        </div>

        {/* Rate-Limited Events */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#FF9F1C] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              RATE-LIMITED EVENTS
            </span>
            <div className="my-3">
              <span className="font-heading text-4xl sm:text-5xl text-black block">
                {metrics?.rate_limited_count || 0}
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              HTTP 429 throttled requests
            </span>
          </div>
        </div>

        {/* Fallback Escalation Rate */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#FF9F1C] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              FALLBACK ESCALATION
            </span>
            <div className="my-3">
              <span className="font-heading text-4xl sm:text-5xl text-black block">
                {((metrics?.fallback_rate || 0) * 100).toFixed(1)}%
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Small → Medium → Large escalations
            </span>
          </div>
        </div>

        {/* Latency p50 / p95 */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#B388FF] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              LATENCY (P50 / P95)
            </span>
            <div className="my-3">
              <span className="font-heading text-3xl sm:text-4xl text-black block truncate">
                {metrics?.p50_latency_ms.toFixed(0) || 0} / {metrics?.p95_latency_ms.toFixed(0) || 0} ms
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Roundtrip inference latency
            </span>
          </div>
        </div>
      </div>

      {/* Dead Letter Queue Section */}
      <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
          <div>
            <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
              TRANSACTIONAL OUTBOX DEAD-LETTER QUEUE
            </h2>
            <div className="h-1 w-24 bg-black mt-1" />
          </div>

          <span className="font-mono text-xs font-bold text-[#333333] px-3 py-1 bg-white border-2 border-black">
            Migrated after 5 exponential backoff retries ({deadLetters.length} Failed Events)
          </span>
        </div>

        {deadLetters.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b-[4px] border-black">
                  <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                    EVENT ID
                  </th>
                  <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                    FAILURE ERROR
                  </th>
                  <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                    TIMESTAMP
                  </th>
                  <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                    PAYLOAD SUMMARY
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y-[3px] divide-black">
                {deadLetters.map((dl) => (
                  <tr key={dl.id} className="bg-white hover:bg-[#FFF8CC] transition-colors relative">
                    {/* Event ID with 8px #FF3B30 red left border */}
                    <td className="p-3 border-[3px] border-black border-l-[8px] border-l-[#FF3B30] font-bold text-black">
                      {dl.id.slice(0, 8)}...
                    </td>
                    <td className="p-3 border-[3px] border-black font-bold text-[#B91C1C] max-w-xs break-words">
                      {dl.error}
                    </td>
                    <td className="p-3 border-[3px] border-black text-black">
                      {new Date(dl.created_at * 1000).toLocaleString()}
                    </td>
                    <td className="p-3 border-[3px] border-black max-w-sm">
                      <pre className="p-2 bg-black text-white font-mono text-[11px] overflow-x-auto whitespace-pre-wrap max-h-24">
                        {typeof dl.payload === "string" ? dl.payload : JSON.stringify(dl.payload, null, 2)}
                      </pre>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-10 border-[3px] border-dashed border-black bg-white flex flex-col items-center justify-center text-center space-y-3">
            <div className="w-12 h-12 bg-[#35F28A] border-[3px] border-black brutalist-shadow-chip flex items-center justify-center">
              <Check className="w-7 h-7 text-black stroke-[3]" />
            </div>
            <div className="space-y-1">
              <span className="font-heading text-2xl text-black block">
                CLEAN PIPELINE. NO DEAD LETTERS.
              </span>
              <p className="font-mono text-sm text-[#333333] max-w-md">
                The transactional outbox background worker has processed and persisted all feedback events cleanly with zero dead-letter migrations.
              </p>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
