"use client";

import { useEffect, useState } from "react";
import { fetchMetrics, fetchDeadLetters, SystemMetricsResponse, DeadLetterItem } from "@/lib/api";
import { Activity, Database, AlertOctagon, RefreshCw, Zap, Server } from "lucide-react";

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
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOpsData();
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl sm:text-5xl font-heading text-white tracking-wide">
            Operational Telemetry & Dead Letters
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Real-time infrastructure health: token bucket rate limits, response caching, fallbacks, and dead-letter events.
          </p>
        </div>
        <button
          onClick={loadOpsData}
          disabled={loading}
          className="flex items-center space-x-2 px-3 py-1.5 bg-[#1A1A1A] border border-[#262626] rounded-lg text-xs font-mono text-gray-300 hover:text-white hover:border-[#3DFF6B] transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Metrics Grid */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Cache Hit Ratio</span>
            <Database className="w-4 h-4 text-blue-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {((metrics?.cache_hit_rate || 0) * 100).toFixed(1)}%
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Exact-match 30-min SHA-256 cache
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Rate-Limited Events</span>
            <AlertOctagon className="w-4 h-4 text-amber-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {metrics?.rate_limited_count || 0}
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            HTTP 429 token-bucket throttled requests
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Fallback Escalation</span>
            <Server className="w-4 h-4 text-yellow-400" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {((metrics?.fallback_rate || 0) * 100).toFixed(1)}%
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Small → Medium → Large escalations
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Latency (p50 / p95)</span>
            <Zap className="w-4 h-4 text-[#3DFF6B]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            {metrics?.p50_latency_ms.toFixed(0) || 0} / {metrics?.p95_latency_ms.toFixed(0) || 0} ms
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Non-cached roundtrip latency
          </span>
        </div>
      </div>

      {/* Dead Letter Table */}
      <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-xs uppercase font-mono text-gray-400 tracking-wider">
            Transactional Outbox Dead-Letter Queue ({deadLetters.length} Failed Events)
          </h2>
          <span className="text-[11px] font-mono text-gray-500">
            Events migrated after 5 exponential backoff retry attempts
          </span>
        </div>

        {deadLetters.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse font-mono text-xs">
              <thead>
                <tr className="border-b border-[#262626] text-gray-400">
                  <th className="py-2.5 px-4">Event ID</th>
                  <th className="py-2.5 px-4">Failure Error</th>
                  <th className="py-2.5 px-4">Timestamp</th>
                  <th className="py-2.5 px-4">Payload Summary</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626] text-gray-300">
                {deadLetters.map((dl) => (
                  <tr key={dl.id} className="hover:bg-[#222222]/50">
                    <td className="py-2.5 px-4 text-red-400">{dl.id.slice(0, 8)}...</td>
                    <td className="py-2.5 px-4 text-red-300 max-w-xs truncate">{dl.error}</td>
                    <td className="py-2.5 px-4 text-gray-400">
                      {new Date(dl.created_at * 1000).toLocaleString()}
                    </td>
                    <td className="py-2.5 px-4 text-gray-400 max-w-sm truncate">
                      {typeof dl.payload === "string" ? dl.payload : JSON.stringify(dl.payload)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="p-8 text-center text-gray-500 font-mono text-sm border border-dashed border-[#262626] rounded-lg">
            No dead-letter events recorded. Outbox background worker has processed all feedback events cleanly.
          </div>
        )}
      </div>
    </div>
  );
}
