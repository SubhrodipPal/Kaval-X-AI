"use client";
import { useEffect, useState } from "react";
import { Activity, AlertTriangle, Shield, TrendingUp, Zap, Server } from "lucide-react";
import { AreaChart, Area, ResponsiveContainer, Tooltip } from "recharts";

// ─── Mock Data ───
const genSparkline = (n: number) =>
  Array.from({ length: n }, (_, i) => ({
    t: i,
    v: 800 + Math.sin(i / 3) * 200 + Math.random() * 150,
  }));

const KPIS = [
  { label: "Transactions Processed", value: 2_847_392, delta: "+12.4%", icon: TrendingUp, color: "#00FFD1", glow: "glow-teal" },
  { label: "Active Threats", value: 23, delta: "+3", icon: AlertTriangle, color: "#FF6B35", glow: "glow-orange" },
  { label: "AMADP Verdicts Today", value: 1_284, delta: "+8.2%", icon: Shield, color: "#FF3CAC", glow: "glow-pink" },
  { label: "System Uptime", value: 99.97, delta: "%, 14d", icon: Server, color: "#7B61FF", glow: "glow-purple", isPercent: true },
];

const RECENT_ALERTS = [
  { id: "ALT-2847", type: "Mule Cluster", severity: "critical", account: "acc_0042", score: 0.94, time: "2m ago" },
  { id: "ALT-2846", type: "RAT Detected", severity: "high", account: "acc_1899", score: 0.87, time: "5m ago" },
  { id: "ALT-2845", type: "Velocity Anomaly", severity: "medium", account: "acc_0331", score: 0.72, time: "12m ago" },
  { id: "ALT-2844", type: "APK Threat", severity: "high", account: "dev_8812", score: 0.81, time: "18m ago" },
  { id: "ALT-2843", type: "Geo Impossible", severity: "medium", account: "acc_0512", score: 0.68, time: "24m ago" },
  { id: "ALT-2842", type: "Credential Leak", severity: "critical", account: "OSINT", score: 0.96, time: "31m ago" },
];

const SERVICES = [
  { name: "API Gateway", status: "healthy", latency: "12ms", port: 8000, color: "#00FFD1" },
  { name: "Transaction Intel", status: "healthy", latency: "28ms", port: 8001, color: "#00C9FF" },
  { name: "APK Analysis", status: "healthy", latency: "45ms", port: 8002, color: "#FF6B35" },
  { name: "Graph Intelligence", status: "healthy", latency: "31ms", port: 8003, color: "#7B61FF" },
  { name: "Biometrics", status: "healthy", latency: "8ms", port: 8004, color: "#FFD700" },
  { name: "AMADP Orchestrator", status: "healthy", latency: "142ms", port: 8005, color: "#FF3CAC" },
  { name: "OSINT Fusion", status: "degraded", latency: "89ms", port: 8006, color: "#00C9FF" },
  { name: "Compliance", status: "healthy", latency: "34ms", port: 8007, color: "#FF6B35" },
  { name: "FL Coordinator", status: "healthy", latency: "67ms", port: 8008, color: "#7B61FF" },
];

function AnimatedNumber({ value, isPercent }: { value: number; isPercent?: boolean }) {
  const [display, setDisplay] = useState(0);
  useEffect(() => {
    let start = 0;
    const end = value;
    const duration = 1500;
    const startTime = Date.now();
    const animate = () => {
      const elapsed = Date.now() - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplay(Math.floor(start + (end - start) * eased));
      if (progress < 1) requestAnimationFrame(animate);
      else setDisplay(end);
    };
    animate();
  }, [value]);
  return (
    <span className="count-anim">
      {isPercent ? display.toFixed(2) : display.toLocaleString()}
    </span>
  );
}

const sevColors: Record<string, string> = {
  critical: "#FF3CAC",
  high: "#FF6B35",
  medium: "#FFD700",
  low: "#00FFD1",
};

export default function DashboardPage() {
  const sparkData = genSparkline(30);

  return (
    <div className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-4">
        {KPIS.map((kpi) => (
          <div key={kpi.label} className={`glass-card p-5 ${kpi.glow}`}>
            <div className="flex items-start justify-between mb-3">
              <div className="text-xs font-semibold text-kx-muted uppercase tracking-wider">
                {kpi.label}
              </div>
              <kpi.icon size={18} style={{ color: kpi.color }} />
            </div>
            <div className="text-3xl font-extrabold tracking-tight" style={{ color: kpi.color }}>
              <AnimatedNumber value={kpi.value} isPercent={kpi.isPercent} />
            </div>
            <div className="text-xs text-kx-muted mt-1">{kpi.delta}</div>
          </div>
        ))}
      </div>

      {/* Transaction Rate Chart + Recent Alerts */}
      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Chart */}
        <div className="xl:col-span-2 glass-card p-5">
          <div className="flex items-center justify-between mb-4">
            <div>
              <div className="text-sm font-bold text-kx-head">Transaction Rate</div>
              <div className="text-xs text-kx-muted">Transactions per second (30-minute window)</div>
            </div>
            <div className="flex items-center gap-2">
              <Zap size={14} className="text-kx-teal" />
              <span className="text-sm font-bold text-kx-teal">1,247 TPS</span>
            </div>
          </div>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={sparkData}>
                <defs>
                  <linearGradient id="tealGrad" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00FFD1" stopOpacity={0.3} />
                    <stop offset="100%" stopColor="#00FFD1" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <Tooltip
                  contentStyle={{ background: '#07111F', border: '1px solid #0F2035', borderRadius: 8, fontSize: 12 }}
                  labelStyle={{ color: '#4A6880' }}
                />
                <Area type="monotone" dataKey="v" stroke="#00FFD1" strokeWidth={2} fill="url(#tealGrad)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        {/* Recent Alerts */}
        <div className="glass-card p-5">
          <div className="text-sm font-bold text-kx-head mb-4">Recent Alerts</div>
          <div className="space-y-3">
            {RECENT_ALERTS.map((a) => (
              <div key={a.id} className="flex items-center gap-3 p-2 rounded-lg hover:bg-kx-border/30 transition-colors">
                <div className="w-2 h-2 rounded-full shrink-0" style={{ background: sevColors[a.severity] }} />
                <div className="flex-1 min-w-0">
                  <div className="text-xs font-semibold text-kx-head truncate">{a.type}</div>
                  <div className="text-[10px] text-kx-muted font-mono">{a.account}</div>
                </div>
                <div className="text-xs font-bold font-mono" style={{ color: sevColors[a.severity] }}>
                  {a.score.toFixed(2)}
                </div>
                <div className="text-[10px] text-kx-muted whitespace-nowrap">{a.time}</div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Service Health */}
      <div className="glass-card p-5">
        <div className="text-sm font-bold text-kx-head mb-4">Service Health Matrix</div>
        <div className="grid grid-cols-1 md:grid-cols-3 xl:grid-cols-9 gap-3">
          {SERVICES.map((svc) => (
            <div key={svc.name} className="p-3 rounded-lg border border-kx-border hover:border-kx-border2 transition-all text-center">
              <div className="w-3 h-3 rounded-full mx-auto mb-2"
                style={{ background: svc.status === "healthy" ? "#00FFD1" : "#FF6B35" }} />
              <div className="text-[10px] font-bold text-kx-head truncate">{svc.name}</div>
              <div className="text-[10px] text-kx-muted font-mono">{svc.latency}</div>
              <div className="text-[10px] font-mono" style={{ color: svc.color }}>:{svc.port}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
