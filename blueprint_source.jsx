import { useState } from "react";

// ─────────────────────────────────────────────
// DATA
// ─────────────────────────────────────────────

const C = {
  bg: "#03070F",
  surface: "#07111F",
  border: "#0F2035",
  border2: "#1A3050",
  teal: "#00FFD1",
  purple: "#7B61FF",
  orange: "#FF6B35",
  gold: "#FFD700",
  pink: "#FF3CAC",
  blue: "#00C9FF",
  muted: "#4A6880",
  body: "#A8BECE",
  head: "#E2EDF7",
};

const SERVICES = [
  { id: "gw", name: "API Gateway", tech: "FastAPI + Nginx", port: 8000, color: C.teal, desc: "Auth (JWT/mTLS), rate limiting, request routing, WebSocket upgrade, OpenTelemetry tracing" },
  { id: "tis", name: "Transaction Intelligence", tech: "FastAPI + Kafka Consumer", port: 8001, color: C.blue, desc: "Ingest UPI/IMPS/NEFT events, feature extraction, publish to scoring queue" },
  { id: "apk", name: "APK Analysis", tech: "FastAPI + Celery", port: 8002, color: C.orange, desc: "Static analysis, dynamic sandbox execution, GenAI deobfuscation, intent extraction" },
  { id: "gis", name: "Graph Intelligence", tech: "FastAPI + PyG", port: 8003, color: C.purple, desc: "TGN inference, causal counterfactuals, mule cluster detection, hyperedge discovery" },
  { id: "bio", name: "Biometrics Engine", tech: "FastAPI + TFLite", port: 8004, color: C.gold, desc: "PINN sensor analysis, keystroke dynamics, entropy scoring, context trust vector" },
  { id: "amd", name: "AMADP Orchestrator", tech: "FastAPI + LangChain", port: 8005, color: C.pink, desc: "Multi-agent debate coordination, Neuro-Symbolic adjudication, verdict emission" },
  { id: "osg", name: "OSINT Fusion", tech: "FastAPI + Scrapy", port: 8006, color: C.teal, desc: "Dark web monitoring, Telegram scanning, GitHub secret detection, STIX feed ingestion" },
  { id: "cmp", name: "Compliance Engine", tech: "FastAPI + ReportLab", port: 8007, color: C.blue, desc: "RBI/CERT-In report generation, IndicTrans2 translation, PQC signing, ledger anchoring" },
  { id: "fed", name: "FL Coordinator", tech: "FastAPI + Flower", port: 8008, color: C.orange, desc: "Homomorphic gradient aggregation, ZK-proof verification, differential privacy noise injection" },
];

const ML_MODELS = [
  {
    name: "Temporal Graph Neural Network (TGN)",
    file: "models/tgn/",
    color: C.purple,
    purpose: "Real-time mule account detection and fraud ring discovery across UPI transaction graph",
    architecture: [
      { param: "Backbone", value: "DyRep variant (event-driven memory)" },
      { param: "Node embedding dim", value: "128" },
      { param: "Edge feature dim", value: "64 (amount_log, time_delta_enc, device_hash_emb)" },
      { param: "Memory module dim", value: "172" },
      { param: "Message function", value: "MLP(2×172 + 64 → 172)" },
      { param: "Memory updater", value: "GRUCell(172, 172)" },
      { param: "Message aggregator", value: "Last-message (streaming) / Mean (batch)" },
      { param: "Time encoder", value: "Time2Vec(1 → 64), learnable" },
      { param: "Graph attention layers", value: "2 layers, 4 heads each" },
      { param: "Link predictor", value: "MLP(172×2 → 128 → 64 → 1) + sigmoid" },
    ],
    training: [
      { param: "Dataset", value: "Synthetic UPI graph: 500K nodes, 5M edges, 2% fraud label" },
      { param: "Optimizer", value: "AdamW, lr=1e-4, weight_decay=1e-5" },
      { param: "Batch size", value: "512 temporal events" },
      { param: "Loss function", value: "BCEWithLogitsLoss + graph reg λ=0.01" },
      { param: "Class weights", value: "neg:pos = 49:1 (imbalanced)" },
      { param: "Epochs", value: "50 with early stopping (patience=7)" },
      { param: "Scheduler", value: "CosineAnnealingLR (T_max=50, η_min=1e-6)" },
      { param: "Negative sampling", value: "Temporal-aware: corrupt edges within ±5min window" },
    ],
    inference: [
      { param: "P99 latency target", value: "< 40ms per subgraph query" },
      { param: "Throughput", value: "10,000 TPS (Memgraph streaming)" },
      { param: "Memory footprint", value: "~850MB GPU / ~2.1GB CPU" },
      { param: "Serving", value: "TorchServe with gRPC, model versioned in MLflow" },
    ],
    metrics: [
      { metric: "AUC-ROC", target: "> 0.97" },
      { metric: "F1 (fraud class)", target: "> 0.91" },
      { metric: "Precision@K (K=100)", target: "> 0.88" },
      { metric: "False Positive Rate", target: "< 0.08%" },
      { metric: "Graph update lag", target: "< 100ms after event" },
    ],
    causal: "DoWhy CausalModel wraps TGN output. Counterfactual: 'Would node X still score > 0.7 if edge E is removed?' Uses linear SCM on graph neighborhoods. Reduces FPR by ~68% vs TGN alone."
  },
  {
    name: "Neuro-Symbolic Engine (NSE)",
    file: "models/nse/",
    color: C.teal,
    purpose: "Legally traceable fraud reasoning — neural perception bridged to symbolic rule engine",
    architecture: [
      { param: "Neural backbone", value: "Mistral-7B-Instruct-v0.3" },
      { param: "Fine-tuning method", value: "QLoRA (4-bit NF4 quantization)" },
      { param: "LoRA rank r", value: "16" },
      { param: "LoRA alpha", value: "32" },
      { param: "LoRA dropout", value: "0.05" },
      { param: "Target modules", value: "q_proj, k_proj, v_proj, o_proj, gate_proj" },
      { param: "Training data", value: "12K examples: RBI circulars, CERT-In advisories, fraud case narratives" },
      { param: "Symbolic engine", value: "py-datalog (Datalog subset of Prolog)" },
      { param: "Rule ontology", value: "187 rules from RBI Master Direction on Cyber Security 2023" },
      { param: "Bridge parser", value: "Custom NER → predicate extractor (spaCy + regex)" },
    ],
    training: [
      { param: "Base model VRAM", value: "~10GB (4-bit), ~24GB (16-bit)" },
      { param: "Training hardware", value: "2× A100 40GB or 4× RTX 3090" },
      { param: "Effective batch size", value: "32 (gradient accumulation steps=4, per_device=8)" },
      { param: "Learning rate", value: "2e-4 with warmup_ratio=0.03" },
      { param: "Epochs", value: "3 full passes over corpus" },
      { param: "Max seq length", value: "4096 tokens" },
      { param: "Loss", value: "Cross-entropy on next token prediction" },
    ],
    inference: [
      { param: "Quantization", value: "GGUF Q5_K_M via llama.cpp for CPU deployment" },
      { param: "GPU serving", value: "vLLM with PagedAttention, tensor_parallel_size=2" },
      { param: "Max new tokens", value: "1024 (reasoning chain)" },
      { param: "Temperature", value: "0.1 (deterministic fraud reasoning)" },
      { param: "P99 latency", value: "< 1.8s for full reasoning chain" },
    ],
    metrics: [
      { metric: "Rule coverage", target: "> 94% of known fraud patterns mapped to ontology" },
      { metric: "Reasoning faithfulness", target: "> 0.89 (FactScore vs RBI text)" },
      { metric: "Symbolic grounding rate", target: "> 87% propositions verified by rule engine" },
    ],
    causal: "Reasoning DAG emitted as JSON-LD graph. Each node: {proposition, confidence, source_rule, evidence_ids}. DAG stored in Neo4j for audit queries. Irreversibly hashed into PQC ledger."
  },
  {
    name: "PINN Biometrics (Physics-Informed Neural Net)",
    file: "models/pinn_bio/",
    color: C.gold,
    purpose: "Detect non-human device operation via physical law violations in sensor telemetry",
    architecture: [
      { param: "Input features", value: "6 channels: acc_x,y,z (m/s²) + gyro_x,y,z (rad/s)" },
      { param: "Sampling rate", value: "50Hz (20ms intervals)" },
      { param: "Window size", value: "100 timesteps = 2 seconds" },
      { param: "Stride", value: "25 timesteps = 500ms (75% overlap)" },
      { param: "Architecture", value: "BiLSTM(128) → Attention(64) → FC(32) → FC(1)" },
      { param: "Physics loss term 1", value: "||∫acc dt - v_estimated||² (velocity consistency)" },
      { param: "Physics loss term 2", value: "||acc_z - g·cos(θ)||² (gravity alignment, g=9.81)" },
      { param: "Physics loss term 3", value: "H(signal) > H_min (Shannon entropy ≥ 2.1 bits/sample)" },
      { param: "Total loss", value: "L_BCE + λ₁·L_physics1 + λ₂·L_physics2 + λ₃·L_entropy" },
      { param: "λ weights", value: "λ₁=0.3, λ₂=0.2, λ₃=0.5" },
    ],
    training: [
      { param: "Human data", value: "50K sessions from 3K users across 5 device models" },
      { param: "Synthetic (RAT) data", value: "20K sessions: scripted Accessibility Service automation" },
      { param: "Optimizer", value: "Adam, lr=3e-4" },
      { param: "Batch size", value: "256 windows" },
      { param: "Epochs", value: "80, early stopping patience=10" },
      { param: "Keystroke GMM", value: "Per-user Gaussian Mixture (K=3 components) on dwell/flight time" },
    ],
    inference: [
      { param: "On-device model", value: "TFLite FP16 quantized, < 1.8MB, < 15ms on mid-range Android" },
      { param: "Server model", value: "Full BiLSTM, < 8ms on CPU" },
      { param: "Entropy threshold", value: "Shannon H < 1.4 bits → synthetic flag" },
      { param: "Confidence fusion", value: "PINN score × GMM keystroke score (geometric mean)" },
    ],
    metrics: [
      { metric: "Human vs RAT AUC", target: "> 0.996" },
      { metric: "False human rejection (FRR)", target: "< 0.3%" },
      { metric: "RAT detection rate (TAR)", target: "> 99.1% @ FAR=0.1%" },
      { metric: "Synthetic signal entropy (mean)", target: "0.91 bits (vs human 3.4 bits)" },
    ],
    causal: "Entropy delta visualization served to analyst: side-by-side sensor replay plot with physics violation highlights. Judge-explainable: 'A human hand cannot produce a perfect 50Hz sine wave. This device is scripted.'"
  },
  {
    name: "APK Threat Classifier",
    file: "models/apk/",
    color: C.orange,
    purpose: "Detect banking trojans, RATs, overlay malware from APK static + dynamic analysis",
    architecture: [
      { param: "Stage 1 — Static", value: "Byte 4-gram TF-IDF (max_features=200K) + Permission graph GCN" },
      { param: "Stage 2 — Dynamic", value: "API call sequence LSTM(256) on 500-call window, trained in sandbox" },
      { param: "Stage 3 — GenAI", value: "Mistral deobfuscation: reconstruct intent from obfuscated DEX bytecode" },
      { param: "Meta-learner", value: "XGBoost (n_estimators=500, max_depth=6, eta=0.05)" },
      { param: "Feature vector", value: "[static_prob, dynamic_prob, gai_intent_score, permission_risk] = 4-dim" },
    ],
    training: [
      { param: "Benign samples", value: "50K APKs from Google Play (top 5K apps × 10 versions)" },
      { param: "Malicious samples", value: "18K: VirusTotal + AndroZoo + custom crawler" },
      { param: "Sandbox", value: "Cuckoo Sandbox on QEMU Android x86 emulator" },
      { param: "Execution timeout", value: "120s per APK, 500 API call capture limit" },
    ],
    inference: [
      { param: "Full analysis time", value: "< 28s (static 2s + dynamic 24s + GenAI 2s)" },
      { param: "Static-only fast path", value: "< 800ms for known-hash cache hit" },
    ],
    metrics: [
      { metric: "Detection rate", target: "> 97.5% on VirusShare dataset" },
      { metric: "False positive rate", target: "< 0.4% on benign corpus" },
      { metric: "Zero-day (synthetic variant)", target: "> 89% via GenAI intent classification" },
    ],
    causal: "SHAP values on XGBoost meta-learner explain which features drove the verdict. Top features always reported in AMADP prosecution argument."
  },
  {
    name: "AMADP — Adversarial Multi-Agent Debate Protocol",
    file: "models/amadp/",
    color: C.pink,
    purpose: "Adversarial prosecution/defense debate before final fraud verdict — eliminates silent false positives",
    architecture: [
      { param: "Prosecution Agent", value: "Mistral-7B (NSE fine-tune) + fraud-focused system prompt" },
      { param: "Defense Agent", value: "Mistral-7B (NSE fine-tune) + exculpatory-focused system prompt" },
      { param: "Judge Agent", value: "py-datalog Neuro-Symbolic Engine with RBI rule ontology" },
      { param: "Max debate rounds", value: "3 (each agent speaks once per round)" },
      { param: "Context window per agent", value: "Full transaction evidence pack + prior round transcripts" },
      { param: "Verdict threshold", value: "Judge confidence ≥ 0.82 → autonomous action; < 0.82 → human escalation" },
      { param: "Disagreement metric", value: "Prosecution_conf − Defense_conf < 0.15 → mandatory human review" },
      { param: "Output schema", value: "JSON-LD {verdict, confidence, reasoning_dag, evidence_ids, action, timestamp}" },
    ],
    training: [],
    inference: [
      { param: "Prosecution first turn", value: "~900ms" },
      { param: "Defense response", value: "~900ms" },
      { param: "Judge adjudication", value: "~120ms (symbolic + NSE)" },
      { param: "Total for 2 rounds", value: "< 4.2s end-to-end" },
      { param: "Streaming", value: "Server-Sent Events stream each agent token to frontend" },
    ],
    metrics: [
      { metric: "FP reduction vs single LLM", target: "> 71%" },
      { metric: "Verdict accuracy (labeled holdout)", target: "> 94%" },
      { metric: "Human escalation rate", target: "5–12% (tunable via threshold τ)" },
    ],
    causal: "Full debate transcript stored. Each argument node links back to transaction evidence_id, sensor reading_id, or graph_node_id. Complete audit trail from raw data → verdict in < 6 hops."
  },
];

const DB_SCHEMAS = [
  {
    name: "PostgreSQL — Core Relational",
    color: C.blue,
    tables: [
      {
        table: "accounts",
        fields: [
          "account_id UUID PK",
          "bank_code CHAR(4) NOT NULL",
          "upi_id VARCHAR(50) UNIQUE",
          "account_type ENUM(savings,current,wallet)",
          "kyc_tier SMALLINT DEFAULT 1",
          "risk_score FLOAT DEFAULT 0.5",
          "risk_updated_at TIMESTAMPTZ",
          "is_frozen BOOLEAN DEFAULT false",
          "created_at TIMESTAMPTZ",
          "metadata JSONB",
        ],
        indexes: ["idx_accounts_upi_id (unique)", "idx_accounts_bank_risk (bank_code, risk_score DESC)", "idx_accounts_frozen WHERE is_frozen=true"]
      },
      {
        table: "transactions",
        fields: [
          "txn_id UUID PK",
          "src_account UUID FK accounts",
          "dst_account UUID FK accounts",
          "amount_paise BIGINT NOT NULL",
          "rail ENUM(UPI,IMPS,NEFT,RTGS)",
          "initiated_at TIMESTAMPTZ",
          "settled_at TIMESTAMPTZ",
          "device_fingerprint VARCHAR(64)",
          "ip_hash VARCHAR(64)",
          "lat FLOAT, lon FLOAT",
          "tgn_risk_score FLOAT",
          "bio_trust_score FLOAT",
          "verdict ENUM(allow,review,block,freeze) DEFAULT allow",
          "verdict_id UUID FK verdicts",
        ],
        indexes: ["idx_txn_src_time (src_account, initiated_at DESC)", "idx_txn_verdict WHERE verdict IN ('review','block','freeze')", "idx_txn_device (device_fingerprint, initiated_at)"]
      },
      {
        table: "verdicts",
        fields: [
          "verdict_id UUID PK",
          "txn_id UUID FK transactions",
          "amadp_transcript JSONB NOT NULL",
          "reasoning_dag_id VARCHAR(64) FK neo4j",
          "prosecution_conf FLOAT",
          "defense_conf FLOAT",
          "judge_conf FLOAT",
          "final_action VARCHAR(20)",
          "pqc_signature BYTEA",
          "ledger_tx_id VARCHAR(128)",
          "created_at TIMESTAMPTZ",
          "analyst_override BOOLEAN DEFAULT false",
        ],
        indexes: ["idx_verdicts_txn (txn_id unique)", "idx_verdicts_action (final_action, created_at DESC)"]
      },
      {
        table: "apk_threats",
        fields: [
          "apk_id UUID PK",
          "sha256 CHAR(64) UNIQUE",
          "package_name VARCHAR(200)",
          "submitted_at TIMESTAMPTZ",
          "static_score FLOAT",
          "dynamic_score FLOAT",
          "genai_intent TEXT",
          "meta_score FLOAT",
          "verdict ENUM(benign,suspicious,malicious)",
          "shap_features JSONB",
          "sandbox_log_path TEXT",
        ],
        indexes: ["idx_apk_sha256 (unique)", "idx_apk_verdict_time (verdict, submitted_at DESC)"]
      },
    ]
  },
  {
    name: "Memgraph — Streaming Graph",
    color: C.purple,
    tables: [
      {
        table: "Node: Account",
        fields: [
          "id: String (UUID)",
          "bank_code: String",
          "upi_id: String",
          "risk_score: Float",
          "tgn_embedding: List[Float] (128-dim)",
          "last_txn_time: DateTime",
          "cluster_id: String (mule cluster label)",
          "is_mule: Boolean",
        ],
        indexes: ["INDEX ON :Account(id)", "INDEX ON :Account(risk_score)", "INDEX ON :Account(cluster_id)"]
      },
      {
        table: "Edge: TRANSFERRED",
        fields: [
          "txn_id: String",
          "amount_paise: Integer",
          "rail: String",
          "timestamp: DateTime",
          "device_fp: String",
          "tgn_edge_score: Float",
        ],
        indexes: ["EDGE INDEX ON :TRANSFERRED(timestamp)", "EDGE INDEX ON :TRANSFERRED(tgn_edge_score)"]
      },
      {
        table: "Node: Device",
        fields: [
          "fingerprint: String",
          "os_version: String",
          "app_version: String",
          "imei_hash: String",
          "bio_trust_score: Float",
          "pinn_entropy_mean: Float",
          "first_seen: DateTime",
          "apk_threat_score: Float",
        ],
        indexes: ["INDEX ON :Device(fingerprint)"]
      },
      {
        table: "Mule Cluster Query (Cypher)",
        fields: [
          "MATCH p = (a:Account)-[:TRANSFERRED*2..5]->(b:Account)",
          "WHERE a.risk_score > 0.7",
          "AND ALL(n IN nodes(p) WHERE n.last_txn_time > datetime() - duration('PT1H'))",
          "WITH p, [n IN nodes(p) | n.risk_score] AS scores",
          "WHERE reduce(s=0, x IN scores | s+x)/size(scores) > 0.65",
          "RETURN p LIMIT 50",
        ],
        indexes: []
      }
    ]
  },
  {
    name: "Redis — Cache & Pub/Sub",
    color: C.teal,
    tables: [
      {
        table: "Key Patterns",
        fields: [
          "risk:acc:{account_id} → Float (TTL 300s)",
          "bio:device:{fingerprint} → JSON trust vector (TTL 60s)",
          "apk:hash:{sha256} → JSON verdict (TTL 86400s)",
          "session:{session_id} → JSON user session (TTL 900s)",
          "ratelimit:{ip}:{endpoint} → Integer counter (TTL 60s)",
          "darkweb:alert:{indicator_hash} → JSON alert (TTL 3600s)",
        ],
        indexes: []
      },
      {
        table: "Pub/Sub Channels",
        fields: [
          "kaval:txn:scored — published after TGN inference",
          "kaval:apk:detected — malicious APK confirmed",
          "kaval:verdict:final — AMADP verdict emitted",
          "kaval:alert:darkweb — OSINT threat signal",
          "kaval:account:freeze — freeze action executed",
        ],
        indexes: []
      }
    ]
  },
  {
    name: "Milvus — Vector Store",
    color: C.orange,
    tables: [
      {
        table: "Collection: apk_embeddings",
        fields: [
          "id: INT64 PK",
          "apk_sha256: VARCHAR(64)",
          "embedding: FLOAT_VECTOR(768) — from Mistral last hidden layer",
          "malware_family: VARCHAR(50)",
          "first_seen: INT64 (unix timestamp)",
          "INDEX: IVF_FLAT, nlist=1024, metric_type=COSINE",
          "SEARCH: top-k=10 similar malware families in < 5ms",
        ],
        indexes: []
      },
      {
        table: "Collection: fraud_patterns",
        fields: [
          "id: INT64 PK",
          "pattern_desc: VARCHAR(500)",
          "embedding: FLOAT_VECTOR(768)",
          "source: VARCHAR(50) (CERT-In / RBI / Honeypot)",
          "severity: TINYINT",
          "INDEX: HNSW, M=16, efConstruction=200",
        ],
        indexes: []
      }
    ]
  }
];

const API_ROUTES = [
  {
    service: "API Gateway :8000",
    color: C.teal,
    routes: [
      { method: "POST", path: "/v1/transaction/score", auth: "mTLS + JWT", latency: "< 200ms P99", body: "TransactionEvent", response: "ScoredTransaction" },
      { method: "POST", path: "/v1/apk/submit", auth: "JWT + API Key", latency: "< 30s", body: "APKUpload (multipart)", response: "APKThreatReport" },
      { method: "GET",  path: "/v1/account/{id}/risk", auth: "JWT", latency: "< 50ms", body: "—", response: "AccountRiskProfile" },
      { method: "WS",   path: "/v1/stream/transactions", auth: "JWT WS", latency: "realtime", body: "—", response: "StreamedTxnEvents" },
      { method: "WS",   path: "/v1/stream/amadp/{verdict_id}", auth: "JWT WS", latency: "realtime", body: "—", response: "DebateTranscriptStream" },
      { method: "POST", path: "/v1/verdict/{id}/override", auth: "JWT + ANALYST_ROLE", latency: "< 100ms", body: "AnalystOverride", response: "UpdatedVerdict" },
      { method: "GET",  path: "/v1/compliance/report/{id}", auth: "JWT + COMPLIANCE_ROLE", latency: "< 5s", body: "—", response: "PDF binary" },
    ]
  },
  {
    service: "Transaction Intelligence :8001",
    color: C.blue,
    routes: [
      { method: "POST", path: "/internal/txn/ingest", auth: "internal mTLS", latency: "< 20ms", body: "RawUPIEvent", response: "FeatureVector" },
      { method: "GET",  path: "/internal/txn/history/{account_id}", auth: "internal mTLS", latency: "< 30ms", body: "—", response: "TransactionHistory[30d]" },
      { method: "POST", path: "/internal/txn/batch-features", auth: "internal mTLS", latency: "< 500ms", body: "BatchTxnEvents[1000]", response: "BatchFeatureMatrix" },
    ]
  },
  {
    service: "Graph Intelligence :8003",
    color: C.purple,
    routes: [
      { method: "POST", path: "/internal/graph/score-node", auth: "internal mTLS", latency: "< 40ms", body: "NodeID + reachability_depth", response: "TGNScore + neighbors" },
      { method: "POST", path: "/internal/graph/causal-check", auth: "internal mTLS", latency: "< 200ms", body: "NodeID + EdgeID[]", response: "CounterfactualResult" },
      { method: "GET",  path: "/internal/graph/mule-clusters", auth: "internal mTLS", latency: "< 150ms", body: "—", response: "MuleCluster[]" },
      { method: "POST", path: "/internal/graph/add-edge", auth: "internal mTLS", latency: "< 10ms", body: "GraphEdgeEvent", response: "ACK" },
    ]
  },
];

const FRONTEND_COMPONENTS = [
  {
    name: "App Shell",
    file: "app/layout.tsx",
    tech: "Next.js 14 App Router",
    children: [
      { name: "AuthProvider", file: "components/auth/AuthProvider.tsx", desc: "JWT context, refresh token rotation, mTLS cert injection" },
      { name: "WebSocketProvider", file: "components/ws/WebSocketProvider.tsx", desc: "Single WS connection, channel multiplexing, auto-reconnect with exp. backoff" },
      { name: "ThemeProvider", file: "components/theme/ThemeProvider.tsx", desc: "Dark theme tokens, Tailwind config override" },
    ]
  },
  {
    name: "Transaction Graph View",
    file: "app/graph/page.tsx",
    tech: "Three.js + WebGL + React Three Fiber",
    children: [
      { name: "GraphCanvas3D", file: "components/graph/GraphCanvas3D.tsx", desc: "R3F Canvas, ForceGraph3D layout, 60fps WebGL render" },
      { name: "NodeRenderer", file: "components/graph/NodeRenderer.tsx", desc: "Account/Device/IP nodes with risk_score → color mapping, instanced mesh" },
      { name: "EdgeStream", file: "components/graph/EdgeStream.tsx", desc: "Subscribes to kaval:txn:scored channel, animates new edges with pulse effect" },
      { name: "ClusterOverlay", file: "components/graph/ClusterOverlay.tsx", desc: "Convex hull overlay on detected mule clusters" },
      { name: "GraphControls", file: "components/graph/GraphControls.tsx", desc: "Time slider (scrub through historical graph), risk filter, search" },
    ]
  },
  {
    name: "AMADP Debate View",
    file: "app/amadp/[verdictId]/page.tsx",
    tech: "SSE streaming + React",
    children: [
      { name: "DebateStage", file: "components/amadp/DebateStage.tsx", desc: "Split-screen prosecution/defense panels with streaming token display" },
      { name: "EvidencePanel", file: "components/amadp/EvidencePanel.tsx", desc: "Linked evidence cards (txn IDs, sensor readings, graph nodes) cited in arguments" },
      { name: "JudgeOutput", file: "components/amadp/JudgeOutput.tsx", desc: "Neuro-Symbolic verdict display with reasoning DAG visualization (D3 tree)" },
      { name: "AnalystActions", file: "components/amadp/AnalystActions.tsx", desc: "Override controls, freeze account, generate report buttons" },
    ]
  },
  {
    name: "Biometrics Monitor",
    file: "app/biometrics/page.tsx",
    tech: "Recharts + D3",
    children: [
      { name: "SensorReplayChart", file: "components/bio/SensorReplayChart.tsx", desc: "6-channel accelerometer/gyro time series with entropy band overlay" },
      { name: "EntropyGauge", file: "components/bio/EntropyGauge.tsx", desc: "Shannon entropy real-time gauge, red zone < 1.4 bits = synthetic" },
      { name: "KeystrokeDensity", file: "components/bio/KeystrokeDensity.tsx", desc: "GMM dwell/flight time density plot vs user's historical profile" },
    ]
  },
  {
    name: "Compliance Dashboard",
    file: "app/compliance/page.tsx",
    tech: "Next.js + ReportLab PDF preview",
    children: [
      { name: "ReportQueue", file: "components/compliance/ReportQueue.tsx", desc: "List of pending/generated RBI incident reports with status" },
      { name: "ReportPreview", file: "components/compliance/ReportPreview.tsx", desc: "Embedded PDF viewer of auto-generated reports" },
      { name: "LedgerAudit", file: "components/compliance/LedgerAudit.tsx", desc: "PQC-signed ledger entries with Hyperledger Fabric verification status" },
    ]
  },
  {
    name: "OSINT Threat Feed",
    file: "app/osint/page.tsx",
    tech: "WebSocket + Recharts",
    children: [
      { name: "ThreatFeed", file: "components/osint/ThreatFeed.tsx", desc: "Live feed of dark web, Telegram, GitHub alerts with severity badges" },
      { name: "IOCMap", file: "components/osint/IOCMap.tsx", desc: "Geolocation map of threat indicators (IP clusters, ASN distribution)" },
      { name: "EarlyWarning", file: "components/osint/EarlyWarning.tsx", desc: "'Hours until likely attack' countdown when matching credential bundle detected" },
    ]
  },
];

const INFRA = [
  {
    name: "Docker Compose (Dev)",
    color: C.teal,
    services: [
      "api-gateway: kavalx/gateway:latest — ports 8000:8000 — env: JWT_SECRET, REDIS_URL, KAFKA_BROKERS",
      "txn-intelligence: kavalx/tis:latest — ports 8001:8001 — env: PG_DSN, MEMGRAPH_URL, KAFKA_BROKERS",
      "graph-intelligence: kavalx/gis:latest — ports 8003:8003 — env: MEMGRAPH_URL, TORCHSERVE_URL",
      "amadp: kavalx/amadp:latest — ports 8005:8005 — env: VLLM_URL, DATALOG_RULES_PATH, PQC_KEY_PATH",
      "biometrics: kavalx/bio:latest — ports 8004:8004 — env: TFLITE_MODEL_PATH, REDIS_URL",
      "osint: kavalx/osint:latest — ports 8006:8006 — env: TOR_PROXY, TELEGRAM_API_ID, MISP_URL",
      "compliance: kavalx/compliance:latest — ports 8007:8007 — env: INDICTRANS_URL, FABRIC_PEER_URL, PQC_CERT",
      "postgres: postgres:16 — ports 5432 — volumes: pg_data — initdb: schema/init.sql",
      "memgraph: memgraph/memgraph-platform:latest — ports 7687,3000 — volumes: mg_data",
      "redis: redis:7-alpine — ports 6379 — cmd: --maxmemory 2gb --maxmemory-policy allkeys-lru",
      "kafka: confluentinc/cp-kafka:7.6 — ports 9092 — env: KAFKA_BROKER_ID=1",
      "milvus: milvusdb/milvus:v2.4 — ports 19530 — depends_on: etcd, minio",
      "torchserve: pytorch/torchserve:latest — ports 8080,8081 — volumes: model_store",
      "vllm: vllm/vllm-openai:latest — ports 8090 — gpu: all — model: /models/mistral-nse-lora",
      "frontend: node:20-alpine — ports 3000:3000 — cmd: npm run dev",
    ]
  },
  {
    name: "Kubernetes (Production)",
    color: C.purple,
    services: [
      "Namespace: kavalx-prod (hard multi-tenancy from kavalx-dev)",
      "HPA: api-gateway minReplicas=3 maxReplicas=20 targetCPU=60%",
      "HPA: graph-intelligence minReplicas=2 maxReplicas=10 targetLatency=40ms (custom metric)",
      "StatefulSet: postgres (3 nodes, Patroni HA, 500Gi SSD PV each)",
      "StatefulSet: memgraph (3 nodes, replication enabled, 200Gi PV)",
      "StatefulSet: kafka (3 brokers, replication.factor=3, min.insync.replicas=2)",
      "Deployment: vllm (1 pod, 2× NVIDIA A100 nodeSelector: gpu=a100)",
      "CronJob: fl-coordinator — schedule '0 2 * * *' (FL retrain at 2AM daily)",
      "NetworkPolicy: deny all ingress except api-gateway; services only talk via ClusterIP",
      "Secret: sealed-secrets (Bitnami) for JWT, PQC keys, DB passwords",
      "Ingress: NGINX with cert-manager (Let's Encrypt) + mTLS for bank connections",
      "ServiceMesh: Istio (mTLS between all services, distributed tracing)",
      "Monitoring: Prometheus + Grafana + Jaeger + Loki (full observability stack)",
      "Cloud: MeitY empaneled sovereign cloud (NIC Cloud / RailTel / BSNL) for data residency",
    ]
  },
  {
    name: "Kafka Topics",
    color: C.orange,
    services: [
      "kaval.txn.raw — partitions=12, retention=24h, key=src_account_id",
      "kaval.txn.features — partitions=12, retention=6h, key=txn_id",
      "kaval.txn.scored — partitions=12, retention=48h, key=txn_id",
      "kaval.apk.submitted — partitions=4, retention=72h, key=apk_sha256",
      "kaval.verdict.final — partitions=8, retention=90d, key=verdict_id (compliance retention)",
      "kaval.alert.osint — partitions=4, retention=7d, key=indicator_hash",
      "kaval.graph.events — partitions=24, retention=2h, key=account_id (high-throughput)",
      "kaval.fl.gradients — partitions=4, retention=1h, encrypted=true, key=bank_id",
    ]
  }
];

const TIMELINE = [
  { week: "Week 1–2", phase: "Infrastructure & Data Pipelines", color: C.teal, tasks: [
    "Docker Compose full stack up: PG, Memgraph, Redis, Kafka, Milvus",
    "Schema migration: apply all SQL DDL, Memgraph indexes, Milvus collections",
    "Kafka producer: UPI transaction simulator (Faker-India, 200 TPS)",
    "Feature engineering pipeline: TIS service ingesting raw events → feature vectors",
    "Memgraph streaming: graph edge writer from Kafka topic",
    "Basic API Gateway: routing, JWT auth, health checks",
  ]},
  { week: "Week 3–4", phase: "TGN + Graph Intelligence", color: C.purple, tasks: [
    "Generate synthetic fraud graph dataset (500K nodes, 5M edges, 2% fraud)",
    "Implement TGN with PyTorch Geometric (DyRep backbone)",
    "Train TGN: 50 epochs, monitor AUC-ROC target > 0.97",
    "Integrate DoWhy causal inference wrapper on TGN output",
    "Deploy TGN via TorchServe, wire into Graph Intelligence service",
    "Mule cluster Cypher query + REST endpoint exposed",
    "Test: inject synthetic mule pattern, verify cluster detection < 100ms",
  ]},
  { week: "Week 5–6", phase: "NSE + AMADP", color: C.pink, tasks: [
    "Curate fine-tuning corpus: 12K RBI/CERT-In documents",
    "QLoRA fine-tune Mistral-7B (2× A100 or Colab A100 × overnight)",
    "Build py-datalog rule engine with 187 RBI ontology rules",
    "Build neural→symbolic bridge parser (spaCy NER + predicate extractor)",
    "Implement AMADP orchestrator: prosecution/defense/judge flow",
    "SSE streaming endpoint for debate transcript",
    "Test AMADP on 100 labeled fraud cases, measure FP reduction",
  ]},
  { week: "Week 7–8", phase: "APK Analysis + Biometrics", color: C.orange, tasks: [
    "Set up Cuckoo Sandbox on QEMU Android emulator",
    "Build static analyzer: byte 4-gram extractor + permission graph GCN",
    "Build dynamic analyzer: API call LSTM on sandbox traces",
    "Train XGBoost meta-learner, wire SHAP explanations",
    "Collect 70K sensor sessions (synthetic via script + human recordings)",
    "Train PINN BiLSTM with physics constraint losses",
    "Quantize to TFLite, verify < 1.8MB model size",
    "Build biometrics microservice, Context Trust Vector endpoint",
  ]},
  { week: "Week 9–10", phase: "OSINT + Compliance + PQC", color: C.blue, tasks: [
    "Scrapy + Tor crawler for dark web indicators (controlled test environment)",
    "Telethon Telegram channel monitor for fraud kit ads",
    "STIX/TAXII ingestion from CyberPeace Foundation feed",
    "IndicTrans2 integration for Hindi compliance report translation",
    "ReportLab RBI incident report template (maps to RBI Cyber Framework fields)",
    "CRYSTALS-Dilithium PQC signing implementation (liboqs Python binding)",
    "Hyperledger Fabric setup: 3-org network (simulate 3 banks)",
    "ZK-proof demo: snarkjs circuit for 'model trained on ≥3 banks without PII'",
  ]},
  { week: "Week 11–12", phase: "Frontend + Integration", color: C.gold, tasks: [
    "Next.js 14 app scaffold, Tailwind dark theme, WebSocket provider",
    "3D Transaction Graph: React Three Fiber + ForceGraph3D",
    "AMADP Debate View with SSE streaming panels",
    "Biometrics Monitor: sensor replay chart + entropy gauge",
    "Compliance Dashboard: report queue + PDF preview + ledger audit",
    "OSINT Threat Feed: live feed + early warning component",
    "End-to-end integration test: APK submitted → transaction scored → AMADP verdict → RBI report generated",
    "Load test: 10K TPS simulation, verify P99 < 200ms",
  ]},
  { week: "Week 13–14", phase: "FL + Hardening + Demo Prep", color: C.purple, tasks: [
    "Homomorphic FL: TenSEAL gradient encryption, Flower federated round",
    "Differential privacy: add Gaussian noise ε=0.5, δ=1e-5",
    "ZK-proof integration into FL coordinator",
    "Security hardening: mTLS everywhere, sealed secrets, network policies",
    "Kubernetes deployment to staging, smoke test all services",
    "Demo script run-through x3, time each section",
    "Prepare printed RBI report for physical handout to judges",
    "Final metrics collection: all KPIs green-lit",
  ]},
];

const METRICS = [
  { category: "Fraud Detection", color: C.teal, kpis: [
    { name: "True Positive Rate (Recall)", target: "> 95%", threshold: "Hard floor 92%" },
    { name: "Precision (fraud class)", target: "> 91%", threshold: "Hard floor 88%" },
    { name: "F1 Score", target: "> 0.93", threshold: "Hard floor 0.90" },
    { name: "AUC-ROC (TGN)", target: "> 0.97", threshold: "Hard floor 0.95" },
    { name: "False Positive Rate", target: "< 0.08%", threshold: "Hard ceiling 0.15%" },
    { name: "AMADP FP Reduction vs baseline", target: "> 71%", threshold: "Target 60%" },
  ]},
  { category: "Latency SLAs", color: C.purple, kpis: [
    { name: "Transaction scoring (P50)", target: "< 80ms", threshold: "Alert > 120ms" },
    { name: "Transaction scoring (P99)", target: "< 200ms", threshold: "SLA breach > 500ms" },
    { name: "TGN inference (P99)", target: "< 40ms", threshold: "Alert > 80ms" },
    { name: "AMADP full debate (2 rounds)", target: "< 4.2s", threshold: "Alert > 6s" },
    { name: "APK full analysis", target: "< 28s", threshold: "SLA breach > 60s" },
    { name: "Compliance report generation", target: "< 60s", threshold: "Alert > 120s" },
    { name: "Graph edge write (Memgraph)", target: "< 10ms", threshold: "Alert > 30ms" },
  ]},
  { category: "Throughput", color: C.orange, kpis: [
    { name: "Transaction events/sec", target: "10,000 TPS sustained", threshold: "Min 5,000 TPS" },
    { name: "Graph edge writes/sec", target: "10,000 writes/sec", threshold: "Min 5,000/sec" },
    { name: "Kafka consumer lag", target: "< 500 messages", threshold: "Alert > 2,000" },
    { name: "Concurrent AMADP debates", target: "50 simultaneous", threshold: "Min 20 concurrent" },
    { name: "APK analyses/hour", target: "120 APKs/hr", threshold: "Min 60/hr" },
  ]},
  { category: "Biometrics", color: C.gold, kpis: [
    { name: "Human vs RAT AUC-ROC", target: "> 0.996", threshold: "Hard floor 0.990" },
    { name: "False Rejection Rate (FRR)", target: "< 0.3%", threshold: "Hard ceiling 0.5%" },
    { name: "Synthetic entropy detection", target: "> 99.1% TAR @ FAR=0.1%", threshold: "" },
    { name: "On-device model size", target: "< 1.8MB TFLite", threshold: "Hard ceiling 3MB" },
    { name: "On-device inference time", target: "< 15ms (mid-range Android)", threshold: "Hard ceiling 30ms" },
  ]},
  { category: "Privacy & Security", color: C.pink, kpis: [
    { name: "FL privacy budget (ε)", target: "ε = 0.5", threshold: "Hard ceiling ε = 1.0" },
    { name: "FL privacy delta (δ)", target: "δ = 1e-5", threshold: "Hard ceiling δ = 1e-4" },
    { name: "ZK-proof verification time", target: "< 3s (browser)", threshold: "Alert > 5s" },
    { name: "PQC signature verification", target: "< 5ms", threshold: "Alert > 20ms" },
    { name: "Data residency compliance", target: "100% India sovereign cloud", threshold: "Zero tolerance" },
    { name: "mTLS coverage", target: "100% inter-service", threshold: "Zero tolerance" },
  ]},
  { category: "System Reliability", color: C.blue, kpis: [
    { name: "API Gateway uptime", target: "99.95%", threshold: "SLA 99.9%" },
    { name: "Kafka message loss rate", target: "0%", threshold: "Zero tolerance" },
    { name: "DB backup RPO", target: "< 5 min", threshold: "Hard ceiling 15 min" },
    { name: "DB recovery RTO", target: "< 15 min", threshold: "Hard ceiling 30 min" },
    { name: "Model drift detection", target: "F1 drop > 2% triggers retrain alert", threshold: "" },
  ]},
];

// ─────────────────────────────────────────────
// COMPONENTS
// ─────────────────────────────────────────────

const Tag = ({ children, color }) => (
  <span style={{
    background: color + "18", border: `1px solid ${color}44`,
    color, borderRadius: 4, padding: "2px 8px",
    fontSize: 11, fontWeight: 700, letterSpacing: "0.5px", whiteSpace: "nowrap"
  }}>{children}</span>
);

const SectionHead = ({ label, color }) => (
  <div style={{ fontSize: 10, color, letterSpacing: "2.5px", fontWeight: 700, marginBottom: 10, textTransform: "uppercase" }}>
    ◈ {label}
  </div>
);

const Card = ({ children, style = {} }) => (
  <div style={{
    background: C.surface, border: `1px solid ${C.border}`,
    borderRadius: 10, overflow: "hidden", ...style
  }}>{children}</div>
);

// ─────────────────────────────────────────────
// TAB VIEWS
// ─────────────────────────────────────────────

function ArchView() {
  const [sel, setSel] = useState(0);
  const svc = SERVICES[sel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Service list */}
      <div style={{ width: 220, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {SERVICES.map((s, i) => (
          <div key={i} onClick={() => setSel(i)} style={{
            padding: "12px 16px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${s.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, color: sel === i ? s.color : C.muted, fontWeight: 700 }}>{s.name}</div>
            <div style={{ fontSize: 10, color: C.muted, marginTop: 2 }}>{s.tech}</div>
          </div>
        ))}
      </div>
      {/* Detail */}
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 20 }}>
          <Tag color={svc.color}>:{svc.port}</Tag>
          <div style={{ fontSize: 22, fontWeight: 800 }}>{svc.name}</div>
        </div>
        <div style={{ fontSize: 13, color: C.body, lineHeight: 1.8, marginBottom: 24 }}>{svc.desc}</div>
        {/* Architecture Diagram */}
        <Card style={{ padding: 20, marginBottom: 20 }}>
          <SectionHead label="Data Flow Position" color={svc.color} />
          <div style={{ fontFamily: "monospace", fontSize: 12, color: C.body, lineHeight: 2 }}>
            {svc.id === "gw" && <>Nginx (TLS terminate) → FastAPI (JWT verify) → Route → [Internal Services via gRPC]<br/>↕ WebSocket upgrade for /stream/* endpoints<br/>↕ OpenTelemetry span injection on every request</>}
            {svc.id === "tis" && <>Kafka Consumer (kaval.txn.raw) → Feature Extraction → PostgreSQL write<br/>→ Kafka Produce (kaval.txn.features) → Redis cache risk:acc:{"{id}"}<br/>Historical query: PG → return 30d transaction window</>}
            {svc.id === "apk" && <>POST /submit → MinIO store (APK binary) → Celery queue<br/>Worker 1: Static analyzer (4-gram + GCN) → static_score<br/>Worker 2: Cuckoo sandbox submit → poll result → dynamic_score<br/>Worker 3: Mistral deobfuscation → intent_score<br/>→ XGBoost meta-learner → verdict → PG write → Milvus embed</>}
            {svc.id === "gis" && <>TorchServe (TGN) gRPC call → node embedding<br/>Memgraph Cypher query → neighborhood subgraph<br/>DoWhy causal check → counterfactual result<br/>→ Return ScoredNode + CausalExplanation</>}
            {svc.id === "bio" && <>SDK POST sensor_stream (6ch × 100 timesteps)<br/>PINN TFLite (on-device) OR BiLSTM server-side<br/>Entropy calculation → Shannon H → synthetic flag<br/>GMM keystroke check → dwell/flight anomaly<br/>→ Context Trust Vector → Redis cache bio:device:{"{fp}"}</>}
            {svc.id === "amd" && <>Receive: TransactionEvidence{"{txn, tgn, bio, apk}"}  <br/>Round 1: Prosecution LLM (evidence → fraud argument)<br/>Round 1: Defense LLM (same evidence → exculpatory)<br/>Judge NSE: rule engine adjudicates<br/>Repeat max 3 rounds → Final verdict JSON-LD<br/>→ PQC sign → Hyperledger Fabric anchor → PG write<br/>→ SSE stream each token to frontend</>}
            {svc.id === "osg" && <>Tor crawler → dark web marketplaces (hourly)<br/>Telethon → Telegram fraud channels (realtime)<br/>truffleHog → GitHub org scan (daily)<br/>cabby → STIX/TAXII feed pull (every 6h)<br/>→ Deduplicate → Redis alert cache → Kafka kaval.alert.osint<br/>→ Match against active account IOC list</>}
            {svc.id === "cmp" && <>AMADP verdict JSON-LD → map to RBI Cyber Framework fields<br/>IndicTrans2 → Hindi translation of narrative<br/>ReportLab → populate PDF template → store MinIO<br/>CRYSTALS-Dilithium sign → Hyperledger Fabric anchor<br/>→ Return report_id + PDF binary</>}
            {svc.id === "fed" && <>Trigger: daily CronJob at 02:00 IST<br/>1. Broadcast training request to bank FL clients<br/>2. Receive TenSEAL-encrypted gradient updates<br/>3. ZK-proof verification per update<br/>4. Homomorphic aggregation (FedAvg on ciphertexts)<br/>5. Decrypt aggregated weights → update TGN<br/>6. MLflow log new model version → shadow deploy</>}
          </div>
        </Card>
      </div>
    </div>
  );
}

function MLView() {
  const [sel, setSel] = useState(0);
  const [tab, setTab] = useState("arch");
  const m = ML_MODELS[sel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 200, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {ML_MODELS.map((m, i) => (
          <div key={i} onClick={() => { setSel(i); setTab("arch"); }} style={{
            padding: "11px 14px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${m.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? m.color : C.muted, lineHeight: 1.4 }}>
              {m.name.split("(")[0].trim()}
            </div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ marginBottom: 20 }}>
          <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 4 }}>{m.name}</div>
          <div style={{ fontSize: 13, color: C.body }}>{m.purpose}</div>
          <div style={{ fontSize: 11, color: C.muted, fontFamily: "monospace", marginTop: 4 }}>📁 {m.file}</div>
        </div>
        <div style={{ display: "flex", gap: 6, marginBottom: 20, flexWrap: "wrap" }}>
          {["arch", "training", "inference", "metrics"].map(t => (
            m[t] && m[t].length > 0 && (
              <button key={t} onClick={() => setTab(t)} style={{
                background: tab === t ? m.color + "20" : C.surface,
                border: `1px solid ${tab === t ? m.color : C.border}`,
                color: tab === t ? m.color : C.muted,
                borderRadius: 6, padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer"
              }}>{t.charAt(0).toUpperCase() + t.slice(1)}</button>
            )
          ))}
          <button onClick={() => setTab("causal")} style={{
            background: tab === "causal" ? m.color + "20" : C.surface,
            border: `1px solid ${tab === "causal" ? m.color : C.border}`,
            color: tab === "causal" ? m.color : C.muted,
            borderRadius: 6, padding: "6px 14px", fontSize: 12, fontWeight: 600, cursor: "pointer"
          }}>XAI / Causal</button>
        </div>
        <Card>
          {tab !== "causal" && m[tab] && m[tab].map((row, i) => (
            <div key={i} style={{
              display: "flex", gap: 16, padding: "10px 20px",
              borderBottom: i < m[tab].length - 1 ? `1px solid ${C.border}` : "none",
              alignItems: "flex-start"
            }}>
              <div style={{ minWidth: 220, fontSize: 12, color: C.muted, fontFamily: "monospace", flexShrink: 0 }}>
                {row.param || row.metric}
              </div>
              <div style={{ fontSize: 13, color: C.head, fontFamily: "monospace" }}>
                {row.value || row.target || row.threshold}
              </div>
            </div>
          ))}
          {tab === "causal" && (
            <div style={{ padding: 20, fontSize: 13, color: C.body, lineHeight: 1.8 }}>{m.causal}</div>
          )}
        </Card>
      </div>
    </div>
  );
}

function BackendView() {
  const [sel, setSel] = useState(0);
  const svc = API_ROUTES[sel];
  const methods = { GET: C.teal, POST: C.blue, WS: C.purple, PUT: C.gold, DELETE: C.orange };
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 220, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {API_ROUTES.map((s, i) => (
          <div key={i} onClick={() => setSel(i)} style={{
            padding: "12px 16px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${s.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? s.color : C.muted }}>{s.service}</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 20 }}>{svc.service}</div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {svc.routes.map((r, i) => (
            <Card key={i} style={{ padding: "14px 18px" }}>
              <div style={{ display: "flex", gap: 12, alignItems: "center", marginBottom: 8, flexWrap: "wrap" }}>
                <Tag color={methods[r.method] || C.body}>{r.method}</Tag>
                <span style={{ fontFamily: "monospace", fontSize: 13, color: C.head }}>{r.path}</span>
                <Tag color={C.muted}>⏱ {r.latency}</Tag>
                <Tag color={C.purple}>🔐 {r.auth}</Tag>
              </div>
              <div style={{ display: "flex", gap: 20 }}>
                <div style={{ fontSize: 11, color: C.muted }}>Body: <span style={{ color: C.body, fontFamily: "monospace" }}>{r.body}</span></div>
                <div style={{ fontSize: 11, color: C.muted }}>Returns: <span style={{ color: C.body, fontFamily: "monospace" }}>{r.response}</span></div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function DBView() {
  const [sel, setSel] = useState(0);
  const [tsel, setTsel] = useState(0);
  const db = DB_SCHEMAS[sel];
  const table = db.tables[tsel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 200, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {DB_SCHEMAS.map((d, i) => (
          <div key={i} onClick={() => { setSel(i); setTsel(0); }} style={{
            padding: "12px 14px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${d.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? d.color : C.muted, lineHeight: 1.4 }}>{d.name}</div>
          </div>
        ))}
      </div>
      <div style={{ width: 180, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {db.tables.map((t, i) => (
          <div key={i} onClick={() => setTsel(i)} style={{
            padding: "10px 14px", cursor: "pointer",
            background: tsel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 600, color: tsel === i ? db.color : C.muted, fontFamily: "monospace" }}>{t.table}</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
        <div style={{ fontSize: 16, fontWeight: 800, fontFamily: "monospace", color: db.color, marginBottom: 20 }}>{table.table}</div>
        <Card style={{ marginBottom: 16 }}>
          <SectionHead label="Fields" color={db.color} />
          {table.fields.map((f, i) => (
            <div key={i} style={{ padding: "8px 20px", borderBottom: i < table.fields.length - 1 ? `1px solid ${C.border}` : "none" }}>
              <span style={{ fontFamily: "monospace", fontSize: 12, color: C.body }}>{f}</span>
            </div>
          ))}
        </Card>
        {table.indexes.length > 0 && (
          <Card>
            <SectionHead label="Indexes" color={db.color} />
            {table.indexes.map((idx, i) => (
              <div key={i} style={{ padding: "8px 20px", borderBottom: i < table.indexes.length - 1 ? `1px solid ${C.border}` : "none" }}>
                <span style={{ fontFamily: "monospace", fontSize: 12, color: C.muted }}>{idx}</span>
              </div>
            ))}
          </Card>
        )}
      </div>
    </div>
  );
}

function FrontendView() {
  const [sel, setSel] = useState(0);
  const comp = FRONTEND_COMPONENTS[sel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 200, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {FRONTEND_COMPONENTS.map((c, i) => (
          <div key={i} onClick={() => setSel(i)} style={{
            padding: "11px 14px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${C.teal}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? C.teal : C.muted }}>{comp === c ? c.name : c.name}</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 4 }}>{comp.name}</div>
        <div style={{ display: "flex", gap: 10, marginBottom: 20 }}>
          <Tag color={C.teal}>{comp.tech}</Tag>
          <Tag color={C.muted}>{comp.file}</Tag>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
          {comp.children.map((child, i) => (
            <Card key={i} style={{ padding: "16px 20px" }}>
              <div style={{ display: "flex", gap: 10, alignItems: "center", marginBottom: 6 }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: C.head }}>{child.name}</span>
                <Tag color={C.muted}>{child.file}</Tag>
              </div>
              <div style={{ fontSize: 13, color: C.body, lineHeight: 1.7 }}>{child.desc}</div>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}

function InfraView() {
  const [sel, setSel] = useState(0);
  const infra = INFRA[sel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 200, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {INFRA.map((s, i) => (
          <div key={i} onClick={() => setSel(i)} style={{
            padding: "12px 14px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${s.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? s.color : C.muted }}>{s.name}</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 20 }}>{infra.name}</div>
        <Card>
          {infra.services.map((s, i) => (
            <div key={i} style={{ padding: "10px 20px", borderBottom: i < infra.services.length - 1 ? `1px solid ${C.border}` : "none" }}>
              <span style={{ fontFamily: "monospace", fontSize: 12, color: C.body }}>{s}</span>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

function TimelineView() {
  const [open, setOpen] = useState(0);
  return (
    <div style={{ overflowY: "auto", height: "100%", padding: 28 }}>
      <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 24 }}>14-Week Build Timeline</div>
      <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
        {TIMELINE.map((t, i) => (
          <div key={i} style={{ border: `1px solid ${open === i ? t.color + "66" : C.border}`, borderRadius: 10, overflow: "hidden" }}>
            <div onClick={() => setOpen(open === i ? -1 : i)} style={{
              display: "flex", alignItems: "center", gap: 16, padding: "14px 20px",
              cursor: "pointer", background: open === i ? t.color + "10" : "transparent"
            }}>
              <Tag color={t.color}>{t.week}</Tag>
              <div style={{ fontSize: 14, fontWeight: 700, color: C.head }}>{t.phase}</div>
              <div style={{ marginLeft: "auto", color: C.muted, fontSize: 16 }}>{open === i ? "▲" : "▼"}</div>
            </div>
            {open === i && (
              <div style={{ padding: "4px 20px 16px 20px" }}>
                {t.tasks.map((task, j) => (
                  <div key={j} style={{ display: "flex", gap: 10, alignItems: "flex-start", padding: "6px 0", borderBottom: j < t.tasks.length - 1 ? `1px solid ${C.border}` : "none" }}>
                    <span style={{ color: t.color, fontSize: 13, marginTop: 1, flexShrink: 0 }}>→</span>
                    <span style={{ fontSize: 13, color: C.body, lineHeight: 1.6 }}>{task}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function MetricsView() {
  const [sel, setSel] = useState(0);
  const cat = METRICS[sel];
  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      <div style={{ width: 200, borderRight: `1px solid ${C.border}`, overflowY: "auto", padding: "12px 0", flexShrink: 0 }}>
        {METRICS.map((m, i) => (
          <div key={i} onClick={() => setSel(i)} style={{
            padding: "12px 14px", cursor: "pointer",
            borderLeft: sel === i ? `3px solid ${m.color}` : "3px solid transparent",
            background: sel === i ? "#0A1628" : "transparent"
          }}>
            <div style={{ fontSize: 11, fontWeight: 700, color: sel === i ? m.color : C.muted }}>{m.category}</div>
          </div>
        ))}
      </div>
      <div style={{ flex: 1, overflowY: "auto", padding: 28 }}>
        <div style={{ fontSize: 20, fontWeight: 800, marginBottom: 20 }}>{cat.category}</div>
        <Card>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 160px 160px", padding: "10px 20px", borderBottom: `1px solid ${C.border2}` }}>
            <div style={{ fontSize: 10, color: C.muted, fontWeight: 700, letterSpacing: "1.5px" }}>METRIC</div>
            <div style={{ fontSize: 10, color: cat.color, fontWeight: 700, letterSpacing: "1.5px" }}>TARGET</div>
            <div style={{ fontSize: 10, color: C.orange, fontWeight: 700, letterSpacing: "1.5px" }}>ALERT THRESHOLD</div>
          </div>
          {cat.kpis.map((kpi, i) => (
            <div key={i} style={{
              display: "grid", gridTemplateColumns: "1fr 160px 160px",
              padding: "12px 20px", borderBottom: i < cat.kpis.length - 1 ? `1px solid ${C.border}` : "none",
              alignItems: "center"
            }}>
              <div style={{ fontSize: 13, color: C.body }}>{kpi.name}</div>
              <div style={{ fontSize: 13, fontWeight: 700, color: cat.color, fontFamily: "monospace" }}>{kpi.target}</div>
              <div style={{ fontSize: 12, color: kpi.threshold ? C.orange : C.muted, fontFamily: "monospace" }}>{kpi.threshold || "—"}</div>
            </div>
          ))}
        </Card>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// ROOT
// ─────────────────────────────────────────────

const TABS = [
  { id: "arch", label: "🏗 Services" },
  { id: "ml", label: "🧠 ML Models" },
  { id: "backend", label: "⚡ APIs" },
  { id: "db", label: "🗄 Databases" },
  { id: "frontend", label: "🖥 Frontend" },
  { id: "infra", label: "☁ Infra" },
  { id: "timeline", label: "📅 Timeline" },
  { id: "metrics", label: "📊 Metrics" },
];

export default function App() {
  const [tab, setTab] = useState("arch");
  return (
    <div style={{ height: "100vh", display: "flex", flexDirection: "column", background: C.bg, color: C.head, fontFamily: "'Inter','Segoe UI',sans-serif" }}>
      {/* Header */}
      <div style={{ borderBottom: `1px solid ${C.border}`, padding: "14px 24px", display: "flex", alignItems: "center", gap: 16, flexShrink: 0, background: C.surface }}>
        <div style={{ width: 30, height: 30, borderRadius: 7, background: `linear-gradient(135deg,${C.teal},${C.purple})`, display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 900, fontSize: 15, color: C.bg }}>K</div>
        <div>
          <div style={{ fontSize: 16, fontWeight: 800, letterSpacing: "-0.3px" }}>KAVAL-X <span style={{ color: C.teal }}>Technical Blueprint</span></div>
          <div style={{ fontSize: 10, color: C.muted, letterSpacing: "1.5px" }}>COMPLETE BUILD SPECIFICATION · IIT NATIONAL HACKATHON</div>
        </div>
        <div style={{ marginLeft: "auto", display: "flex", gap: 6 }}>
          {[C.teal, C.purple, C.orange, C.gold, C.pink].map((c, i) => (
            <div key={i} style={{ width: 6, height: 6, borderRadius: "50%", background: c }} />
          ))}
        </div>
      </div>
      {/* Tab Bar */}
      <div style={{ display: "flex", borderBottom: `1px solid ${C.border}`, flexShrink: 0, overflowX: "auto", background: C.surface }}>
        {TABS.map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            background: "none", border: "none", cursor: "pointer",
            padding: "11px 18px", fontSize: 12, fontWeight: 600, whiteSpace: "nowrap",
            color: tab === t.id ? C.teal : C.muted,
            borderBottom: tab === t.id ? `2px solid ${C.teal}` : "2px solid transparent",
          }}>{t.label}</button>
        ))}
      </div>
      {/* Content */}
      <div style={{ flex: 1, overflow: "hidden" }}>
        {tab === "arch" && <ArchView />}
        {tab === "ml" && <MLView />}
        {tab === "backend" && <BackendView />}
        {tab === "db" && <DBView />}
        {tab === "frontend" && <FrontendView />}
        {tab === "infra" && <InfraView />}
        {tab === "timeline" && <TimelineView />}
        {tab === "metrics" && <MetricsView />}
      </div>
    </div>
  );
}
