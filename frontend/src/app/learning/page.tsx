"use client";

import { useEffect, useState } from "react";
import { fetchStats, fetchHistory, PosteriorArmStat, HistoryPoint } from "@/lib/api";
import { RefreshCw, Sparkles, AlertCircle } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";

const CATEGORIES = ["code", "math", "summarize", "chat", "high_stakes"];
const TIERS = ["small", "medium", "large"] as const;

export default function LearningPage() {
  const [stats, setStats] = useState<PosteriorArmStat[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [hoveredArm, setHoveredArm] = useState<PosteriorArmStat | null>(null);

  const loadData = async () => {
    setLoading(true);
    try {
      const statsRes = await fetchStats();
      setStats(statsRes.posteriors);

      const histRes = await fetchHistory(500);
      setHistory(histRes.history);
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const getArmStat = (cat: string, tier: string): PosteriorArmStat | undefined => {
    return stats.find((s) => s.category === cat && s.tier === tier);
  };

  // Format line chart data from history
  const historyChartData = history.map((item, idx) => ({
    index: idx + 1,
    time: new Date(item.ts * 1000).toLocaleTimeString(),
    [`${item.category}_${item.tier}`]: Number(item.mean.toFixed(3)),
  }));

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl sm:text-5xl font-heading text-white tracking-wide">
            Posterior Heatmap & Belief Evolution
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Dynamic Bayesian Beta posteriors updated via Thompson sampling feedback and time decay.
          </p>
        </div>
        <button
          onClick={loadData}
          disabled={loading}
          className="flex items-center space-x-2 px-3 py-1.5 bg-[#1A1A1A] border border-[#262626] rounded-lg text-xs font-mono text-gray-300 hover:text-white hover:border-[#3DFF6B] transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Heatmap Grid */}
      <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
        <h2 className="text-xs uppercase font-mono text-gray-400 mb-4 tracking-wider">
          Category x Tier Posterior Heatmap (Mean Expectation E[θ])
        </h2>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr className="border-b border-[#262626] text-xs font-mono text-gray-400">
                <th className="py-2.5 px-4">Category</th>
                <th className="py-2.5 px-4 text-center">Small Tier</th>
                <th className="py-2.5 px-4 text-center">Medium Tier</th>
                <th className="py-2.5 px-4 text-center">Large Tier</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[#262626]">
              {CATEGORIES.map((cat) => (
                <tr key={cat} className="hover:bg-[#222222]/50 transition-colors">
                  <td className="py-3 px-4 font-mono text-sm capitalize font-medium text-gray-200">
                    {cat.replace("_", " ")}
                    {cat === "high_stakes" && (
                      <span className="ml-2 text-[10px] px-1.5 py-0.5 rounded bg-purple-950 text-purple-400 border border-purple-800">
                        Immutable
                      </span>
                    )}
                  </td>
                  {TIERS.map((tier) => {
                    const arm = getArmStat(cat, tier);
                    if (!arm) return <td key={tier} className="text-center text-gray-600">-</td>;

                    // Color gradient based on mean (0.0 red -> 0.5 neutral -> 1.0 green)
                    const meanVal = arm.mean;
                    const greenIntensity = Math.min(255, Math.floor(meanVal * 255));
                    const redIntensity = Math.min(255, Math.floor((1 - meanVal) * 255));

                    return (
                      <td
                        key={tier}
                        onMouseEnter={() => setHoveredArm(arm)}
                        className="py-3 px-4 text-center cursor-pointer relative group"
                      >
                        <div
                          className="inline-flex flex-col items-center justify-center px-4 py-2 rounded-lg border border-[#333333] transition-all hover:border-[#3DFF6B]"
                          style={{
                            backgroundColor: `rgba(${redIntensity}, ${greenIntensity}, 100, 0.12)`,
                          }}
                        >
                          <span className="text-base font-semibold font-mono text-white">
                            {(arm.mean * 100).toFixed(1)}%
                          </span>
                          <span className="text-[10px] text-gray-400 font-mono mt-0.5">
                            α={arm.alpha.toFixed(1)} β={arm.beta.toFixed(1)}
                          </span>

                          {arm.cold_start && (
                            <span className="mt-1 flex items-center space-x-1 text-[9px] font-mono px-1.5 py-0.2 rounded bg-amber-950/80 border border-amber-600 text-amber-300">
                              <AlertCircle className="w-2.5 h-2.5" />
                              <span>Cold start</span>
                            </span>
                          )}
                        </div>
                      </td>
                    );
                  })}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Hover Inspector for 90% Credible Interval */}
        <div className="mt-4 p-3 bg-[#111111] border border-[#262626] rounded-lg flex items-center justify-between text-xs font-mono">
          {hoveredArm ? (
            <div className="flex flex-wrap items-center gap-4 text-gray-300">
              <span className="text-[#3DFF6B] font-semibold uppercase">
                {hoveredArm.category} / {hoveredArm.tier}
              </span>
              <span>Posterior Mean: {(hoveredArm.mean * 100).toFixed(2)}%</span>
              <span>
                90% Credible Interval: [{(hoveredArm.ci90[0] * 100).toFixed(1)}%, {(hoveredArm.ci90[1] * 100).toFixed(1)}%]
              </span>
              <span>Evidence (α+β-2): {hoveredArm.evidence.toFixed(2)}</span>
            </div>
          ) : (
            <span className="text-gray-500">Hover over any heatmap arm to inspect its 90% Bayesian Credible Interval</span>
          )}
        </div>
      </div>

      {/* History Time Series Chart */}
      <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
        <h2 className="text-xs uppercase font-mono text-gray-400 mb-4 tracking-wider">
          Posterior Mean History Over Time
        </h2>
        {history.length > 0 ? (
          <div className="h-72 w-full">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={historyChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
                <XAxis dataKey="index" stroke="#666666" tick={{ fill: "#888888", fontSize: 10 }} />
                <YAxis domain={[0, 1]} stroke="#666666" tick={{ fill: "#888888", fontSize: 10 }} />
                <Tooltip
                  contentStyle={{ backgroundColor: "#111111", border: "1px solid #333333", fontSize: "12px" }}
                />
                <Legend wrapperStyle={{ fontSize: "11px", paddingTop: "10px" }} />
                <Line type="monotone" dataKey="code_small" stroke="#3DFF6B" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="code_medium" stroke="#eab308" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="code_large" stroke="#A855F7" dot={false} strokeWidth={2} />
                <Line type="monotone" dataKey="math_small" stroke="#38bdf8" dot={false} strokeWidth={1.5} />
                <Line type="monotone" dataKey="math_medium" stroke="#f97316" dot={false} strokeWidth={1.5} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="h-64 flex items-center justify-center text-gray-500 font-mono text-sm">
            No history points recorded yet. Submit prompts and feedback in Playground to observe updates.
          </div>
        )}
      </div>
    </div>
  );
}
