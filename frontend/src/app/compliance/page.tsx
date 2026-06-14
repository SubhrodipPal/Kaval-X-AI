"use client";
import { useState } from "react";
import { FileText, Shield, CheckCircle, Clock, AlertTriangle, ExternalLink } from "lucide-react";

const MOCK_REPORTS = [
  { id: "RPT-001", txn: "txn_7e9b3c4a", type: "rbi_incident", status: "signed", generated: "2024-11-15 14:32", lang: "EN", sig: "a3f2...8c91", ledger: "fabric_tx_8a2f...e7d1" },
  { id: "RPT-002", txn: "txn_3c8d2e1f", type: "cert_in_advisory", status: "completed", generated: "2024-11-15 13:18", lang: "EN", sig: null, ledger: null },
  { id: "RPT-003", txn: "txn_9a4b5c6d", type: "rbi_incident", status: "generating", generated: "2024-11-15 15:01", lang: "HI", sig: null, ledger: null },
  { id: "RPT-004", txn: "txn_1f2e3d4c", type: "rbi_incident", status: "signed", generated: "2024-11-15 11:45", lang: "EN", sig: "b7c4...2d3e", ledger: "fabric_tx_4c1a...b9f2" },
  { id: "RPT-005", txn: "txn_5e6f7a8b", type: "cert_in_advisory", status: "pending", generated: "2024-11-15 15:12", lang: "EN", sig: null, ledger: null },
];

const statusColors: Record<string, { bg: string; text: string; icon: any }> = {
  signed: { bg: "#00FFD115", text: "#00FFD1", icon: CheckCircle },
  completed: { bg: "#7B61FF15", text: "#7B61FF", icon: Shield },
  generating: { bg: "#FFD70015", text: "#FFD700", icon: Clock },
  pending: { bg: "#FF6B3515", text: "#FF6B35", icon: AlertTriangle },
};

const LEDGER_TRAIL = [
  { block: 12847, hash: "0x8a2f...e7d1c3", timestamp: "14:32:18 IST", status: "verified", reports: 1 },
  { block: 12846, hash: "0x4c1a...b9f2a7", timestamp: "11:45:42 IST", status: "verified", reports: 1 },
  { block: 12845, hash: "0x9e3b...d4c8f1", timestamp: "09:22:05 IST", status: "verified", reports: 2 },
  { block: 12844, hash: "0x1f7a...e2b5c9", timestamp: "08:15:33 IST", status: "pending", reports: 1 },
];

export default function CompliancePage() {
  const [selectedReport, setSelectedReport] = useState(MOCK_REPORTS[0]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-extrabold">Compliance <span className="text-kx-orange">Dashboard</span></h1>

      <div className="grid grid-cols-1 xl:grid-cols-3 gap-4">
        {/* Report Queue */}
        <div className="xl:col-span-2 glass-card">
          <div className="px-5 py-3 border-b border-kx-border flex items-center justify-between">
            <div className="text-sm font-bold">Report Queue</div>
            <div className="flex gap-4 text-xs text-kx-muted">
              <span>Pending: <span className="text-kx-orange font-bold">2</span></span>
              <span>Completed: <span className="text-kx-purple font-bold">3</span></span>
              <span>Signed: <span className="text-kx-teal font-bold">2</span></span>
            </div>
          </div>
          <div className="divide-y divide-kx-border">
            {MOCK_REPORTS.map((r) => {
              const sc = statusColors[r.status];
              const Icon = sc.icon;
              return (
                <div key={r.id} onClick={() => setSelectedReport(r)}
                  className={`px-5 py-3 flex items-center gap-4 cursor-pointer hover:bg-kx-border/20 transition-colors ${selectedReport.id === r.id ? 'bg-kx-border/30' : ''}`}>
                  <FileText size={16} className="text-kx-muted shrink-0" />
                  <div className="flex-1 min-w-0">
                    <div className="text-sm font-semibold text-kx-head">{r.id}</div>
                    <div className="text-[10px] text-kx-muted font-mono">{r.txn}</div>
                  </div>
                  <span className="text-[10px] px-2 py-0.5 rounded-full font-bold uppercase"
                    style={{ background: sc.bg, color: sc.text }}>
                    <Icon size={10} className="inline mr-1" />{r.status}
                  </span>
                  <span className="text-[10px] text-kx-muted font-mono">{r.type.replace("_", " ").toUpperCase()}</span>
                  <span className="text-[10px] text-kx-muted">{r.generated}</span>
                </div>
              );
            })}
          </div>
        </div>

        {/* Report Preview */}
        <div className="glass-card p-5 glow-orange">
          <div className="text-sm font-bold text-kx-head mb-4">Report Preview</div>
          <div className="bg-white rounded-lg p-4 text-black text-xs space-y-3" style={{ fontFamily: 'serif' }}>
            <div className="text-center">
              <div className="font-bold text-sm text-blue-900">RESERVE BANK OF INDIA</div>
              <div className="text-[10px] text-gray-500">Cyber Security Incident Report</div>
              <hr className="my-2" />
            </div>
            <div><b>Report ID:</b> {selectedReport.id}</div>
            <div><b>Transaction:</b> {selectedReport.txn}</div>
            <div><b>Type:</b> {selectedReport.type.replace("_", " ").toUpperCase()}</div>
            <div><b>Status:</b> {selectedReport.status.toUpperCase()}</div>
            <div><b>Language:</b> {selectedReport.lang}</div>
            {selectedReport.sig && (
              <div className="mt-2 p-2 bg-gray-100 rounded font-mono text-[10px]">
                <div><b>PQC Signature:</b> {selectedReport.sig}</div>
                <div><b>Algorithm:</b> CRYSTALS-Dilithium</div>
              </div>
            )}
            {selectedReport.ledger && (
              <div className="p-2 bg-blue-50 rounded font-mono text-[10px]">
                <div><b>Ledger TX:</b> {selectedReport.ledger}</div>
                <div className="text-green-600">✓ Anchored to Hyperledger Fabric</div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Ledger Audit Trail */}
      <div className="glass-card p-5">
        <div className="text-sm font-bold text-kx-head mb-4">Blockchain Audit Trail</div>
        <div className="space-y-3">
          {LEDGER_TRAIL.map((entry, i) => (
            <div key={i} className="flex items-center gap-4 p-3 rounded-lg border border-kx-border hover:border-kx-border2 transition-all">
              <div className="w-10 h-10 rounded-lg bg-kx-surface flex items-center justify-center text-xs font-bold text-kx-purple font-mono">
                #{entry.block}
              </div>
              <div className="flex-1">
                <div className="text-sm font-mono text-kx-head">{entry.hash}</div>
                <div className="text-[10px] text-kx-muted">{entry.timestamp} • {entry.reports} report(s)</div>
              </div>
              <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${entry.status === 'verified' ? 'bg-[#00FFD115] text-[#00FFD1]' : 'bg-[#FFD70015] text-[#FFD700]'}`}>
                {entry.status.toUpperCase()}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
