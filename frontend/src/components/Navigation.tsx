"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { PlayCircle, BrainCircuit, DollarSign, BarChart3, Activity } from "lucide-react";

const NAV_ITEMS = [
  { name: "Playground", href: "/playground", icon: PlayCircle },
  { name: "Learning", href: "/learning", icon: BrainCircuit },
  { name: "Cost", href: "/cost", icon: DollarSign },
  { name: "Benchmark", href: "/benchmark", icon: BarChart3 },
  { name: "Ops", href: "/ops", icon: Activity },
];

export default function Navigation() {
  const pathname = usePathname();

  return (
    <nav className="border-b border-[#262626] bg-[#1A1A1A]/80 backdrop-blur sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-16">
          <div className="flex items-center space-x-3">
            <Link href="/" className="flex items-center space-x-2">
              <span className="font-heading text-3xl font-bold tracking-wider text-[#3DFF6B]">
                RELAY
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-[#262626] text-gray-400 font-mono">
                v0.1
              </span>
            </Link>
          </div>

          <div className="flex space-x-1 sm:space-x-2">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const isActive = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={`flex items-center space-x-2 px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-[#262626] text-[#3DFF6B] border border-[#3DFF6B]/30"
                      : "text-gray-400 hover:text-white hover:bg-[#222222]"
                  }`}
                >
                  <Icon className="w-4 h-4" />
                  <span className="hidden sm:inline">{item.name}</span>
                </Link>
              );
            })}
          </div>
        </div>
      </div>
    </nav>
  );
}
