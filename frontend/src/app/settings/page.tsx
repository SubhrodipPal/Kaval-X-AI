"use client";
import { Shield, Database, Server, Key, Bell, Palette, Globe } from "lucide-react";

const SETTINGS_SECTIONS = [
  {
    icon: Shield,
    title: "Security",
    color: "#00FFD1",
    items: [
      { label: "JWT Token Expiry", value: "30 minutes", type: "text" },
      { label: "mTLS Enabled", value: true, type: "toggle" },
      { label: "PQC Algorithm", value: "CRYSTALS-Dilithium Level 3", type: "text" },
      { label: "Rate Limit", value: "100 req/min per IP", type: "text" },
      { label: "Session Timeout", value: "15 minutes", type: "text" },
    ],
  },
  {
    icon: Database,
    title: "Databases",
    color: "#7B61FF",
    items: [
      { label: "PostgreSQL DSN", value: "postgresql://kavalx:***@postgres:5432/kavalx", type: "text" },
      { label: "Memgraph URL", value: "bolt://memgraph:7687", type: "text" },
      { label: "Redis URL", value: "redis://redis:6379/0", type: "text" },
      { label: "Milvus Host", value: "milvus:19530", type: "text" },
    ],
  },
  {
    icon: Server,
    title: "ML Models",
    color: "#FF3CAC",
    items: [
      { label: "TGN Fraud Threshold", value: "0.70", type: "text" },
      { label: "AMADP Judge Threshold", value: "0.82", type: "text" },
      { label: "Biometric Entropy Min", value: "1.4 bits", type: "text" },
      { label: "AMADP Max Debate Rounds", value: "3", type: "text" },
      { label: "Disagreement Threshold", value: "0.15", type: "text" },
    ],
  },
  {
    icon: Key,
    title: "Kafka",
    color: "#FF6B35",
    items: [
      { label: "Bootstrap Servers", value: "kafka:9092", type: "text" },
      { label: "Txn Raw Partitions", value: "12", type: "text" },
      { label: "Graph Events Partitions", value: "24", type: "text" },
      { label: "Verdict Retention", value: "90 days", type: "text" },
    ],
  },
  {
    icon: Bell,
    title: "Alerting",
    color: "#FFD700",
    items: [
      { label: "Email Notifications", value: true, type: "toggle" },
      { label: "Slack Webhook", value: "Configured ✓", type: "text" },
      { label: "Critical Alert Cooldown", value: "5 minutes", type: "text" },
      { label: "Auto-freeze on Score > 0.9", value: true, type: "toggle" },
    ],
  },
  {
    icon: Globe,
    title: "OSINT",
    color: "#00C9FF",
    items: [
      { label: "Dark Web Scan Interval", value: "6 hours", type: "text" },
      { label: "Telegram Channels Monitored", value: "47", type: "text" },
      { label: "STIX/TAXII Feed URL", value: "https://feeds.cert-in.org.in/taxii2", type: "text" },
      { label: "Tor Proxy", value: "socks5://tor:9050", type: "text" },
    ],
  },
];

export default function SettingsPage() {
  return (
    <div className="space-y-6 max-w-4xl">
      <div>
        <h1 className="text-xl font-extrabold">System <span className="text-kx-muted">Settings</span></h1>
        <div className="text-xs text-kx-muted mt-1">Configuration for all Kavalx services and models</div>
      </div>

      {SETTINGS_SECTIONS.map((section) => (
        <div key={section.title} className="glass-card overflow-hidden">
          <div className="px-5 py-3 border-b border-kx-border flex items-center gap-3">
            <section.icon size={16} style={{ color: section.color }} />
            <span className="text-sm font-bold" style={{ color: section.color }}>{section.title}</span>
          </div>
          <div className="divide-y divide-kx-border">
            {section.items.map((item) => (
              <div key={item.label} className="px-5 py-3 flex items-center justify-between hover:bg-kx-border/10 transition-colors">
                <span className="text-sm text-kx-body">{item.label}</span>
                {item.type === "toggle" ? (
                  <div className={`w-10 h-5 rounded-full relative cursor-pointer transition-colors ${item.value ? 'bg-kx-teal/30' : 'bg-kx-border2'}`}>
                    <div className={`w-4 h-4 rounded-full absolute top-0.5 transition-all ${item.value ? 'right-0.5 bg-kx-teal' : 'left-0.5 bg-kx-muted'}`} />
                  </div>
                ) : (
                  <span className="text-sm font-mono text-kx-muted">{item.value as string}</span>
                )}
              </div>
            ))}
          </div>
        </div>
      ))}

      <div className="glass-card p-5">
        <div className="text-xs text-kx-muted text-center">
          Kavalx v1.0.0 • Build: 2024.11.15 • IIT National Hackathon Edition
        </div>
      </div>
    </div>
  );
}
