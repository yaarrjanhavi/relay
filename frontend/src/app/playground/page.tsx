"use client";

import { useState, useEffect, useCallback } from "react";
import { routePrompt, submitFeedback, RouteResponse } from "@/lib/api";
import { Check, Copy, Lock, AlertTriangle, Database } from "lucide-react";

export default function PlaygroundPage() {
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<RouteResponse | null>(null);
  const [feedbackSent, setFeedbackSent] = useState<"up" | "down" | null>(null);
  const [feedbackStatus, setFeedbackStatus] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  const handleRoute = async (e?: React.FormEvent) => {
    if (e) e.preventDefault();
    if (!prompt.trim() || loading) return;

    setLoading(true);
    setError(null);
    setFeedbackSent(null);
    setFeedbackStatus(null);

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
        const res = await submitFeedback(result.request_id, thumbsUp);
        setFeedbackSent(thumbsUp ? "up" : "down");
        setFeedbackStatus(res.status === "duplicate_ignored" ? "Duplicate ignored" : "Feedback accepted");
      } catch (err: any) {
        setError(err.message || "Failed to submit feedback");
      }
    },
    [result, feedbackSent]
  );

  const handleCopyId = () => {
    if (!result?.request_id) return;
    navigator.clipboard.writeText(result.request_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // Keyboard shortcuts: U = thumbs up, D = thumbs down (only when not inside input/textarea)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
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

  const charCount = prompt.length;
  const isNearLimit = charCount > 19000;

  return (
    <div className="space-y-6">
      {/* Hero Headline */}
      <div className="border-b-[4px] border-black pb-4">
        <h1 className="font-heading text-4xl sm:text-6xl md:text-7xl leading-none tracking-tight text-black">
          SEND IT. <br />
          <span className="bg-black text-[#FFE14D] px-2 py-0.5 inline-block mt-1">
            WE PICK THE MODEL.
          </span>
        </h1>
        <p className="font-mono text-sm sm:text-base text-black font-bold mt-2">
          Bayesian Thompson Sampling LLM Router // Cheap & good enough with safety locks.
        </p>
      </div>

      {/* Two Column Layout on Desktop, Stacked on Mobile */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 items-start">
        {/* Left Column: Input Panel */}
        <div className="bg-white border-[3px] border-black shadow-card p-6 flex flex-col justify-between">
          <form onSubmit={handleRoute} className="flex-1 flex flex-col">
            <div className="flex items-center justify-between mb-2">
              <label htmlFor="prompt-input" className="font-heading text-xl uppercase tracking-wider text-black">
                PROMPT INPUT
              </label>
              <span
                className={`font-mono text-xs font-bold ${
                  isNearLimit ? "text-[#B91C1C] underline font-extrabold" : "text-black"
                }`}
              >
                {charCount.toLocaleString()} / 20,000 CHARS
              </span>
            </div>

            <textarea
              id="prompt-input"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder="Enter prompt here (e.g. 'Write a Python binary search' or 'Dosage of amoxicillin')..."
              rows={11}
              className="w-full bg-white border-[3px] border-black p-4 font-mono text-sm text-black placeholder:text-[#666666] focus:bg-[#FFF8CC] focus:outline-none focus:ring-0 transition-colors resize-none leading-relaxed"
            />

            {error && (
              <div className="mt-4 p-4 bg-[#FF3B30] border-[3px] border-black shadow-err text-black font-mono font-bold text-xs sm:text-sm">
                ERROR: {error}
              </div>
            )}

            <div className="mt-5 flex items-center justify-between">
              <span className="text-xs font-mono text-[#333333]">
                Shortcuts: <kbd className="bg-black text-white px-1.5 py-0.5 text-xs font-bold font-mono">U</kbd> up, <kbd className="bg-black text-white px-1.5 py-0.5 text-xs font-bold font-mono">D</kbd> down
              </span>

              <button
                type="submit"
                disabled={loading || !prompt.trim()}
                className={`min-h-[44px] px-6 py-2.5 font-heading text-lg tracking-wider border-[3px] border-black transition-all ${
                  !prompt.trim()
                    ? "bg-white text-[#555555] diagonal-hatch cursor-not-allowed shadow-none"
                    : loading
                    ? "bg-[#FF4FA3] text-black shadow-btn cursor-wait"
                    : "bg-[#FF4FA3] text-black shadow-btn hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-btnHover active:translate-x-1 active:translate-y-1 active:shadow-none cursor-pointer"
                }`}
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    <span className="brutalist-spinner" />
                    ROUTING...
                  </span>
                ) : (
                  "ROUTE PROMPT"
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Right Column: Result Card */}
        <div className="bg-white border-[3px] border-black shadow-card flex flex-col overflow-hidden">
          {/* High-Stakes Strip */}
          {result?.category === "high_stakes" && (
            <div className="bg-black text-white px-4 py-2 font-heading text-sm sm:text-base flex items-center gap-2 border-b-[3px] border-black">
              <Lock className="w-4 h-4 text-[#B388FF]" />
              <span>SAFETY LOCK: ALWAYS ROUTED TO LARGE</span>
            </div>
          )}

          <div className="p-6 space-y-5">
            {/* Header / Section Label */}
            <div className="flex items-center justify-between border-b-[3px] border-black pb-3">
              <span className="font-heading text-xl uppercase tracking-wider text-black">
                ROUTING DECISION
              </span>
              {result && (
                <div className="flex flex-wrap items-center gap-2">
                  {result.cache_hit && (
                    <span className="bg-white text-black text-xs font-heading border-[3px] border-dashed border-black px-2 py-0.5 shadow-badge">
                      CACHE HIT ($0.00)
                    </span>
                  )}
                  {result.fallback_used && (
                    <span className="bg-[#FF9F1C] text-black text-xs font-heading border-[3px] border-black px-2 py-0.5 shadow-badge flex items-center gap-1">
                      <AlertTriangle className="w-3 h-3" />
                      FALLBACK ESCALATED
                    </span>
                  )}
                </div>
              )}
            </div>

            {result ? (
              <div className="space-y-5">
                {/* Served Tier Badge & Category Row */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <span className="block font-mono text-xs font-bold text-[#333333] uppercase">
                      SERVED TIER
                    </span>
                    <div
                      className={`inline-block font-heading text-3xl sm:text-4xl px-4 py-1 border-[3px] border-black shadow-card -rotate-1 tracking-wider uppercase ${
                        result.tier === "small"
                          ? "bg-[#35F28A] text-black"
                          : result.tier === "medium"
                          ? "bg-[#FF9F1C] text-black"
                          : "bg-[#B388FF] text-black"
                      }`}
                    >
                      {result.tier} TIER
                    </div>
                  </div>

                  <div className="text-right">
                    <span className="block font-mono text-xs font-bold text-[#333333] uppercase">
                      CATEGORY / CONFIDENCE
                    </span>
                    <div className="bg-white border-[3px] border-black shadow-badge px-3 py-1 font-heading text-base inline-block uppercase text-black">
                      {result.category} // {(result.confidence * 100).toFixed(1)}%
                    </div>
                  </div>
                </div>

                {/* Model ID & Request ID with COPY sticker */}
                <div className="bg-[#FFF8CC] border-[3px] border-black p-3 space-y-1.5 font-mono text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-black">MODEL: {result.model_id}</span>
                    <button
                      onClick={handleCopyId}
                      className="bg-white hover:bg-black hover:text-white text-black font-bold border-[2px] border-black px-2 py-0.5 text-[11px] shadow-[2px_2px_0px_#000] flex items-center gap-1 transition-all cursor-pointer"
                    >
                      {copied ? <Check className="w-3 h-3 text-[#35F28A]" /> : <Copy className="w-3 h-3" />}
                      <span>{copied ? "COPIED" : "COPY ID"}</span>
                    </button>
                  </div>
                  <div className="text-[#333333] truncate">REQ ID: {result.request_id}</div>
                </div>

                {/* Metric Chips */}
                <div className="grid grid-cols-3 gap-2">
                  <div className="bg-white border-[3px] border-black p-2 text-center shadow-[3px_3px_0px_#000]">
                    <span className="text-[10px] font-mono font-bold text-[#333333] block">COST</span>
                    <span className="font-mono font-bold text-sm text-black">
                      ${result.cost_usd.toFixed(6)}
                    </span>
                  </div>
                  <div className="bg-white border-[3px] border-black p-2 text-center shadow-[3px_3px_0px_#000]">
                    <span className="text-[10px] font-mono font-bold text-[#333333] block">LATENCY</span>
                    <span className="font-mono font-bold text-sm text-black">
                      {result.latency_ms.toFixed(1)} ms
                    </span>
                  </div>
                  <div className="bg-white border-[3px] border-black p-2 text-center shadow-[3px_3px_0px_#000]">
                    <span className="text-[10px] font-mono font-bold text-[#333333] block">TOKENS</span>
                    <span className="font-mono font-bold text-sm text-black">
                      {result.tier === "small" ? "45/120" : result.tier === "medium" ? "45/160" : "45/210"}
                    </span>
                  </div>
                </div>

                {/* Response Box */}
                <div>
                  <span className="font-mono text-xs font-bold text-black block mb-1">RESPONSE:</span>
                  <div className="border-[3px] border-dashed border-black p-4 font-mono text-sm leading-relaxed max-h-80 overflow-y-auto whitespace-pre-wrap bg-white text-black">
                    {result.response}
                  </div>
                </div>

                {/* Feedback Action Bar */}
                <div className="border-t-[3px] border-black pt-4 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <span className="font-mono font-bold text-xs uppercase text-black">GRADE:</span>
                    {feedbackStatus && (
                      <span className="font-mono text-xs font-bold px-2 py-0.5 bg-[#FFF8CC] border-[2px] border-black">
                        {feedbackStatus}
                      </span>
                    )}
                  </div>

                  <div className="flex items-center gap-3">
                    <button
                      onClick={() => handleFeedback(true)}
                      disabled={!!feedbackSent}
                      className={`min-h-[44px] px-4 py-2 font-heading text-base uppercase border-[3px] border-black transition-all flex items-center gap-1.5 ${
                        feedbackSent === "up"
                          ? "bg-[#35F28A] text-black shadow-none translate-x-1 translate-y-1 font-bold"
                          : "bg-[#35F28A] text-black shadow-btn hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-btnHover active:translate-x-1 active:translate-y-1 active:shadow-none cursor-pointer"
                      }`}
                    >
                      {feedbackSent === "up" && <Check className="w-4 h-4 stroke-[3]" />}
                      <span>GOOD (U)</span>
                    </button>

                    <button
                      onClick={() => handleFeedback(false)}
                      disabled={!!feedbackSent}
                      className={`min-h-[44px] px-4 py-2 font-heading text-base uppercase border-[3px] border-black transition-all flex items-center gap-1.5 ${
                        feedbackSent === "down"
                          ? "bg-[#FF3B30] text-black shadow-none translate-x-1 translate-y-1 font-bold"
                          : "bg-white text-[#B91C1C] shadow-btn hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-btnHover active:translate-x-1 active:translate-y-1 active:shadow-none cursor-pointer"
                      }`}
                    >
                      <span>POOR (D)</span>
                    </button>
                  </div>
                </div>
              </div>
            ) : (
              <div className="border-[3px] border-dashed border-black p-12 text-center space-y-3 bg-[#FFF8CC]/40 my-6">
                <div className="font-heading text-4xl text-black">NOTHING YET.</div>
                <p className="font-mono text-sm text-[#333333] max-w-sm mx-auto">
                  Type a prompt on the left and click &quot;Route Prompt&quot; to inspect real-time tier selection.
                </p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
