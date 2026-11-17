"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  LineChart,
  Briefcase,
  ShieldAlert,
  History,
  Terminal,
  Zap,
  Coins,
  Bot,
} from "lucide-react";

export const Sidebar: React.FC = () => {
  const pathname = usePathname();

  const navItems = [
    { label: "Dashboard", href: "/", icon: LayoutDashboard, badge: "" },
    { label: "Multi-Agent Brain", href: "/agents", icon: Bot, badge: "AI" },
    { label: "Market Scanner", href: "/scanner", icon: LineChart, badge: "" },
    { label: "CoinDCX Crypto", href: "/coindcx", icon: Coins, badge: "Crypto" },
    { label: "Portfolio", href: "/portfolio", icon: Briefcase, badge: "" },
    { label: "Risk Console", href: "/risk", icon: ShieldAlert, badge: "" },
    { label: "Backtesting", href: "/backtest", icon: History, badge: "" },
    { label: "24/7 Gold & TradingView", href: "/tradingview", icon: Zap, badge: "24/7" },
  ];

  return (
    <aside className="w-64 bg-white border-r border-slate-200 flex flex-col justify-between shrink-0 shadow-sm">
      <div>
        {/* Brand header */}
        <div className="h-16 flex items-center gap-3 px-6 border-b border-slate-200">
          <div className="w-9 h-9 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600 font-bold shadow-xs">
            <Terminal className="w-5 h-5" />
          </div>
          <div>
            <div className="text-sm font-bold tracking-tight text-slate-900 flex items-center gap-1.5">
              Groww Lab <span className="text-[10px] text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200 font-mono font-medium">v1.0</span>
            </div>
            <div className="text-[10px] text-slate-500 uppercase tracking-wider font-medium">Algo Trading Platform</div>
          </div>
        </div>

        {/* Navigation links */}
        <nav className="p-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition ${
                  isActive
                    ? "bg-emerald-50 text-emerald-700 font-semibold border border-emerald-200/80 shadow-xs"
                    : "text-slate-600 hover:text-slate-900 hover:bg-slate-100/80"
                }`}
              >
                <Icon className={`w-4 h-4 shrink-0 ${isActive ? "text-emerald-600" : "text-slate-400"}`} />
                <span className="flex-1 text-left">{item.label}</span>
                {Boolean(item.badge) && (
                  <span className="text-[10px] font-bold px-1.5 py-0.5 rounded-full bg-amber-100 text-amber-800 border border-amber-300">
                    {item.badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Safety notice in footer */}
      <div className="p-4 m-4 rounded-xl bg-slate-50 border border-slate-200 text-[11px] text-slate-600 space-y-1">
        <div className="font-semibold text-slate-800 flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500" />
          Safety Guard Active
        </div>
        <div className="text-slate-500 text-[10px] leading-relaxed">
          Pre-trade risk engine intercepts all candidate orders. Live execution remains locked.
        </div>
      </div>
    </aside>
  );
};
