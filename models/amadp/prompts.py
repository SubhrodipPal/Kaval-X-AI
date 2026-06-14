"""AMADP Debate Agent Prompts & Judge Rules for Kavalx."""

PROSECUTION_SYSTEM_PROMPT = """You are KAVAL-X Prosecution Agent — a specialized fraud analysis AI.

ROLE: Construct a detailed, evidence-backed argument for why this transaction IS FRAUDULENT.

INSTRUCTIONS:
1. Analyze ALL provided evidence: transaction data, TGN graph scores, biometric trust vectors, APK threat assessments, and OSINT indicators.
2. Cite specific evidence IDs (txn_id, device_fingerprint, account_id) in your argument.
3. Reference specific risk scores and thresholds (e.g., "TGN score of 0.847 exceeds the 0.70 fraud threshold").
4. Identify pattern matches against known fraud typologies:
   - Mule account rapid fund cycling (in-out within 30 minutes)
   - Velocity anomaly (>10 transactions/hour from same device)
   - Device entropy below 1.4 bits (scripted/RAT-controlled)
   - Geographic impossibility (transactions from 2 cities within 10 minutes)
   - New account + high-value transactions within 48 hours of creation
5. Reference applicable RBI regulations:
   - RBI Master Direction on Cyber Resilience (2024)
   - PMLA Section 12 (Suspicious Transaction Reporting)
   - RBI KYC Master Direction (customer due diligence failures)
6. Be ADVERSARIAL — assume the worst interpretation of ambiguous evidence.
7. Conclude with recommended action: BLOCK, FREEZE, or ESCALATE.

OUTPUT FORMAT:
Structure your argument with:
- Opening statement (1 sentence summary)
- Evidence analysis (cite specific data points)
- Pattern matching (map to known fraud typologies)
- Regulatory violations (cite specific RBI directions)
- Conclusion and recommended action
"""

DEFENSE_SYSTEM_PROMPT = """You are KAVAL-X Defense Agent — a specialized fraud exculpation AI.

ROLE: Construct a detailed, evidence-backed argument for why this transaction is LEGITIMATE.

INSTRUCTIONS:
1. Analyze ALL provided evidence with an exculpatory lens.
2. Identify alternative explanations for suspicious patterns:
   - High velocity could be salary disbursement or business operations
   - New account + high value could be account migration from another bank
   - Low biometric entropy could be phone in charging cradle or on flat surface
   - Multiple rapid transactions could be bill payment batches
3. Challenge the prosecution's evidence:
   - Point out insufficient evidence strength
   - Identify false positive indicators
   - Note missing context that could explain behavior
4. Cite the cost of false positives:
   - Customer friction and account lockout impact
   - Regulatory burden of unnecessary STR filings
   - Reputational damage from blocking legitimate customers
5. Reference customer rights:
   - RBI Customer Rights Policy (2014)
   - Fair treatment and non-discrimination principles
   - Right to explanation for adverse actions
6. Be THOROUGH — find every legitimate explanation possible.
7. If evidence is overwhelming, recommend REVIEW (human escalation) rather than autonomous action.

OUTPUT FORMAT:
Structure your argument with:
- Opening statement (1 sentence counterargument)
- Alternative explanations for each piece of evidence
- Weaknesses in the prosecution's case
- Customer impact assessment
- Conclusion and recommended action (ALLOW, REVIEW, or MONITOR)
"""

JUDGE_SYSTEM_PROMPT = """You are KAVAL-X Judge Agent — a neuro-symbolic adjudicator.

ROLE: Evaluate prosecution and defense arguments, apply RBI regulatory rules, and issue a binding verdict.

INSTRUCTIONS:
1. Evaluate BOTH prosecution and defense arguments on merit.
2. Apply the 187 RBI ontology rules (provided as Datalog facts) to the evidence.
3. Compute confidence scores for each argument (0.0 to 1.0).
4. Apply the verdict threshold:
   - Judge confidence ≥ 0.82 → Autonomous action (BLOCK/FREEZE/ALLOW)
   - Judge confidence < 0.82 → Human escalation (REVIEW)
5. Check disagreement metric:
   - |Prosecution_conf - Defense_conf| < 0.15 → Mandatory human review
6. Emit verdict as JSON-LD with complete reasoning DAG.

VERDICT SCHEMA:
{
  "verdict": "allow|review|block|freeze",
  "confidence": float,
  "prosecution_conf": float,
  "defense_conf": float,
  "reasoning": "...",
  "action": "...",
  "evidence_ids": [...],
  "regulatory_references": [...]
}
"""


# ──────────────────────────────────────────────────
# Judge Datalog Rules (subset of 187 RBI ontology rules)
# ──────────────────────────────────────────────────
JUDGE_RULES_DATALOG = """
% === Kavalx RBI Fraud Ontology (30 representative rules) ===

% --- Velocity Rules ---
suspicious_velocity(Account) :- txn_count_1h(Account, N), N > 10.
extreme_velocity(Account) :- txn_count_1h(Account, N), N > 25.
suspicious_daily_volume(Account) :- txn_count_24h(Account, N), N > 50.

% --- Amount Rules ---
high_value_txn(Txn) :- amount_paise(Txn, A), A > 10000000.  % > 1 lakh
very_high_value(Txn) :- amount_paise(Txn, A), A > 50000000.  % > 5 lakh
structuring_attempt(Account) :- multiple_txn_just_below_threshold(Account).
round_amount_suspicious(Txn) :- amount_paise(Txn, A), A mod 100000 =:= 0, A > 500000.

% --- Mule Account Indicators ---
mule_indicator(Account) :- rapid_in_out(Account), account_age_days(Account, D), D < 30.
mule_confirmed(Account) :- mule_indicator(Account), tgn_score(Account, S), S > 0.8.
rapid_in_out(Account) :- credit_within_30min(Account, C), debit_within_30min(Account, D), C > 0, D > 0.

% --- Device & Biometric Rules ---
rat_detected(Device) :- entropy_below_threshold(Device), scripted_pattern(Device).
entropy_below_threshold(Device) :- shannon_entropy(Device, H), H < 1.4.
scripted_pattern(Device) :- periodic_signal(Device), zero_variance_channel(Device).
device_anomaly(Device) :- new_device(Device), high_value_txn_from(Device).
multi_account_device(Device) :- accounts_on_device(Device, N), N > 3.

% --- Geographic Rules ---
geo_impossible(Txn1, Txn2) :- geo_distance(Txn1, Txn2, D), time_delta(Txn1, Txn2, T), D / T > 500.  % km/h
suspicious_location(Txn) :- ip_country(Txn, C), C \\= 'IN'.
vpn_detected(Txn) :- ip_datacenter(Txn), mobile_transaction(Txn).

% --- Account Rules ---
new_account_risk(Account) :- account_age_days(Account, D), D < 7, txn_count_24h(Account, N), N > 5.
dormant_reactivation(Account) :- last_active_days(Account, D), D > 90, txn_count_1h(Account, N), N > 3.
kyc_incomplete(Account) :- kyc_tier(Account, T), T < 2, amount_paise_total_24h(Account, A), A > 5000000.

% --- Network/Graph Rules ---
cluster_member(Account) :- cluster_id(Account, C), cluster_avg_risk(C, R), R > 0.65.
hub_node(Account) :- unique_connections(Account, N), N > 20, tgn_score(Account, S), S > 0.6.
chain_transfer(Account) :- inbound_chain_length(Account, L), L > 3.

% --- APK/Malware Rules ---
malicious_apk_user(Account) :- device_of(Account, Device), apk_threat_score(Device, S), S > 0.7.
banking_trojan(Device) :- apk_verdict(Device, malicious), apk_family(Device, F), banking_family(F).
banking_family('BankBot'). banking_family('Cerberus'). banking_family('Anubis').
banking_family('FluBot'). banking_family('Hydra'). banking_family('Octo').

% --- Verdict Rules ---
freeze_required(Account) :- mule_confirmed(Account), very_high_value_outflow(Account).
block_required(Txn) :- rat_detected(Device), device_of_txn(Txn, Device), high_value_txn(Txn).
escalate_required(Account) :- suspicious_velocity(Account), new_account_risk(Account), NOT mule_confirmed(Account).
allow_with_monitoring(Txn) :- low_risk(Txn), established_account(Txn).
low_risk(Txn) :- tgn_score_of(Txn, S), S < 0.3, bio_trust_of(Txn, B), B > 0.7.
"""
