"use client";

import { useEffect, useState } from "react";
import { fetchStats, fetchHistory, PosteriorArmStat, HistoryPoint } from "@/lib/api";
import { Lock, AlertCircle } from "lucide-react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
} from "recharts";

const CATEGORIES = ["code", "math", "summarize", "chat", "high_stakes"] as const;
const TIERS = [
  { id: "small", label: "SMALL TIER", color: "#35F28A" },
  { id: "medium", label: "MEDIUM TIER", color: "#FF9F1C" },
  { id: "large", label: "LARGE TIER", color: "#B388FF" },
] as const;

export default function LearningPage() {
  const [stats, setStats] = useState<PosteriorArmStat[]>([]);
  const [history, setHistory] = useState<HistoryPoint[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedArm, setSelectedArm] = useState<PosteriorArmStat | null>(null);
  const [activeCategory, setActiveCategory] = useState<string>("code");

  const loadData = async () => {
    setLoading(true);
    try {
      const statsRes = await fetchStats();
      setStats(statsRes.posteriors);

      // Select default arm if none selected
      if (!selectedArm && statsRes.posteriors.length > 0) {
        const defaultArm =
          statsRes.posteriors.find((s) => s.category === "code" && s.tier === "medium") ||
          statsRes.posteriors[0];
        setSelectedArm(defaultArm);
      }

      const histRes = await fetchHistory(500);
      setHistory(histRes.history);
    } catch (err) {
      console.error("Failed to load learning data:", err);
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

  // 5 discrete steps background: 0-20%, 20-40%, 40-60%, 60-80%, 80-100%
  const getStepBg = (mean: number, isHighStakes: boolean) => {
    if (isHighStakes) return "bg-[#B388FF] diagonal-hatch-light";
    if (mean < 0.2) return "bg-[#FFFFFF]";
    if (mean < 0.4) return "bg-[#E8FCEF]";
    if (mean < 0.6) return "bg-[#B7F9D1]";
    if (mean < 0.8) return "bg-[#76F6AC]";
    return "bg-[#35F28A]";
  };

  // Chart data for selected category
  const categoryHistory = history.filter((h) => h.category === activeCategory);
  const chartData = categoryHistory.map((item, idx) => ({
    index: idx + 1,
    time: new Date(item.ts * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" }),
    tier: item.tier,
    mean: Number((item.mean * 100).toFixed(1)),
    small: item.tier === "small" ? Number((item.mean * 100).toFixed(1)) : undefined,
    medium: item.tier === "medium" ? Number((item.mean * 100).toFixed(1)) : undefined,
    large: item.tier === "large" ? Number((item.mean * 100).toFixed(1)) : undefined,
  }));

  // Build sequential series for the 3 tiers
  const smallSeries = history
    .filter((h) => h.category === activeCategory && h.tier === "small")
    .map((h, i) => ({ i: i + 1, mean: Number((h.mean * 100).toFixed(1)) }));
  const mediumSeries = history
    .filter((h) => h.category === activeCategory && h.tier === "medium")
    .map((h, i) => ({ i: i + 1, mean: Number((h.mean * 100).toFixed(1)) }));
  const largeSeries = history
    .filter((h) => h.category === activeCategory && h.tier === "large")
    .map((h, i) => ({ i: i + 1, mean: Number((h.mean * 100).toFixed(1)) }));

  const maxPoints = Math.max(smallSeries.length, mediumSeries.length, largeSeries.length, 1);
  const alignedChartData = Array.from({ length: maxPoints }).map((_, idx) => ({
    step: idx + 1,
    small: smallSeries[idx]?.mean,
    medium: mediumSeries[idx]?.mean,
    large: largeSeries[idx]?.mean,
  }));

  return (
    <div className="space-y-8">
      {/* Top Controls */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl sm:text-6xl text-black uppercase tracking-tight leading-none">
            WHAT RELAY LEARNED
          </h1>
          <p className="font-mono text-sm sm:text-base text-black mt-2 font-medium">
            Dynamic Bayesian Beta posteriors updated via Thompson sampling feedback and time decay.
          </p>
        </div>

        <button
          onClick={loadData}
          disabled={loading}
          aria-label="Refresh posterior stats"
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

      {/* Heatmap Matrix Card */}
      <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6">
        <div className="mb-6">
          <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
            POSTERIOR HEATMAP MATRIX (5 CATEGORIES × 3 TIERS)
          </h2>
          <div className="h-1 w-24 bg-black mt-1" />
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse">
            <thead>
              <tr>
                <th className="p-3 font-heading text-sm text-black uppercase border-[3px] border-black bg-white">
                  CATEGORY
                </th>
                {TIERS.map((tier) => (
                  <th
                    key={tier.id}
                    className="p-3 text-center border-[3px] border-black"
                    style={{ backgroundColor: tier.color }}
                  >
                    <span className="font-heading text-sm uppercase text-black inline-block -rotate-1">
                      {tier.label}
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {CATEGORIES.map((cat) => {
                const isHighStakes = cat === "high_stakes";
                return (
                  <tr key={cat}>
                    <td className="p-4 border-[3px] border-black bg-white font-heading text-base text-black uppercase align-middle">
                      <div className="flex items-center space-x-2">
                        <span>{cat.replace("_", " ")}</span>
                        {isHighStakes && (
                          <span className="bg-black text-white px-2 py-0.5 font-heading text-xs uppercase flex items-center space-x-1">
                            <Lock className="w-3 h-3 stroke-[3]" />
                            <span>IMMUTABLE</span>
                          </span>
                        )}
                      </div>
                    </td>

                    {TIERS.map((tier) => {
                      const arm = getArmStat(cat, tier.id);
                      if (!arm) {
                        return (
                          <td
                            key={tier.id}
                            className="p-3 text-center border-[3px] border-black bg-white font-mono text-sm"
                          >
                            -
                          </td>
                        );
                      }

                      const isSelected =
                        selectedArm?.category === cat && selectedArm?.tier === tier.id;
                      const cellBg = getStepBg(arm.mean, isHighStakes);

                      return (
                        <td key={tier.id} className="p-2 border-[3px] border-black bg-white">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedArm(arm);
                              setActiveCategory(cat);
                            }}
                            onMouseEnter={() => setSelectedArm(arm)}
                            aria-label={`${cat.replace("_", " ")}, ${tier.label}, mean ${(arm.mean * 100).toFixed(1)} percent`}
                            title={
                              isHighStakes
                                ? "never learns, always routes to Large"
                                : `${cat.replace("_", " ")} / ${tier.id}: ${(arm.mean * 100).toFixed(1)}%`
                            }
                            className={`w-full p-3 border-[3px] border-black transition-all flex flex-col items-center justify-center text-center cursor-pointer ${cellBg} ${
                              isSelected
                                ? "ring-4 ring-black scale-[0.98] brutalist-shadow-sm"
                                : "hover:-translate-y-0.5 hover:-translate-x-0.5 hover:shadow-[4px_4px_0px_#000]"
                            }`}
                          >
                            <span className="font-heading text-2xl sm:text-3xl text-black leading-none">
                              {(arm.mean * 100).toFixed(1)}%
                            </span>

                            <span className="font-mono text-xs text-black font-bold mt-1">
                              α={arm.alpha.toFixed(1)} β={arm.beta.toFixed(1)}
                            </span>

                            {arm.cold_start && !isHighStakes && (
                              <span className="mt-1.5 px-2 py-0.5 bg-[#FF9F1C] text-black font-mono font-bold text-[10px] uppercase border-2 border-black brutalist-shadow-chip -rotate-1">
                                COLD START
                              </span>
                            )}

                            {isHighStakes && (
                              <span className="mt-1.5 px-2 py-0.5 bg-black text-white font-heading text-[10px] uppercase flex items-center space-x-1">
                                <Lock className="w-2.5 h-2.5" />
                                <span>LOCKED</span>
                              </span>
                            )}
                          </button>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* Credible Interval Inspector */}
      {selectedArm ? (
        <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-4">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2 border-b-[3px] border-black pb-3">
            <div>
              <span className="font-mono text-xs uppercase font-bold text-[#333333]">
                ARM INSPECTOR
              </span>
              <h3 className="font-heading text-2xl sm:text-3xl text-black uppercase">
                {selectedArm.category.replace("_", " ")} // {selectedArm.tier}
              </h3>
            </div>

            <div className="flex items-center space-x-3">
              <span className="font-mono text-xs font-bold px-3 py-1 bg-white border-2 border-black brutalist-shadow-chip">
                Decay: 0.98^days (half-life ≈ 34.3 days)
              </span>
            </div>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <div className="p-3 bg-[#FFE14D] border-[3px] border-black">
              <span className="font-mono text-xs font-bold uppercase text-black block">
                POSTERIOR MEAN E[θ]
              </span>
              <span className="font-heading text-3xl sm:text-4xl text-black">
                {(selectedArm.mean * 100).toFixed(2)}%
              </span>
            </div>

            <div className="p-3 bg-white border-[3px] border-black">
              <span className="font-mono text-xs font-bold uppercase text-black block">
                90% CREDIBLE INTERVAL
              </span>
              <span className="font-mono text-2xl sm:text-3xl font-bold text-black">
                [{(selectedArm.ci90[0] * 100).toFixed(1)}%, {(selectedArm.ci90[1] * 100).toFixed(1)}%]
              </span>
            </div>

            <div className="p-3 bg-white border-[3px] border-black">
              <span className="font-mono text-xs font-bold uppercase text-black block">
                EVIDENCE COUNT & PARAMETERS
              </span>
              <span className="font-mono text-base font-bold text-black mt-1 block">
                α = {selectedArm.alpha.toFixed(2)} | β = {selectedArm.beta.toFixed(2)}
              </span>
              <span className="font-mono text-xs text-[#333333]">
                Total Evidence (α+β−2) = {selectedArm.evidence.toFixed(2)}
              </span>
            </div>
          </div>

          {/* Visual 90% Credible Interval Bar */}
          <div className="pt-2">
            <span className="font-mono text-xs font-bold uppercase text-black block mb-2">
              BAYESIAN 90% CREDIBLE INTERVAL VISUALIZATION
            </span>

            <div className="w-full h-10 bg-white border-[3px] border-black relative overflow-hidden">
              {/* Range bar from ci90[0] to ci90[1] */}
              <div
                className="absolute top-0 bottom-0 border-l-[3px] border-r-[3px] border-black"
                style={{
                  left: `${Math.max(0, selectedArm.ci90[0] * 100)}%`,
                  width: `${Math.max(2, (selectedArm.ci90[1] - selectedArm.ci90[0]) * 100)}%`,
                  backgroundColor:
                    selectedArm.category === "high_stakes" ? "#B388FF" : "#35F28A",
                }}
              />

              {/* Mean marker triangle */}
              <div
                className="absolute top-0 -translate-x-1/2 flex flex-col items-center z-10"
                style={{ left: `${selectedArm.mean * 100}%` }}
              >
                <div className="w-0 h-0 border-l-[6px] border-l-transparent border-r-[6px] border-r-transparent border-t-[8px] border-t-black" />
                <div className="w-[3px] h-6 bg-black" />
              </div>
            </div>

            <div className="flex justify-between font-mono text-xs text-black font-bold mt-1.5">
              <span>0%</span>
              <span>CI Lower: {(selectedArm.ci90[0] * 100).toFixed(1)}%</span>
              <span className="font-heading">MEAN: {(selectedArm.mean * 100).toFixed(1)}%</span>
              <span>CI Upper: {(selectedArm.ci90[1] * 100).toFixed(1)}%</span>
              <span>100%</span>
            </div>
          </div>
        </div>
      ) : null}

      {/* History Evolution Line Chart */}
      <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
              POSTERIOR MEAN EVOLUTION OVER TIME
            </h2>
            <div className="h-1 w-24 bg-black mt-1" />
          </div>

          {/* Category Filter Badges */}
          <div className="flex flex-wrap gap-2">
            {CATEGORIES.map((cat) => {
              const active = activeCategory === cat;
              return (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`px-3 py-1 font-mono text-xs uppercase font-bold border-2 border-black transition-all ${
                    active
                      ? "bg-[#FF4FA3] text-black brutalist-shadow-chip translate-x-[-1px] translate-y-[-1px]"
                      : "bg-white text-black hover:bg-[#FFF8CC]"
                  }`}
                >
                  {cat.replace("_", " ")}
                </button>
              );
            })}
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 pt-2">
          {TIERS.map((tier) => (
            <div
              key={tier.id}
              className="flex items-center space-x-2 px-3 py-1 border-2 border-black font-mono text-xs uppercase font-bold"
              style={{ backgroundColor: tier.color }}
            >
              <span className="w-3 h-3 bg-black border border-black inline-block" />
              <span>{tier.label}</span>
            </div>
          ))}
        </div>

        {alignedChartData.length > 0 && alignedChartData.some((d) => d.small || d.medium || d.large) ? (
          <div className="h-72 w-full pt-4">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={alignedChartData}>
                <CartesianGrid stroke="#000000" strokeWidth={1} strokeDasharray="4 4" />
                <XAxis
                  dataKey="step"
                  stroke="#000000"
                  strokeWidth={3}
                  tick={{ fill: "#000000", fontSize: 12, fontFamily: "Space Mono", fontWeight: "bold" }}
                />
                <YAxis
                  domain={[0, 100]}
                  stroke="#000000"
                  strokeWidth={3}
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
                <Line
                  type="monotone"
                  dataKey="small"
                  name="Small Tier"
                  stroke="#35F28A"
                  strokeWidth={3}
                  dot={{ r: 4, stroke: "#000000", strokeWidth: 2, fill: "#35F28A" }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="medium"
                  name="Medium Tier"
                  stroke="#FF9F1C"
                  strokeWidth={3}
                  dot={{ r: 4, stroke: "#000000", strokeWidth: 2, fill: "#FF9F1C" }}
                  connectNulls
                />
                <Line
                  type="monotone"
                  dataKey="large"
                  name="Large Tier"
                  stroke="#B388FF"
                  strokeWidth={3}
                  dot={{ r: 4, stroke: "#000000", strokeWidth: 2, fill: "#B388FF" }}
                  connectNulls
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        ) : (
          <div className="p-10 border-[3px] border-dashed border-black bg-white text-center space-y-2">
            <span className="font-heading text-2xl text-black block">NOTHING YET.</span>
            <p className="font-mono text-sm text-[#333333]">
              No posterior updates logged for category &quot;{activeCategory}&quot;. Send prompts in the Playground to see history lines evolve.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
