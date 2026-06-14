-- ============================================================
-- Kavalx Advanced Fraud Detection & Banking Security
-- PostgreSQL Schema Initialization
-- ============================================================
-- Run against: PostgreSQL 16+
-- Encoding:    UTF-8
-- ============================================================

BEGIN;

-- --------------------------------------------------------
-- Extensions
-- --------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- --------------------------------------------------------
-- Custom ENUM Types
-- --------------------------------------------------------
DO $$ BEGIN
    CREATE TYPE account_type_enum AS ENUM ('savings', 'current', 'wallet');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE rail_enum AS ENUM ('UPI', 'IMPS', 'NEFT', 'RTGS');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE verdict_enum AS ENUM ('allow', 'review', 'block', 'freeze');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE apk_verdict_enum AS ENUM ('benign', 'suspicious', 'malicious');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- --------------------------------------------------------
-- Table: accounts
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS accounts (
    account_id    UUID            PRIMARY KEY DEFAULT uuid_generate_v4(),
    bank_code     CHAR(4)         NOT NULL,
    upi_id        VARCHAR(50)     UNIQUE,
    account_type  account_type_enum,
    kyc_tier      SMALLINT        NOT NULL DEFAULT 1
                                  CHECK (kyc_tier BETWEEN 1 AND 4),
    risk_score    FLOAT           NOT NULL DEFAULT 0.5
                                  CHECK (risk_score >= 0.0 AND risk_score <= 1.0),
    risk_updated_at TIMESTAMPTZ,
    is_frozen     BOOLEAN         NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    metadata      JSONB           DEFAULT '{}'::jsonb
);

COMMENT ON TABLE  accounts IS 'Bank accounts participating in the Kavalx monitoring network.';
COMMENT ON COLUMN accounts.bank_code IS 'IFSC-prefix identifying the issuing bank (e.g. SBIN, HDFC).';
COMMENT ON COLUMN accounts.kyc_tier IS 'KYC verification level: 1=min-KYC, 2=full-KYC, 3=enhanced, 4=institutional.';
COMMENT ON COLUMN accounts.risk_score IS 'Composite risk score in [0,1]; 0=safest, 1=highest risk.';

-- Indexes for accounts
CREATE UNIQUE INDEX IF NOT EXISTS idx_accounts_upi_id
    ON accounts (upi_id);

CREATE INDEX IF NOT EXISTS idx_accounts_bank_risk
    ON accounts (bank_code, risk_score DESC);

CREATE INDEX IF NOT EXISTS idx_accounts_frozen
    ON accounts (account_id)
    WHERE is_frozen = true;

-- --------------------------------------------------------
-- Table: verdicts  (created before transactions for FK)
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS verdicts (
    verdict_id        UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    txn_id            UUID,         -- FK added after transactions table
    amadp_transcript  JSONB         NOT NULL DEFAULT '{}'::jsonb,
    reasoning_dag_id  VARCHAR(64),
    prosecution_conf  FLOAT         CHECK (prosecution_conf >= 0.0 AND prosecution_conf <= 1.0),
    defense_conf      FLOAT         CHECK (defense_conf >= 0.0 AND defense_conf <= 1.0),
    judge_conf        FLOAT         CHECK (judge_conf >= 0.0 AND judge_conf <= 1.0),
    final_action      VARCHAR(20)   NOT NULL,
    pqc_signature     BYTEA,
    ledger_tx_id      VARCHAR(128),
    created_at        TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    analyst_override  BOOLEAN       NOT NULL DEFAULT false
);

COMMENT ON TABLE  verdicts IS 'AMADP tribunal decisions: prosecution, defense, and judge confidence scores.';
COMMENT ON COLUMN verdicts.amadp_transcript IS 'Full JSON transcript of the AMADP multi-agent debate.';
COMMENT ON COLUMN verdicts.pqc_signature IS 'Post-quantum (Dilithium) signature over the verdict payload.';
COMMENT ON COLUMN verdicts.ledger_tx_id IS 'Hyperledger Fabric transaction ID anchoring this verdict on-chain.';

-- Indexes for verdicts
CREATE UNIQUE INDEX IF NOT EXISTS idx_verdicts_txn
    ON verdicts (txn_id);

CREATE INDEX IF NOT EXISTS idx_verdicts_action
    ON verdicts (final_action, created_at DESC);

-- --------------------------------------------------------
-- Table: transactions
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS transactions (
    txn_id            UUID          PRIMARY KEY DEFAULT uuid_generate_v4(),
    src_account       UUID          NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    dst_account       UUID          NOT NULL REFERENCES accounts(account_id) ON DELETE RESTRICT,
    amount_paise      BIGINT        NOT NULL CHECK (amount_paise > 0),
    rail              rail_enum     NOT NULL,
    initiated_at      TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    settled_at        TIMESTAMPTZ,
    device_fingerprint VARCHAR(64),
    ip_hash           VARCHAR(64),
    lat               FLOAT,
    lon               FLOAT,
    tgn_risk_score    FLOAT         CHECK (tgn_risk_score >= 0.0 AND tgn_risk_score <= 1.0),
    bio_trust_score   FLOAT         CHECK (bio_trust_score >= 0.0 AND bio_trust_score <= 1.0),
    verdict           verdict_enum  NOT NULL DEFAULT 'allow',
    verdict_id        UUID          REFERENCES verdicts(verdict_id) ON DELETE SET NULL
);

COMMENT ON TABLE  transactions IS 'Financial transactions across UPI/IMPS/NEFT/RTGS rails.';
COMMENT ON COLUMN transactions.amount_paise IS 'Transaction amount in paise (1 INR = 100 paise) for lossless integer arithmetic.';
COMMENT ON COLUMN transactions.tgn_risk_score IS 'Temporal Graph Network risk score for this transaction edge.';
COMMENT ON COLUMN transactions.bio_trust_score IS 'Biometric trust score (keystroke dynamics, PINN fusion).';

-- Indexes for transactions
CREATE INDEX IF NOT EXISTS idx_txn_src_time
    ON transactions (src_account, initiated_at DESC);

CREATE INDEX IF NOT EXISTS idx_txn_verdict
    ON transactions (verdict, initiated_at DESC)
    WHERE verdict IN ('review', 'block', 'freeze');

CREATE INDEX IF NOT EXISTS idx_txn_device
    ON transactions (device_fingerprint, initiated_at);

-- Add the FK from verdicts -> transactions now that both tables exist
ALTER TABLE verdicts
    ADD CONSTRAINT fk_verdicts_txn
    FOREIGN KEY (txn_id) REFERENCES transactions(txn_id) ON DELETE CASCADE;

-- --------------------------------------------------------
-- Table: apk_threats
-- --------------------------------------------------------
CREATE TABLE IF NOT EXISTS apk_threats (
    apk_id          UUID              PRIMARY KEY DEFAULT uuid_generate_v4(),
    sha256          CHAR(64)          NOT NULL UNIQUE,
    package_name    VARCHAR(200),
    submitted_at    TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    static_score    FLOAT             CHECK (static_score >= 0.0 AND static_score <= 1.0),
    dynamic_score   FLOAT             CHECK (dynamic_score >= 0.0 AND dynamic_score <= 1.0),
    genai_intent    TEXT,
    meta_score      FLOAT             CHECK (meta_score >= 0.0 AND meta_score <= 1.0),
    verdict         apk_verdict_enum  NOT NULL DEFAULT 'benign',
    shap_features   JSONB             DEFAULT '{}'::jsonb,
    sandbox_log_path TEXT
);

COMMENT ON TABLE  apk_threats IS 'APK malware analysis results from static, dynamic, and GenAI intent pipelines.';
COMMENT ON COLUMN apk_threats.sha256 IS 'SHA-256 hash of the APK binary (hex-encoded, lowercase).';
COMMENT ON COLUMN apk_threats.genai_intent IS 'LLM-generated natural-language summary of decompiled APK intent.';
COMMENT ON COLUMN apk_threats.shap_features IS 'SHAP feature-importance values explaining the verdict.';

-- Indexes for apk_threats
CREATE UNIQUE INDEX IF NOT EXISTS idx_apk_sha256
    ON apk_threats (sha256);

CREATE INDEX IF NOT EXISTS idx_apk_verdict_time
    ON apk_threats (verdict, submitted_at DESC);

-- --------------------------------------------------------
-- Trigger: auto-update risk_updated_at on accounts
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_update_risk_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.risk_score IS DISTINCT FROM OLD.risk_score THEN
        NEW.risk_updated_at := NOW();
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_accounts_risk_updated ON accounts;
CREATE TRIGGER trg_accounts_risk_updated
    BEFORE UPDATE ON accounts
    FOR EACH ROW
    EXECUTE FUNCTION fn_update_risk_timestamp();

-- --------------------------------------------------------
-- Trigger: prevent transactions on frozen accounts
-- --------------------------------------------------------
CREATE OR REPLACE FUNCTION fn_check_frozen_account()
RETURNS TRIGGER AS $$
BEGIN
    IF EXISTS (SELECT 1 FROM accounts WHERE account_id = NEW.src_account AND is_frozen = true) THEN
        RAISE EXCEPTION 'Source account % is frozen', NEW.src_account;
    END IF;
    IF EXISTS (SELECT 1 FROM accounts WHERE account_id = NEW.dst_account AND is_frozen = true) THEN
        RAISE EXCEPTION 'Destination account % is frozen', NEW.dst_account;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_check_frozen ON transactions;
CREATE TRIGGER trg_check_frozen
    BEFORE INSERT ON transactions
    FOR EACH ROW
    EXECUTE FUNCTION fn_check_frozen_account();

COMMIT;
