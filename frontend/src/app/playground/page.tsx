"use client";

import { useState, useEffect, useCallback } from "react";
import { routePrompt, submitFeedback, RouteResponse } from "@/lib/api";
import { ThumbsUp, ThumbsDown, Send, Zap, ShieldCheck, Database, Layers } from "lucide-react";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<"up" | "down" | null>(null);

  const handleRoute = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || loading) return;

    setLoading(true);
    setError(null);
    setFeedbackSent(null);

    try {
      const data = await routePrompt(prompt.trim());
      setResult(data);
    } catch (err: any) {
      setError(err.message || "Failed to route prompt");
    } finally {
      setLoading(false);
    }
  };

  const handleFeedback = useCallback(
    async (thumbsUp: boolean) => {
      if (!result?.request_id || feedbackSent) return;

      try {
        await submitFeedback(result.request_id, thumbsUp);
        setFeedbackSent(thumbsUp ? "up" : "down");
      } catch (err: any) {
        setError(err.message || "Failed to submit feedback");
      }
    },
    [result, feedbackSent]
  );

  // Keyboard shortcuts: U = thumbs up, D = thumbs down
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore when typing inside input/textarea
      const tag = (e.target as HTMLElement)?.tagName?.toLowerCase();
      if (tag === "input" || tag === "textarea") return;

      if (e.key === "u" || e.key === "U") {
        e.preventDefault();
        handleFeedback(true);
      } else if (e.key === "d" || e.key === "D") {
        e.preventDefault();
        handleFeedback(false);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [handleFeedback]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-4xl sm:text-5xl font-heading text-white tracking-wide">
          Interactive Router Playground
        </h1>
        <p className="text-gray-400 text-sm mt-1">
          Send a prompt to test dynamic Thompson Sampling routing across Gemini tiers.
          Keyboard shortcuts: <kbd className="px-1.5 py-0.5 bg-[#262626] rounded text-[#3DFF6B]">U</kbd> thumbs up,{" "}
          <kbd className="px-1.5 py-0.5 bg-[#262626] rounded text-[#3DFF6B]">D</kbd> thumbs down.
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Input Panel */}
        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5 flex flex-col justify-between">
          <form onSubmit={handleRoute} className="flex-1 flex flex-col">
            <label htmlFor="prompt-input" className="text-xs uppercase font-mono text-gray-400 mb-2">
              User Prompt
            </label>
            <textarea
              id="prompt-input"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter your prompt here... (e.g. 'Write a Python binary search function' or 'What is pediatric dosage of amoxicillin?')"
              rows={9}
              className="w-full bg-[#111111] border border-[#262626] rounded-lg p-3 text-sm text-gray-100 placeholder-gray-500 focus:outline-none focus:border-[#3DFF6B] focus:ring-1 focus:ring-[#3DFF6B] transition-all resize-none flex-1"
            />

            <div className="mt-4 flex items-center justify-between">
              <span className="text-xs text-gray-500 font-mono">
                {prompt.length} / 20,000 chars
              </span>
              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className="flex items-center space-x-2 px-5 py-2.5 bg-[#3DFF6B] hover:bg-[#34e25e] text-black font-semibold rounded-lg text-sm transition-all disabled:opacity-50 disabled:cursor-not-allowed cursor-pointer"
              >
                <Send className="w-4 h-4" />
                <span>{loading ? "Routing..." : "Route Prompt"}</span>
              </button>
            </div>
          </form>

          {error && (
            <div className="mt-4 p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-red-300 text-xs font-mono">
              {error}
            </div>
          )}
        </div>

        {/* Results Panel */}
        <div className="bg-[#1A1A1A] border border-[#262626] rounded-xl p-5 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between border-b border-[#262626] pb-3 mb-4">
              <span className="text-xs uppercase font-mono text-gray-400">
                Routing Metadata
              </span>
              {result && (
                <div className="flex items-center space-x-2">
                  {result.category === "high_stakes" && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-mono bg-purple-950/60 border border-[#A855F7] text-[#c084fc]">
                      <ShieldCheck className="w-3 h-3 text-[#A855F7]" />
                      <span>SAFETY LOCK</span>
                    </span>
                  )}
                  {result.cache_hit && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-mono bg-blue-950/60 border border-blue-500 text-blue-300">
                      <Database className="w-3 h-3" />
                      <span>CACHE HIT</span>
                    </span>
                  )}
                  {result.fallback_used && (
                    <span className="flex items-center space-x-1 px-2 py-0.5 rounded text-xs font-mono bg-amber-950/60 border border-amber-500 text-amber-300">
                      <Layers className="w-3 h-3" />
                      <span>FALLBACK ESCALATED</span>
                    </span>
                  )}
                </div>
              )}
            </div>

            {result ? (
              <div className="space-y-4">
                {/* Metric Badges */}
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
                  <div className="bg-[#111111] border border-[#262626] p-2.5 rounded-lg">
                    <span className="text-[10px] font-mono text-gray-400 block uppercase">Category</span>
                    <span className="text-sm font-semibold text-white capitalize">{result.category}</span>
                  </div>
                  <div className="bg-[#111111] border border-[#262626] p-2.5 rounded-lg">
                    <span className="text-[10px] font-mono text-gray-400 block uppercase">Served Tier</span>
                    <span
                      className={`text-sm font-semibold uppercase ${
                        result.tier === "small"
                          ? "text-[#3DFF6B]"
                          : result.tier === "medium"
                          ? "text-yellow-400"
                          : "text-[#A855F7]"
                      }`}
                    >
                      {result.tier}
                    </span>
                  </div>
                  <div className="bg-[#111111] border border-[#262626] p-2.5 rounded-lg">
                    <span className="text-[10px] font-mono text-gray-400 block uppercase">Cost (USD)</span>
                    <span className="text-sm font-mono text-white">${result.cost_usd.toFixed(6)}</span>
                  </div>
                  <div className="bg-[#111111] border border-[#262626] p-2.5 rounded-lg">
                    <span className="text-[10px] font-mono text-gray-400 block uppercase">Latency</span>
                    <span className="text-sm font-mono text-white">{result.latency_ms.toFixed(1)}ms</span>
                  </div>
                </div>

                <div>
                  <span className="text-[10px] font-mono text-gray-500 block mb-1">
                    MODEL ID: {result.model_id} | REQ: {result.request_id}
                  </span>
                  <div className="bg-[#111111] border border-[#262626] rounded-lg p-3 max-h-64 overflow-y-auto text-sm text-gray-200 whitespace-pre-wrap font-mono leading-relaxed">
                    {result.response}
                  </div>
                </div>
              </div>
            ) : (
              <div className="h-64 flex flex-col items-center justify-center text-gray-500 space-y-2">
                <Zap className="w-8 h-8 opacity-40 text-gray-400" />
                <p className="text-sm">Submit a prompt to view routing decision & response</p>
              </div>
            )}
          </div>

          {/* Feedback Section */}
          {result && (
            <div className="border-t border-[#262626] pt-4 mt-4 flex items-center justify-between">
              <span className="text-xs text-gray-400 font-mono">Rate Response Quality:</span>
              <div className="flex space-x-2">
                <button
                  onClick={() => handleFeedback(true)}
                  disabled={!!feedbackSent}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    feedbackSent === "up"
                      ? "bg-[#3DFF6B]/20 border-[#3DFF6B] text-[#3DFF6B]"
                      : "border-[#262626] bg-[#111111] text-gray-300 hover:border-[#3DFF6B] hover:text-[#3DFF6B]"
                  }`}
                >
                  <ThumbsUp className="w-3.5 h-3.5" />
                  <span>Good (U)</span>
                </button>
                <button
                  onClick={() => handleFeedback(false)}
                  disabled={!!feedbackSent}
                  className={`flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${
                    feedbackSent === "down"
                      ? "bg-red-950/60 border-red-500 text-red-400"
                      : "border-[#262626] bg-[#111111] text-gray-300 hover:border-red-500 hover:text-red-400"
                  }`}
                >
                  <ThumbsDown className="w-3.5 h-3.5" />
                  <span>Poor (D)</span>
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
