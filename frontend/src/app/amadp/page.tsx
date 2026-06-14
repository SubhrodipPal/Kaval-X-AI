"use client";
import { useState, useEffect, useRef } from "react";

// ─── Mock Debate Data ───
const MOCK_DEBATE = {
  verdict_id: "vrd_a8c2f1d3",
  txn_id: "txn_7e9b3c4a",
  rounds: [
    {
      prosecution: `**Opening Statement:** Based on multi-vector analysis, transaction txn_7e9b3c4a exhibits 
strong indicators of coordinated mule account fraud.

**Evidence Analysis:**
1. **TGN Graph Score: 0.847** (threshold: 0.70) — The source account acc_0042 is embedded within 
a cluster of 7 accounts showing rapid fund cycling patterns. The TGN temporal attention mechanism 
detected anomalous edge patterns: 14 outbound transfers in 47 minutes, each just below ₹49,999.
2. **Biometric Trust: 0.231** (threshold: 0.50) — PINN analysis reveals Shannon entropy of 
1.18 bits/sample on the device sensor stream, well below the 1.4-bit humanness threshold. 
Gravity alignment violation detected: acc_z deviation of 0.72 from expected g·cos(θ).
3. **Velocity: 14 txn/hour** — This is 4.7σ above the account's historical mean of 2.1 txn/hour.

**Regulatory Violations:**
- RBI Master Direction §7.2: Failure to implement transaction velocity monitoring
- PMLA §12(1): Structuring below ₹50,000 to avoid CTR reporting threshold

**Recommendation: BLOCK and FREEZE source account pending investigation.**`,

      defense: `**Opening Statement:** The prosecution's case relies heavily on circumstantial scoring models 
without accounting for legitimate business activity patterns that explain this transaction.

**Alternative Explanations:**
1. **TGN Score Context:** Account acc_0042 is registered as a small business (STD Kirana store). 
The 14 transactions in 47 minutes are consistent with end-of-day batch settlements from UPI 
collect requests. Merchant accounts routinely show 15-25 daily settlements.
2. **Biometric Analysis:** The low entropy reading (1.18 bits) is explained by the device being 
placed on a flat surface (shop counter) during batch processing — a common merchant behavior. 
The PINN model was trained primarily on handheld phone data and has known bias against 
stationary device patterns (documented in technical review TR-2024-017).
3. **Amount Pattern:** Individual amounts of ₹45,000-49,000 match the modal transaction size 
for wholesale grocery purchases in Tier-2 cities (per RBI Digital Payment Statistics Q3 2024).

**False Positive Impact:**
Freezing a merchant account would prevent legitimate business operations for 72+ hours, 
affecting 200+ daily customers. False positive rate for merchant accounts is 3.2x higher than personal.

**Recommendation: ALLOW with enhanced monitoring for 7 days.**`,
    },
    {
      prosecution: `**Rebuttal Round 2:**
The defense's merchant explanation has critical weaknesses:

1. **Merchant registration was completed only 6 days ago.** New merchant accounts require 
30-day monitoring under RBI's Know Your Merchant (KYM) guidelines. Zero transaction history 
prior to Day 5 — this is consistent with mule account priming.
2. **Beneficiary analysis:** 5 of 7 receiving accounts (acc_0088, acc_0091, acc_0095, acc_0097, 
acc_0099) were created within a 48-hour window. This is a hallmark of coordinated mule ring setup.
3. **The defense cites TR-2024-017** regarding stationary device bias, but this technical review 
specifically states correction is needed for devices showing BOTH low entropy AND zero gyroscope 
variance. This device shows near-zero gyro_z variance (σ=0.0003), confirming scripted automation.

**Updated confidence: 0.91 → BLOCK remains recommended.**`,

      defense: `**Rebuttal Round 2:**
Acknowledged: the 6-day account age is concerning. However:

1. **Account migration context:** The KYC documents show a pre-existing ICICI account (12 years). 
Account migration to digital-first banks is common — 34% of new accounts at neobanks are migrations.
2. **Beneficiary clustering:** Multiple new supplier accounts being created simultaneously is 
normal during seasonal onboarding (June = Monsoon stock-up). The defense requests a 24-hour 
hold to verify with the account holder directly before autonomous action.
3. **Partial concession:** We agree enhanced monitoring is warranted but FREEZE would cause 
disproportionate harm. A 24-hour REVIEW with customer contact is appropriate.

**Updated confidence: 0.62 → REVIEW (human escalation) recommended.**`,
    },
  ],
  judge: {
    verdict: "review",
    confidence: 0.78,
    prosecution_conf: 0.91,
    defense_conf: 0.62,
    reasoning: `The prosecution presents strong quantitative evidence (TGN 0.847, entropy 1.18, 
velocity 4.7σ). The defense raises valid concerns about merchant patterns and false positive costs.

KEY FACTORS:
✓ Account age < 30 days → KYM monitoring required (Rule R-007)
✓ Beneficiary clustering detected → Elevated risk (Rule R-041)  
✗ Merchant migration is plausible but unverified
✗ Disagreement gap |0.91 - 0.62| = 0.29 > 0.15 → Significant disagreement

RULING: The disagreement threshold is NOT exceeded (0.29 > 0.15), but judge confidence 
(0.78) is below autonomous action threshold (0.82). MANDATORY HUMAN REVIEW.

ACTION: Temporary hold (24h), notify analyst team, request customer callback.`,
    action: "REVIEW — Human escalation with 24h hold",
  },
};

function TypingText({ text, speed = 10, className = "" }: { text: string; speed?: number; className?: string }) {
  const [displayed, setDisplayed] = useState("");
  const [done, setDone] = useState(false);
  useEffect(() => {
    setDisplayed("");
    setDone(false);
    let i = 0;
    const timer = setInterval(() => {
      setDisplayed(text.slice(0, i + 1));
      i++;
      if (i >= text.length) { clearInterval(timer); setDone(true); }
    }, speed);
    return () => clearInterval(timer);
  }, [text, speed]);
  return (
    <div className={className}>
      <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed">{displayed}</pre>
      {!done && <span className="inline-block w-2 h-4 bg-current animate-pulse ml-0.5" />}
    </div>
  );
}

export default function AMADPPage() {
  const [round, setRound] = useState(0);
  const [showJudge, setShowJudge] = useState(false);
  const debate = MOCK_DEBATE;
  const currentRound = debate.rounds[round];

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-extrabold">AMADP <span className="text-kx-pink">Adversarial Debate</span></h1>
          <div className="text-xs text-kx-muted font-mono mt-1">
            Verdict: {debate.verdict_id} | Transaction: {debate.txn_id}
          </div>
        </div>
        <div className="flex gap-2">
          {debate.rounds.map((_, i) => (
            <button key={i} onClick={() => { setRound(i); setShowJudge(false); }}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${round === i ? 'border-kx-pink bg-[#FF3CAC15] text-kx-pink' : 'border-kx-border text-kx-muted hover:border-kx-border2'}`}>
              Round {i + 1}
            </button>
          ))}
          <button onClick={() => setShowJudge(true)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all ${showJudge ? 'border-kx-purple bg-[#7B61FF15] text-kx-purple' : 'border-kx-border text-kx-muted hover:border-kx-border2'}`}>
            ⚖️ Judge Verdict
          </button>
        </div>
      </div>

      {!showJudge ? (
        /* Debate Panels */
        <div className="grid grid-cols-1 xl:grid-cols-2 gap-4">
          {/* Prosecution */}
          <div className="glass-card border-[#FF3CAC33] glow-pink">
            <div className="px-5 py-3 border-b border-kx-border flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#FF3CAC20] flex items-center justify-center text-sm">⚔️</div>
              <div>
                <div className="text-sm font-bold text-[#FF3CAC]">Prosecution Agent</div>
                <div className="text-[10px] text-kx-muted">Mistral-7B | Confidence: {debate.judge.prosecution_conf}</div>
              </div>
              <div className="ml-auto flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-[#FF3CAC] pulse-dot" />
                <span className="text-[10px] text-kx-muted">ACTIVE</span>
              </div>
            </div>
            <div className="p-5 max-h-[60vh] overflow-y-auto">
              <TypingText text={currentRound.prosecution} className="text-kx-body" speed={3} />
            </div>
          </div>

          {/* Defense */}
          <div className="glass-card border-[#00FFD133] glow-teal">
            <div className="px-5 py-3 border-b border-kx-border flex items-center gap-3">
              <div className="w-8 h-8 rounded-lg bg-[#00FFD120] flex items-center justify-center text-sm">🛡️</div>
              <div>
                <div className="text-sm font-bold text-kx-teal">Defense Agent</div>
                <div className="text-[10px] text-kx-muted">Mistral-7B | Confidence: {debate.judge.defense_conf}</div>
              </div>
              <div className="ml-auto flex items-center gap-1">
                <div className="w-2 h-2 rounded-full bg-[#00FFD1] pulse-dot" />
                <span className="text-[10px] text-kx-muted">ACTIVE</span>
              </div>
            </div>
            <div className="p-5 max-h-[60vh] overflow-y-auto">
              <TypingText text={currentRound.defense} className="text-kx-body" speed={3} />
            </div>
          </div>
        </div>
      ) : (
        /* Judge Verdict */
        <div className="glass-card border-[#7B61FF33] glow-purple max-w-4xl mx-auto">
          <div className="px-5 py-4 border-b border-kx-border flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-[#7B61FF20] flex items-center justify-center text-lg">⚖️</div>
            <div>
              <div className="text-lg font-bold text-kx-purple">Judge Verdict</div>
              <div className="text-xs text-kx-muted">Neuro-Symbolic Adjudicator (py-datalog + NSE)</div>
            </div>
          </div>
          <div className="p-6 space-y-6">
            {/* Confidence Meters */}
            <div className="grid grid-cols-3 gap-4">
              {[
                { label: "Prosecution", value: debate.judge.prosecution_conf, color: "#FF3CAC" },
                { label: "Defense", value: debate.judge.defense_conf, color: "#00FFD1" },
                { label: "Judge", value: debate.judge.confidence, color: "#7B61FF" },
              ].map(({ label, value, color }) => (
                <div key={label} className="text-center">
                  <div className="text-xs text-kx-muted mb-2">{label}</div>
                  <div className="text-2xl font-extrabold font-mono" style={{ color }}>{value.toFixed(2)}</div>
                  <div className="h-2 rounded-full bg-kx-border mt-2 overflow-hidden">
                    <div className="h-full rounded-full transition-all duration-1000"
                      style={{ width: `${value * 100}%`, background: color }} />
                  </div>
                </div>
              ))}
            </div>

            {/* Verdict Badge */}
            <div className="text-center">
              <span className="inline-block px-6 py-2 rounded-full text-lg font-extrabold border-2"
                style={{ borderColor: "#FFD700", color: "#FFD700", background: "#FFD70010" }}>
                VERDICT: {debate.judge.verdict.toUpperCase()}
              </span>
              <div className="text-sm text-kx-body mt-2">{debate.judge.action}</div>
            </div>

            {/* Reasoning */}
            <div className="bg-kx-bg rounded-lg p-4 border border-kx-border">
              <div className="text-xs text-kx-muted font-bold mb-2 uppercase tracking-wider">Reasoning Chain</div>
              <pre className="whitespace-pre-wrap text-sm text-kx-body font-sans leading-relaxed">
                {debate.judge.reasoning}
              </pre>
            </div>
          </div>
        </div>
      )}

      {/* Evidence Summary Bar */}
      <div className="glass-card p-4">
        <div className="flex items-center gap-6 text-xs">
          <span className="text-kx-muted font-semibold">Evidence:</span>
          <span className="font-mono">TGN: <span className="text-[#FF3CAC] font-bold">0.847</span></span>
          <span className="font-mono">Bio: <span className="text-[#FFD700] font-bold">0.231</span></span>
          <span className="font-mono">APK: <span className="text-[#00FFD1] font-bold">0.156</span></span>
          <span className="font-mono">Velocity: <span className="text-[#FF6B35] font-bold">14 txn/h</span></span>
          <span className="font-mono">Entropy: <span className="text-[#FF3CAC] font-bold">1.18 bits</span></span>
          <span className="font-mono ml-auto">Rounds: <span className="text-kx-head font-bold">{debate.rounds.length}</span></span>
        </div>
      </div>
    </div>
  );
}
