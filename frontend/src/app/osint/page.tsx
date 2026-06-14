"use client";
import { useState, useEffect } from "react";
import { Globe, MessageCircle, Code, Radio, AlertTriangle, Clock, Shield } from "lucide-react";

const THREAT_INDICATORS = [
  { id: "IOC-001", type: "credential", value: "user1234@hdfc***", source: "darkweb", severity: 5, time: "2m ago",
    context: "Credential bundle for HDFC net banking found on Exploit.in forum, includes 2FA bypass method", geo: "🇷🇺 Moscow" },
  { id: "IOC-002", type: "credential", value: "admin@***.sbi.co.in:P@ss***", source: "telegram", severity: 5, time: "30m ago",
    context: "SBI internal credentials posted in Telegram channel 'BankLeaks_IN' (180K subscribers)", geo: null },
  { id: "IOC-003", type: "credential", value: "UPI:victim@oksbi (OTP kit)", source: "darkweb", severity: 5, time: "45m ago",
    context: "Complete UPI fraud kit with OTP interception tool, priced at ₹5000 on dark web marketplace", geo: null },
  { id: "IOC-004", type: "hash", value: "a3f2b8c9d1e4f7g8...", source: "stix", severity: 5, time: "1h ago",
    context: "SHA-256 hash of BankBot v4.2 variant targeting Indian UPI apps (CERT-In advisory CIAD-2024-0089)", geo: null },
  { id: "IOC-005", type: "domain", value: "hdfc-secure-login.xyz", source: "stix", severity: 4, time: "8h ago",
    context: "Phishing domain mimicking HDFC Bank login page, SSL cert issued 6h ago", geo: null },
  { id: "IOC-006", type: "card_bin", value: "4367-26XX-XXXX-XXXX", source: "darkweb", severity: 4, time: "5h ago",
    context: "Batch of 500 SBI debit card numbers listed for sale at $15/card", geo: "🇺🇦 Kyiv" },
  { id: "IOC-007", type: "domain", value: "paytm-rewards-claim.com", source: "telegram", severity: 4, time: "4h ago",
    context: "Paytm phishing kit being distributed via WhatsApp groups", geo: null },
  { id: "IOC-008", type: "ip", value: "185.220.101.42", source: "darkweb", severity: 3, time: "12h ago",
    context: "C2 server for Anubis banking trojan campaign targeting Indian banks", geo: "🇳🇱 Netherlands" },
  { id: "IOC-009", type: "hash", value: "e7d2f1a3b5c8d0e2...", source: "github", severity: 3, time: "3h ago",
    context: "API key for payment gateway found in public GitHub repo (truffleHog detection)", geo: null },
  { id: "IOC-010", type: "ip", value: "103.152.220.18", source: "stix", severity: 4, time: "6h ago",
    context: "SMS phishing campaign origin server targeting Indian mobile numbers", geo: "🇮🇳 Delhi" },
  { id: "IOC-011", type: "card_bin", value: "5241-07XX (ICICI Plat)", source: "darkweb", severity: 4, time: "7h ago",
    context: "ICICI Bank platinum card BIN dump, 200 cards, includes CVV and expiry", geo: "🇺🇦 Kyiv" },
  { id: "IOC-012", type: "ip", value: "45.153.243.99", source: "stix", severity: 3, time: "18h ago",
    context: "Tor exit node associated with banking fraud reconnaissance", geo: "🇩🇪 Germany" },
];

const EARLY_WARNINGS = [
  { type: "Credential Bundle Attack", confidence: 0.87, hours: 6.5, indicators: 3, color: "#FF3CAC" },
  { type: "Phishing Campaign — HDFC", confidence: 0.72, hours: 18.2, indicators: 2, color: "#FF6B35" },
  { type: "Card Data Breach — SBI", confidence: 0.65, hours: 36.0, indicators: 2, color: "#FFD700" },
];

const sourceIcons: Record<string, { icon: any; label: string; color: string }> = {
  darkweb: { icon: Globe, label: "Dark Web", color: "#FF3CAC" },
  telegram: { icon: MessageCircle, label: "Telegram", color: "#00C9FF" },
  github: { icon: Code, label: "GitHub", color: "#7B61FF" },
  stix: { icon: Radio, label: "STIX/TAXII", color: "#FFD700" },
};

const sevColors: Record<number, string> = { 5: "#FF3CAC", 4: "#FF6B35", 3: "#FFD700", 2: "#00C9FF", 1: "#4A6880" };
const sevLabels: Record<number, string> = { 5: "CRITICAL", 4: "HIGH", 3: "MEDIUM", 2: "LOW", 1: "INFO" };

export default function OSINTPage() {
  const [sourceFilter, setSourceFilter] = useState<string | null>(null);
  const [minSeverity, setMinSeverity] = useState(1);
  const [newAlert, setNewAlert] = useState(false);

  // Simulate new indicator arrival
  useEffect(() => {
    const timer = setTimeout(() => setNewAlert(true), 5000);
    return () => clearTimeout(timer);
  }, []);

  const filtered = THREAT_INDICATORS.filter(t =>
    (!sourceFilter || t.source === sourceFilter) && t.severity >= minSeverity
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-extrabold">OSINT <span className="text-kx-blue">Threat Feed</span></h1>
          <div className="text-xs text-kx-muted">Dark web, Telegram, GitHub, STIX/TAXII intelligence</div>
        </div>
        <div className="flex items-center gap-2">
          {newAlert && (
            <span className="px-3 py-1 rounded-full text-xs font-bold bg-[#FF3CAC20] text-[#FF3CAC] animate-pulse">
              🔴 NEW THREAT DETECTED
            </span>
          )}
          <span className="text-xs text-kx-muted font-mono">{filtered.length} indicators</span>
        </div>
      </div>

      {/* Early Warnings */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {EARLY_WARNINGS.map((w, i) => (
          <div key={i} className="glass-card p-4" style={{ boxShadow: `0 0 20px ${w.color}15` }}>
            <div className="flex items-start justify-between mb-2">
              <AlertTriangle size={16} style={{ color: w.color }} />
              <span className="text-[10px] font-bold px-2 py-0.5 rounded-full" style={{ background: `${w.color}15`, color: w.color }}>
                {(w.confidence * 100).toFixed(0)}% confidence
              </span>
            </div>
            <div className="text-sm font-bold text-kx-head mb-1">{w.type}</div>
            <div className="flex items-center gap-2 text-xs text-kx-muted">
              <Clock size={10} />
              <span>Est. {w.hours.toFixed(1)}h until attack</span>
              <span>•</span>
              <span>{w.indicators} IOCs</span>
            </div>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="flex gap-2 flex-wrap">
        <button onClick={() => setSourceFilter(null)}
          className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${!sourceFilter ? 'border-kx-teal bg-[#00FFD115] text-kx-teal' : 'border-kx-border text-kx-muted'}`}>
          All Sources
        </button>
        {Object.entries(sourceIcons).map(([key, { label, color }]) => (
          <button key={key} onClick={() => setSourceFilter(key === sourceFilter ? null : key)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${sourceFilter === key ? `bg-[${color}15]` : 'border-kx-border text-kx-muted'}`}
            style={sourceFilter === key ? { borderColor: color, color, background: `${color}15` } : {}}>
            {label}
          </button>
        ))}
        <select value={minSeverity} onChange={e => setMinSeverity(Number(e.target.value))}
          className="px-3 py-1.5 rounded-lg text-xs font-semibold border border-kx-border bg-kx-surface text-kx-body">
          <option value={1}>All Severities</option>
          <option value={3}>Medium+</option>
          <option value={4}>High+</option>
          <option value={5}>Critical only</option>
        </select>
      </div>

      {/* Threat Feed */}
      <div className="space-y-3">
        {filtered.map((t, i) => {
          const src = sourceIcons[t.source];
          const Icon = src.icon;
          return (
            <div key={t.id} className={`glass-card p-4 hover:border-kx-border2 transition-all ${i === 0 && newAlert ? 'animate-pulse border-[#FF3CAC55]' : ''}`}>
              <div className="flex items-start gap-4">
                <div className="w-10 h-10 rounded-lg flex items-center justify-center shrink-0"
                  style={{ background: `${src.color}15` }}>
                  <Icon size={18} style={{ color: src.color }} />
                </div>
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-bold px-2 py-0.5 rounded-full"
                      style={{ background: `${sevColors[t.severity]}15`, color: sevColors[t.severity] }}>
                      {sevLabels[t.severity]}
                    </span>
                    <span className="text-xs text-kx-muted font-mono">{t.id}</span>
                    <span className="text-xs text-kx-muted">{t.type.toUpperCase()}</span>
                    <span className="text-xs text-kx-muted ml-auto">{t.time}</span>
                  </div>
                  <div className="text-sm font-mono font-bold text-kx-head mb-1">{t.value}</div>
                  <div className="text-xs text-kx-body leading-relaxed">{t.context}</div>
                  {t.geo && <div className="text-[10px] text-kx-muted mt-1">📍 {t.geo}</div>}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
