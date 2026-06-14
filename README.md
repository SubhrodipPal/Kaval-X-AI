# Kavalx – Advanced Fraud Detection & Banking Security Platform

> Real-time, multi-modal fraud detection for India's digital payment ecosystem — combining Temporal Graph Networks, biometric behavioral analysis, adversarial APK scanning, and an AI-powered multi-agent tribunal system.

---

## 🏗️ Architecture Overview

Kavalx is composed of **9 microservices** orchestrated via Docker Compose, backed by a polyglot persistence layer and event-driven messaging:

| # | Service | Port | Description |
|---|---------|------|-------------|
| 1 | **API Gateway** | 8000 | Central entry point — JWT auth, rate-limiting, request routing |
| 2 | **Transaction Intelligence** | 8001 | TGN-based risk scoring, feature engineering, velocity checks |
| 3 | **APK Analysis** | 8002 | Static + dynamic + GenAI intent analysis of Android APKs |
| 4 | **Graph Intelligence** | 8003 | Memgraph-powered mule-account clustering, community detection |
| 5 | **Biometrics** | 8004 | Keystroke dynamics, PINN fusion, behavioral trust scoring |
| 6 | **AMADP** | 8005 | Adversarial Multi-Agent Debate Protocol — prosecutor/defender/judge tribunal |
| 7 | **OSINT** | 8006 | Dark-web monitoring, Telegram scraping, MISP integration |
| 8 | **Compliance** | 8007 | RBI rule engine (Soufflé Datalog), SAR generation, audit trail |
| 9 | **FL Coordinator** | 8008 | Federated learning orchestration across participating banks |

### Infrastructure Services

| Service | Technology | Purpose |
|---------|-----------|---------|
| PostgreSQL 16 | Relational DB | Accounts, transactions, verdicts, APK threats |
| Memgraph | Graph DB | Transaction graphs, device linkage, cluster detection |
| Redis 7 | Cache / Pub-Sub | Session cache, rate limiting, distributed locks |
| Kafka (Confluent 7.6) | Event streaming | 8 topics for real-time event pipelines |
| Milvus 2.4 | Vector DB | APK embeddings, fraud pattern similarity search |
| MinIO | Object storage | Milvus backend, APK binaries, model artifacts |

```
┌──────────────┐     ┌───────────────────────────────────────────────────┐
│   Clients    │────▶│  API Gateway (8000)                               │
└──────────────┘     └─────┬───────┬────────┬───────┬───────┬───────────┘
                           │       │        │       │       │
              ┌────────────┘  ┌────┘   ┌────┘  ┌────┘  ┌────┘
              ▼               ▼        ▼       ▼       ▼
        ┌──────────┐  ┌──────────┐  ┌─────┐  ┌─────┐  ┌──────┐
        │ Txn Intel│  │APK Analy.│  │Graph│  │ Bio │  │AMADP │
        │  (8001)  │  │  (8002)  │  │(8003│  │(8004│  │(8005)│
        └────┬─────┘  └────┬─────┘  └──┬──┘  └──┬──┘  └──┬───┘
             │              │           │        │        │
        ─────┴──────────────┴───────────┴────────┴────────┴─────
                              Kafka (9092)
        ────────────────────────────────────────────────────────
             │              │           │        │        │
        ┌────┴────┐   ┌─────┴────┐  ┌──┴───┐  ┌─┴──┐  ┌─┴──┐
        │Postgres │   │  Milvus  │  │Memgr.│  │Redis│  │MinIO│
        │ (5432)  │   │ (19530)  │  │(7687)│  │(6379│  │(9000│
        └─────────┘   └──────────┘  └──────┘  └────┘  └─────┘
```

---

## 🚀 Quick Start

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) ≥ 24.0
- [Docker Compose](https://docs.docker.com/compose/) ≥ 2.20
- GNU Make (optional, for `make` targets)

### 1. Clone & Configure

```bash
git clone https://github.com/your-org/kavalx.git
cd kavalx

# Create your environment file
cp .env.example .env
# Edit .env — set JWT_SECRET, API_KEY_SALT, and any external service keys
```

### 2. Start the Stack

```bash
# Using Make
make up

# Or directly
docker compose up -d --build
```

### 3. Create Kafka Topics

```bash
docker exec -it kavalx-kafka bash /scripts/create-topics.sh
# Or copy and run:
docker cp infra/kafka/create-topics.sh kavalx-kafka:/scripts/create-topics.sh
docker exec kavalx-kafka bash /scripts/create-topics.sh
```

### 4. Initialize Milvus Collections

```bash
pip install pymilvus
python schema/milvus/init.py
```

### 5. Verify

```bash
# Check all services are healthy
docker compose ps

# View logs
make logs

# Run tests
make test
```

---

## 🛠️ Technology Stack

| Layer | Technologies |
|-------|-------------|
| **Languages** | Python 3.11+, TypeScript, Cypher, SQL, Datalog |
| **ML/DL** | PyTorch, TorchServe, TFLite, vLLM, SHAP |
| **Databases** | PostgreSQL 16, Memgraph, Redis 7, Milvus 2.4 |
| **Messaging** | Apache Kafka (Confluent 7.6) |
| **Frontend** | Next.js 14, React, TailwindCSS |
| **Security** | Dilithium PQC signatures, Hyperledger Fabric, JWT |
| **NLP** | IndicTrans (multilingual), vLLM (AMADP reasoning) |
| **Compliance** | Soufflé Datalog, RBI ontology rules |
| **OSINT** | Tor, Telegram API, MISP threat feeds |

---

## 📁 Project Structure

```
kavalx/
├── docker-compose.yml          # Full dev stack
├── Makefile                    # Build / dev targets
├── .env.example                # Environment template
├── schema/
│   ├── postgres/init.sql       # PostgreSQL DDL
│   ├── memgraph/init.cypher    # Memgraph indexes & constraints
│   └── milvus/init.py          # Milvus collection setup
├── infra/
│   └── kafka/create-topics.sh  # Kafka topic provisioning
├── services/
│   ├── shared/                 # Shared Python library
│   │   ├── config.py           # Pydantic settings
│   │   ├── models.py           # Canonical data models
│   │   ├── auth.py             # JWT utilities
│   │   ├── kafka_utils.py      # Kafka producer/consumer
│   │   └── redis_utils.py      # Redis helpers
│   ├── gateway/                # API Gateway service
│   ├── transaction_intelligence/
│   ├── apk_analysis/
│   ├── graph_intelligence/
│   ├── biometrics/
│   ├── amadp/
│   ├── osint/
│   ├── compliance/
│   └── fl_coordinator/
└── frontend/                   # Next.js dashboard
```

---

## 🧪 Development

```bash
# Run all tests
make test

# View service logs
make logs

# Rebuild a single service
docker compose build txn-intelligence
docker compose up -d txn-intelligence

# Database migration
make migrate

# Clean up everything
make clean
```

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

<p align="center">
  Built with ❤️ for a safer digital India
</p>
