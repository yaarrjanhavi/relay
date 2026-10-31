"use client";

import { useEffect, useState } from "react";
import { fetchMetrics, SystemMetricsResponse } from "@/lib/api";
import { DollarSign, TrendingDown, PiggyBank, RefreshCw } from "lucide-react";
import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Cell,
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
      console.error(err);
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
    { name: "Relay (Actual)", cost: Number(totalActual.toFixed(6)), fill: "#3DFF6B" },
    { name: "Always Large (Counterfactual)", cost: Number(alwaysLargeCounterfactual.toFixed(6)), fill: "#A855F7" },
  ];

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-4xl sm:text-5xl font-heading text-white tracking-wide">
            Cost & Counterfactual Savings
          </h1>
          <p className="text-gray-400 text-sm mt-1">
            Realized LLM cost efficiency comparing Relay routing decisions against always-large baseline.
          </p>
        </div>
        <button
          onClick={loadMetrics}
          disabled={loading}
          className="flex items-center space-x-2 px-3 py-1.5 bg-[#1A1A1A] border border-[#262626] rounded-lg text-xs font-mono text-gray-300 hover:text-white hover:border-[#3DFF6B] transition-all"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Actual Relay Spend</span>
            <DollarSign className="w-4 h-4 text-[#3DFF6B]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            ${totalActual.toFixed(5)}
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Across {metrics?.total_requests || 0} routed requests
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Always Large Spend</span>
            <DollarSign className="w-4 h-4 text-[#A855F7]" />
          </div>
          <div className="text-2xl font-bold font-mono text-white">
            ${alwaysLargeCounterfactual.toFixed(5)}
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            If routed exclusively to Gemini 2.5 Pro
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Net Dollar Savings</span>
            <PiggyBank className="w-4 h-4 text-[#3DFF6B]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#3DFF6B]">
            ${estimatedSavings.toFixed(5)}
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Dollars saved from tier optimization
          </span>
        </div>

        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
          <div className="flex items-center justify-between text-gray-400 mb-2">
            <span className="text-xs uppercase font-mono">Cost Reduction</span>
            <TrendingDown className="w-4 h-4 text-[#3DFF6B]" />
          </div>
          <div className="text-2xl font-bold font-mono text-[#3DFF6B]">
            {savingsPct.toFixed(1)}%
          </div>
          <span className="text-[11px] text-gray-500 font-mono mt-1 block">
            Relative expenditure reduction
          </span>
        </div>
      </div>

      {/* Comparison Chart */}
      <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5">
        <h2 className="text-xs uppercase font-mono text-gray-400 mb-4 tracking-wider">
          Cumulative Spend Comparison (USD)
        </h2>
        <div className="h-64 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={comparisonData} layout="vertical" margin={{ left: 40, right: 40 }}>
              <CartesianGrid strokeDasharray="3 3" stroke="#262626" />
              <XAxis type="number" stroke="#666666" tick={{ fill: "#888888", fontSize: 11 }} />
              <YAxis dataKey="name" type="category" stroke="#666666" tick={{ fill: "#DDDDDD", fontSize: 12 }} />
              <Tooltip
                formatter={(val: any) => [`$${val.toFixed(6)}`, "Cost"]}
                contentStyle={{ backgroundColor: "#111111", border: "1px solid #333333", fontSize: "12px" }}
              />
              <Bar dataKey="cost" radius={[0, 4, 4, 0]}>
                {comparisonData.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={entry.fill} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
