"use client";

import { useEffect, useState } from "react";
import { fetchMetrics, SystemMetricsResponse } from "@/lib/api";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
  LabelList,
} from "recharts";

export default function CostPage() {
  const [metrics, setMetrics] = useState<SystemMetricsResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadMetrics = async () => {
    setLoading(true);
    try {
      const data = await fetchMetrics();
      setMetrics(data);
    } catch (err) {
      console.error("Failed to load metrics:", err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMetrics();
  }, []);

  const totalActual = metrics?.total_cost || 0.0;
  const estimatedSavings = metrics?.estimated_savings_vs_always_large || 0.0;
  const alwaysLargeCounterfactual = totalActual + estimatedSavings;
  const savingsPct =
    alwaysLargeCounterfactual > 0
      ? (estimatedSavings / alwaysLargeCounterfactual) * 100.0
      : 0.0;

  const comparisonData = [
    {
      name: "Relay (Actual)",
      cost: Number(totalActual.toFixed(6)),
      label: `$${totalActual.toFixed(5)}`,
      fill: "#35F28A",
    },
    {
      name: "Always Large",
      cost: Number(alwaysLargeCounterfactual.toFixed(6)),
      label: `$${alwaysLargeCounterfactual.toFixed(5)}`,
      fill: "#B388FF",
    },
  ];

  return (
    <div className="space-y-8">
      {/* Top Controls */}
      <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4">
        <div>
          <h1 className="font-heading text-4xl sm:text-6xl text-black uppercase tracking-tight leading-none">
            WHERE THE MONEY WENT
          </h1>
          <p className="font-mono text-sm sm:text-base text-black mt-2 font-medium">
            Realized LLM cost efficiency comparing Relay routing decisions against always-large baseline.
          </p>
        </div>

        <button
          onClick={loadMetrics}
          disabled={loading}
          aria-label="Refresh cost metrics"
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

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {/* Actual Relay Spend */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#35F28A] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              ACTUAL RELAY SPEND
            </span>
            <div className="my-3">
              <span className="font-heading text-3xl sm:text-4xl text-black block truncate">
                ${totalActual.toFixed(5)}
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Across {metrics?.total_requests || 0} routed requests
            </span>
          </div>
        </div>

        {/* Always Large Spend */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#B388FF] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              ALWAYS LARGE SPEND
            </span>
            <div className="my-3">
              <span className="font-heading text-3xl sm:text-4xl text-black block truncate">
                ${alwaysLargeCounterfactual.toFixed(5)}
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Exclusively Gemini 2.5 Pro
            </span>
          </div>
        </div>

        {/* Net Dollar Savings */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden">
          <div className="h-3 w-full bg-[#FF4FA3] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
              NET DOLLAR SAVINGS
            </span>
            <div className="my-3">
              <span className="font-heading text-3xl sm:text-4xl text-black block truncate">
                ${estimatedSavings.toFixed(5)}
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Dollars saved via tier optimization
            </span>
          </div>
        </div>

        {/* Cost Reduction % */}
        <div className="bg-white border-[3px] border-black brutalist-shadow flex flex-col justify-between overflow-hidden relative">
          <div className="h-3 w-full bg-[#FF9F1C] border-b-[3px] border-black" />
          <div className="p-5 flex-1 flex flex-col justify-between">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs uppercase font-bold text-black tracking-wider block">
                COST REDUCTION %
              </span>
              <span className="px-2 py-0.5 bg-[#FF9F1C] text-black font-heading text-[10px] uppercase border-2 border-black brutalist-shadow-chip -rotate-2">
                SAVINGS
              </span>
            </div>
            <div className="my-3">
              <span className="font-heading text-3xl sm:text-4xl text-black block">
                {savingsPct.toFixed(1)}%
              </span>
            </div>
            <span className="font-mono text-xs text-[#333333] font-medium block">
              Relative expenditure drop
            </span>
          </div>
        </div>
      </div>

      {/* Comparison Bar Chart */}
      <div className="bg-white border-[3px] border-black brutalist-shadow p-5 sm:p-6 space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h2 className="font-heading text-xl sm:text-2xl text-black uppercase">
              CUMULATIVE SPEND COMPARISON (USD)
            </h2>
            <div className="h-1 w-24 bg-black mt-1" />
          </div>

          {savingsPct > 0 && (
            <div className="px-4 py-2 bg-[#35F28A] text-black font-heading text-sm uppercase border-[3px] border-black brutalist-shadow-chip -rotate-2 inline-block">
              YOU SAVED {savingsPct.toFixed(1)}%!
            </div>
          )}
        </div>

        <div className="h-80 w-full pt-4">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart
              data={comparisonData}
              layout="vertical"
              margin={{ top: 20, right: 80, left: 20, bottom: 20 }}
            >
              <CartesianGrid stroke="#000000" strokeWidth={1} strokeDasharray="4 4" />
              <XAxis
                type="number"
                stroke="#000000"
                strokeWidth={3}
                tick={{ fill: "#000000", fontSize: 12, fontFamily: "Space Mono", fontWeight: "bold" }}
                tickFormatter={(val) => `$${val}`}
              />
              <YAxis
                dataKey="name"
                type="category"
                stroke="#000000"
                strokeWidth={3}
                tick={{ fill: "#000000", fontSize: 13, fontFamily: "Archivo Black" }}
                width={150}
              />
              <Tooltip
                formatter={(val: any) => [`$${Number(val).toFixed(6)}`, "Cost"]}
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
              <Bar dataKey="cost" stroke="#000000" strokeWidth={3}>
                <LabelList
                  dataKey="label"
                  position="right"
                  style={{
                    fontFamily: "Space Mono",
                    fontWeight: "bold",
                    fontSize: 13,
                    fill: "#000000",
                  }}
                />
                {comparisonData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap gap-4 pt-2 border-t-[3px] border-black">
          <div className="flex items-center space-x-2 px-3 py-1 bg-[#35F28A] border-2 border-black font-mono text-xs uppercase font-bold text-black">
            <span className="w-3 h-3 bg-black inline-block" />
            <span>RELAY ACTUAL (OPTIMIZED)</span>
          </div>
          <div className="flex items-center space-x-2 px-3 py-1 bg-[#B388FF] border-2 border-black font-mono text-xs uppercase font-bold text-black">
            <span className="w-3 h-3 bg-black inline-block" />
            <span>ALWAYS LARGE (COUNTERFACTUAL)</span>
          </div>
        </div>
      </div>
    </div>
  );
}
