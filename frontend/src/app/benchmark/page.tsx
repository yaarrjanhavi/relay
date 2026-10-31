"use client";

import { useState } from "react";
import { runBenchmarkReplay, BenchmarkResult } from "@/lib/api";
import { BarChart3, Play, Loader2, Award, Zap, ShieldCheck } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

export default function BenchmarkPage() {
  const [result, setResult] = useState<BenchmarkResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [activeMode, setActiveMode] = useState<"simulated" | "real">("simulated");
  const [error, setError] = useState<string | null>(null);

  const handleRun = async (mode: "simulated" | "real") => {
    setActiveMode(mode);
    setLoading(true);
    setError(null);

    try {
      const data = await runBenchmarkReplay(mode, 10);
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to execute benchmark");
    } finally {
      setLoading(false);
    }
  };

  const chartData = result
    ? Object.entries(result.strategies).map(([strat, metrics]) => ({
        name: strat.replace("_", " ").toUpperCase(),
        quality: Number((metrics.mean_quality * 100).toFixed(1)),
        cost_saved: Number(metrics.mean_cost_saved_pct.toFixed(1)),
      }))
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-4xl sm:text-5xl font-heading text-white tracking-wide">
            Honest Multi-Seed Benchmark
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Empirical evaluation across 10 random seeds on held-out test data (70/30 train/test split).
          </p>
        </div>

        <div className="flex space-x-2">
          <button
            onClick={() => handleRun("simulated")}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-[#1A1A1A] hover:bg-[#222222] border border-[#262626] hover:border-[#3DFF6B] text-white rounded-lg text-xs font-mono transition-all disabled:opacity-50 cursor-pointer"
          >
            {loading && activeMode === "simulated" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin text-[#3DFF6B]" />
            ) : (
              <Play className="w-3.5 h-3.5 text-[#3DFF6B]" />
            )}
            <span>Run Simulated Mode</span>
          </button>

          <button
            onClick={() => handleRun("real")}
            disabled={loading}
            className="flex items-center space-x-2 px-4 py-2 bg-[#3DFF6B] hover:bg-[#34e25e] text-black font-semibold rounded-lg text-xs font-mono transition-all disabled:opacity-50 cursor-pointer"
          >
            {loading && activeMode === "real" ? (
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
            ) : (
              <Award className="w-3.5 h-3.5" />
            )}
            <span>Run Real Mode (200 Prompts)</span>
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 bg-red-950/40 border border-red-800 rounded-lg text-red-300 text-xs font-mono">
          {error}
        </div>
      )}

      {result ? (
        <div className="space-y-6">
          {/* Comparison Table */}
          <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5 overflow-x-auto">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xs uppercase font-mono text-gray-400 tracking-wider">
                Benchmark Results (Mode: {result.mode.toUpperCase()} | Seeds: {result.seeds} | Train: {result.train_size} | Test: {result.test_size})
              </h2>
              <span className="text-[11px] font-mono text-gray-500">
                Metrics evaluated strictly on held-out 30% test set
              </span>
            </div>

            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-[#262626] text-xs font-mono text-gray-400">
                  <th className="py-2.5 px-4">Routing Strategy</th>
                  <th className="py-2.5 px-4">Quality (Mean ± Std)</th>
                  <th className="py-2.5 px-4">Test Set Cost (USD)</th>
                  <th className="py-2.5 px-4">Cost Saved vs Large (%)</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#262626] font-mono text-sm">
                {Object.entries(result.strategies).map(([strat, metrics]) => {
                  const isRouter = strat === "router";
                  return (
                    <tr
                      key={strat}
                      className={isRouter ? "bg-[#3DFF6B]/5 font-semibold text-white" : "hover:bg-[#222222]/50 text-gray-300"}
                    >
                      <td className="py-3 px-4 capitalize flex items-center space-x-2">
                        <span>{strat.replace("_", " ")}</span>
                        {isRouter && (
                          <span className="text-[10px] px-1.5 py-0.5 rounded bg-[#3DFF6B]/20 text-[#3DFF6B] border border-[#3DFF6B]/40">
                            Our System
                          </span>
                        )}
                      </td>
                      <td className="py-3 px-4">
                        {(metrics.mean_quality * 100).toFixed(1)}% ± {(metrics.std_quality * 100).toFixed(1)}%
                      </td>
                      <td className="py-3 px-4">
                        ${metrics.mean_cost.toFixed(4)} ± ${metrics.std_cost.toFixed(4)}
                      </td>
                      <td className="py-3 px-4">
                        <span
                          className={
                            metrics.mean_cost_saved_pct > 50
                              ? "text-[#3DFF6B]"
                              : metrics.mean_cost_saved_pct > 0
                              ? "text-yellow-400"
                              : "text-gray-400"
                          }
                        >
                          {metrics.mean_cost_saved_pct.toFixed(1)}% ± {metrics.std_cost_saved_pct.toFixed(1)}%
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Visualization */}
          <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
            <h2 className="text-xs uppercase font-mono text-gray-400 mb-4 tracking-wider">
              Strategy Trade-off: Quality (%) vs Cost Saved (%)
            </h2>
            <div className="h-72 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 5 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                  <XAxis dataKey="name" stroke="#666666" tick={{ fill: "#DDDDDD", fontSize: 11 }} />
                  <YAxis stroke="#666666" domain={[0, 100]} tick={{ fill: "#888888", fontSize: 11 }} />
                  <Tooltip
                    contentStyle={{ backgroundColor: "#111111", border: "1px solid #333333", fontSize: "12px" }}
                  />
                  <Legend wrapperStyle={{ fontSize: "12px", paddingTop: "10px" }} />
                  <Bar dataKey="quality" name="Response Quality (%)" fill="#A855F7" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="cost_saved" name="Cost Saved (%)" fill="#3DFF6B" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      ) : (
        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-12 flex flex-col items-center justify-center text-center space-y-4">
          <BarChart3 className="w-12 h-12 text-gray-600" />
          <div className="max-w-md">
            <h3 className="text-lg font-semibold text-white">No Benchmark Executed Yet</h3>
            <p className="text-sm text-gray-400 mt-1">
              Click &quot;Run Real Mode&quot; or &quot;Run Simulated Mode&quot; to execute 10-seed cross validation on the held-out 30% test sets.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}
