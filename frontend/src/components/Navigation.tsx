"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

const NAV_ITEMS = [
  { name: "Playground", href: "/playground" },
  { name: "Learning", href: "/learning" },
  { name: "Cost", href: "/cost" },
  { name: "Benchmark", href: "/benchmark" },
  { name: "Ops", href: "/ops" },
];

export default function Navigation() {
  const pathname = usePathname();
  const [isOnline, setIsOnline] = useState<boolean>(true);

  // Poll /healthz every 15s
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const apiBase = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        const res = await fetch(`${apiBase}/healthz`, { cache: "no-store" });
        setIsOnline(res.ok);
      } catch {
        setIsOnline(false);
      }
    };

    checkHealth();
    const interval = setInterval(checkHealth, 15000);
    return () => clearInterval(interval);
  }, []);

  return (
    <header className="sticky top-0 z-50 bg-[#FFE14D] border-b-[3px] border-black">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 py-3 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
        {/* Brand / Logo + Status */}
        <div className="flex items-center justify-between">
          <Link href="/" className="flex items-center gap-2 group">
            {/* Logo: RELAY in black block with yellow text, rotated -2deg */}
            <div className="bg-black text-[#FFE14D] px-3.5 py-1 font-heading text-3xl sm:text-4xl tracking-wider -rotate-2 border-[3px] border-black shadow-[4px_4px_0px_#000] group-hover:rotate-0 transition-transform">
              RELAY
            </div>
            {/* V0.1 sticker */}
            <span className="bg-white text-black font-mono font-bold text-xs px-2 py-1 border-[3px] border-black shadow-[2px_2px_0px_#000]">
              V0.1
            </span>
          </Link>

          {/* Mobile Status badge */}
          <div className="md:hidden">
            <StatusBadge isOnline={isOnline} />
          </div>
        </div>

        {/* Navigation Tabs (Stickers) */}
        <nav className="flex items-center gap-2 overflow-x-auto pb-1 md:pb-0 scrollbar-none">
          {NAV_ITEMS.map((item) => {
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                aria-current={isActive ? "page" : undefined}
                className={`whitespace-nowrap px-3.5 py-1.5 font-heading text-sm sm:text-base uppercase tracking-wider border-[3px] border-black transition-all ${
                  isActive
                    ? "bg-[#FF4FA3] text-black shadow-[2px_2px_0px_#000] translate-x-0.5 translate-y-0.5"
                    : "bg-white text-black shadow-[3px_3px_0px_#000] hover:-translate-x-0.5 hover:-translate-y-0.5 hover:shadow-[5px_5px_0px_#000] active:translate-x-0.5 active:translate-y-0.5 active:shadow-none"
                }`}
              >
                {item.name}
              </Link>
            );
          })}
        </nav>

        {/* Desktop Status Badge */}
        <div className="hidden md:flex items-center">
          <StatusBadge isOnline={isOnline} />
        </div>
      </div>
    </header>
  );
}

function StatusBadge({ isOnline }: { isOnline: boolean }) {
  return (
    <div
      className={`flex items-center gap-2 px-3 py-1 border-[3px] border-black shadow-[3px_3px_0px_#000] font-mono font-bold text-xs ${
        isOnline ? "bg-white text-black" : "bg-[#FF3B30] text-black"
      }`}
    >
      <span
        className={`w-2.5 h-2.5 border-[2px] border-black ${
          isOnline ? "bg-[#35F28A]" : "bg-black animate-pulse"
        }`}
      />
      <span>{isOnline ? "ONLINE" : "OFFLINE"}</span>
    </div>
  );
}
