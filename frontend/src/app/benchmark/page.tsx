"use client";

import { useState } from "react";
import { runBenchmarkReplay, BenchmarkResult } from "@/lib/api";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
  LabelList,
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
    <div className="space-y-8">
      {/* Top Controls */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl sm:text-6xl text-black uppercase tracking-tight leading-none">
            PROVE IT
          </h1>
          <p className="font-mono text-sm sm:text-base text-black mt-2 font-medium">
            Empirical evaluation across 10 random seeds on held-out test data (70/30 train/test split).
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          {/* Simulated Mode Button */}
          <button
            onClick={() => handleRun("simulated")}
            disabled={loading}
            aria-label="Run simulated benchmark mode"
            className="px-5 py-3 bg-white text-black font-heading text-sm uppercase border-[3px] border-black brutalist-shadow-button brutalist-button-press transition-all flex items-center space-x-2 cursor-pointer disabled:opacity-50"
          >
            {loading && activeMode === "simulated" ? (
              <div className="brutalist-spinner" />
            ) : (
              <span className="w-3 h-3 bg-black inline-block" />
            )}
            <span>RUN SIMULATED MODE</span>
          </button>

          {/* Real Mode Button */}
          <button
            onClick={() => handleRun("real")}
            disabled={loading}
            aria-label="Run real benchmark mode with 200 prompts"
            className="px-5 py-3 bg-[#FF4FA3] text-black font-heading text-sm uppercase border-[3px] border-black brutalist-shadow-button brutalist-button-press transition-all flex items-center space-x-2 cursor-pointer disabled:opacity-50 relative"
          >
            {loading && activeMode === "real" ? (
              <div className="brutalist-spinner" />
            ) : (
              <span className="w-3 h-3 bg-black inline-block" />
            )}
            <span>RUN REAL MODE</span>
            <span className="px-2 py-0.5 bg-white text-black font-heading text-[10px] uppercase border-2 border-black -rotate-2 ml-1">
              200 PROMPTS
            </span>
          </button>
        </div>
      </div>

      {/* Error Box */}
      {error && (
        <div className="p-4 bg-[#FF3B30] border-[3px] border-black brutalist-shadow text-black font-mono font-bold text-sm">
          ERROR: {error}
        </div>
      )}

      {/* Loading State */}
      {loading && (
        <div className="bg-white border-[3px] border-black brutalist-shadow p-10 flex flex-col items-center justify-center text-center space-y-4">
          <div className="brutalist-spinner scale-150" />
          <div className="space-y-1">
            <h3 className="font-heading text-2xl text-black uppercase">
              EXECUTING {activeMode.toUpperCase()} BENCHMARK...
            </h3>
            <p className="font-mono text-sm text-[#333333]">
              Running 10-seed cross validation over train/test splits. Computing quality expectation and counterfactual cost.
            </p>
          </div>
        </div>
      )}

      {/* Results Section */}
      {!loading && result && (
        <div className="space-y-8">
          {/* Results Table */}
          <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
              <div>
                <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
                  BENCHMARK RESULTS (MODE: {result.mode.toUpperCase()} // SEEDS: {result.seeds})
                </h2>
                <div className="h-1 w-24 bg-black mt-1" />
              </div>

              <span className="font-mono text-xs font-bold text-[#333333] px-3 py-1 bg-white border-2 border-black">
                Held-out 30% test set (Train: {result.train_size} | Test: {result.test_size})
              </span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b-[4px] border-black">
                    <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                      ROUTING STRATEGY
                    </th>
                    <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                      QUALITY (MEAN ± STD)
                    </th>
                    <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                      TEST SET COST (USD)
                    </th>
                    <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                      COST SAVED VS LARGE (%)
                    </th>
                  </tr>
                </thead>
                <tbody className="divide-y-[3px] divide-black font-mono text-sm">
                  {Object.entries(result.strategies).map(([strat, metrics]) => {
                    const isRouter = strat === "router";
                    return (
                      <tr
                        key={strat}
                        className={
                          isRouter
                            ? "bg-[#FF4FA3] font-bold text-black"
                            : "bg-white hover:bg-[#FFF8CC] text-black transition-colors"
                        }
                      >
                        <td className="p-3 border-[3px] border-black align-middle font-heading text-base uppercase">
                          <div className="flex items-center space-x-2">
                            <span>{strat.replace("_", " ")}</span>
                            {isRouter && (
                              <span className="px-2 py-0.5 bg-white text-black font-heading text-xs uppercase border-2 border-black brutalist-shadow-chip -rotate-1">
                                OUR SYSTEM
                              </span>
                            )}
                          </div>
                        </td>
                        <td className="p-3 border-[3px] border-black align-middle font-bold">
                          {(metrics.mean_quality * 100).toFixed(1)}% ± {(metrics.std_quality * 100).toFixed(1)}%
                        </td>
                        <td className="p-3 border-[3px] border-black align-middle font-bold">
                          ${metrics.mean_cost.toFixed(4)} ± ${metrics.std_cost.toFixed(4)}
                        </td>
                        <td className="p-3 border-[3px] border-black align-middle font-bold">
                          <span
                            className={
                              isRouter
                                ? "text-black underline decoration-4"
                                : metrics.mean_cost_saved_pct > 50
                                ? "text-black"
                                : "text-[#333333]"
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
          </div>

          {/* Trade-Off Chart */}
          <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-4">
            <div>
              <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
                STRATEGY TRADE-OFF: QUALITY (%) VS COST SAVED (%)
              </h2>
              <div className="h-1 w-24 bg-black mt-1" />
            </div>

            <div className="h-80 w-full pt-4">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} margin={{ top: 20, right: 30, left: 10, bottom: 20 }}>
                  <CartesianGrid stroke="#000000" strokeWidth={1} strokeDasharray="4 4" />
                  <XAxis
                    dataKey="name"
                    stroke="#000000"
                    strokeWidth={3}
                    tick={{ fill: "#000000", fontSize: 12, fontFamily: "Space Mono", fontWeight: "bold" }}
                  />
                  <YAxis
                    stroke="#000000"
                    strokeWidth={3}
                    domain={[0, 100]}
                    tick={{ fill: "#000000", fontSize: 12, fontFamily: "Space Mono", fontWeight: "bold" }}
                    unit="%"
                  />
                  <Tooltip
                    contentStyle={{
                      backgroundColor: "#FFFFFF",
                      border: "3px solid #000000",
                      boxShadow: "4px 4px 0px #000",
                      borderRadius: 0,
                      fontFamily: "Space Mono",
                      fontWeight: "bold",
                      color: "#000000",
                    }}
                  />
                  <Legend
                    wrapperStyle={{
                      fontFamily: "Space Mono",
                      fontWeight: "bold",
                      fontSize: "12px",
                      paddingTop: "15px",
                    }}
                  />
                  <Bar
                    dataKey="quality"
                    name="Response Quality (%)"
                    fill="#B388FF"
                    stroke="#000000"
                    strokeWidth={3}
                  >
                    <LabelList
                      dataKey="quality"
                      position="top"
                      formatter={(v: any) => `${v}%`}
                      style={{ fontFamily: "Space Mono", fontSize: 11, fontWeight: "bold", fill: "#000" }}
                    />
                  </Bar>
                  <Bar
                    dataKey="cost_saved"
                    name="Cost Saved (%)"
                    fill="#35F28A"
                    stroke="#000000"
                    strokeWidth={3}
                  >
                    <LabelList
                      dataKey="cost_saved"
                      position="top"
                      formatter={(v: any) => `${v}%`}
                      style={{ fontFamily: "Space Mono", fontSize: 11, fontWeight: "bold", fill: "#000" }}
                    />
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>
        </div>
      )}

      {/* Empty State when no benchmark run yet */}
      {!loading && !result && (
        <div className="bg-white border-[3px] border-dashed border-black p-12 text-center space-y-4">
          <span className="font-heading text-3xl text-black uppercase block">
            NO BENCHMARK EXECUTED YET
          </span>
          <p className="font-mono text-sm text-[#333333] max-w-lg mx-auto">
            Click &quot;RUN REAL MODE&quot; or &quot;RUN SIMULATED MODE&quot; above to execute 10-seed cross validation on the 200 curated prompts across all 5 strategies.
          </p>
        </div>
      )}

      {/* Honesty Note Card */}
      <div className="bg-white border-[3px] border-dashed border-black brutalist-shadow p-5">
        <span className="font-heading text-xs uppercase text-black block mb-1">
          METHODOLOGY & BENCHMARK INTEGRITY
        </span>
        <p className="font-mono text-xs sm:text-sm text-black font-bold">
          Held-out 30% split, 10 seeds. Simulated mode proves the mechanism, not production performance. Real mode executes deterministic LLM grading against the full 200-prompt evaluation dataset.
        </p>
      </div>
    </div>
  );
}
