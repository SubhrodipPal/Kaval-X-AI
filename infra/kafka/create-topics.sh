#!/usr/bin/env bash
# ============================================================
# Kavalx Advanced Fraud Detection & Banking Security
# Kafka Topic Creation Script
# ============================================================
# Usage:
#   docker exec -it kavalx-kafka bash /scripts/create-topics.sh
#   OR
#   KAFKA_BOOTSTRAP=localhost:29092 bash infra/kafka/create-topics.sh
# ============================================================

set -euo pipefail

KAFKA_BOOTSTRAP="${KAFKA_BOOTSTRAP:-kafka:9092}"
KAFKA_BIN="${KAFKA_BIN:-/usr/bin/kafka-topics}"
REPLICATION_FACTOR="${REPLICATION_FACTOR:-1}"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

create_topic() {
    local topic="$1"
    local partitions="$2"
    local retention_ms="$3"

    log "Creating topic: ${topic} (partitions=${partitions}, retention=${retention_ms}ms)"

    if ${KAFKA_BIN} \
        --bootstrap-server "${KAFKA_BOOTSTRAP}" \
        --list 2>/dev/null | grep -qw "${topic}"; then
        log "  Topic '${topic}' already exists, updating config..."
        ${KAFKA_BIN} \
            --bootstrap-server "${KAFKA_BOOTSTRAP}" \
            --alter \
            --topic "${topic}" \
            --partitions "${partitions}" 2>/dev/null || true
    else
        ${KAFKA_BIN} \
            --bootstrap-server "${KAFKA_BOOTSTRAP}" \
            --create \
            --topic "${topic}" \
            --partitions "${partitions}" \
            --replication-factor "${REPLICATION_FACTOR}" \
            --config retention.ms="${retention_ms}" \
            --config cleanup.policy=delete \
            --if-not-exists
    fi

    log "  ✓ ${topic} ready"
}

# ── Helper: Convert human-readable retention to milliseconds ──
hours_to_ms()  { echo $(( $1 * 3600 * 1000 )); }
days_to_ms()   { echo $(( $1 * 86400 * 1000 )); }

log "============================================"
log "Kavalx Kafka Topic Provisioning"
log "Bootstrap: ${KAFKA_BOOTSTRAP}"
log "Replication Factor: ${REPLICATION_FACTOR}"
log "============================================"

# ── Raw transaction events from payment rails ──
create_topic "kaval.txn.raw"         12  "$(hours_to_ms 24)"

# ── Feature-engineered transaction vectors ──
create_topic "kaval.txn.features"    12  "$(hours_to_ms 6)"

# ── Scored transactions (TGN + biometric fusion) ──
create_topic "kaval.txn.scored"      12  "$(hours_to_ms 48)"

# ── APK binaries submitted for analysis ──
create_topic "kaval.apk.submitted"   4   "$(hours_to_ms 72)"

# ── Final AMADP tribunal verdicts ──
create_topic "kaval.verdict.final"   8   "$(days_to_ms 90)"

# ── OSINT / dark-web / Telegram alerts ──
create_topic "kaval.alert.osint"     4   "$(days_to_ms 7)"

# ── Graph mutation events (high-throughput) ──
create_topic "kaval.graph.events"    24  "$(hours_to_ms 2)"

# ── Federated learning gradient exchanges ──
create_topic "kaval.fl.gradients"    4   "$(hours_to_ms 1)"

log "============================================"
log "All 8 Kafka topics provisioned successfully."
log "============================================"

# ── Verify ──
log "Topic listing:"
${KAFKA_BIN} \
    --bootstrap-server "${KAFKA_BOOTSTRAP}" \
    --list \
    --exclude-internal 2>/dev/null | grep "^kaval\." | sort || true
