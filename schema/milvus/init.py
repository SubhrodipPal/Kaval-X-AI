"""
Kavalx Advanced Fraud Detection & Banking Security
Milvus Vector Database Initialization

Creates two collections:
  - apk_embeddings: 768-dim vectors for APK similarity search (IVF_FLAT)
  - fraud_patterns:  768-dim vectors for fraud pattern matching (HNSW)

Usage:
    python schema/milvus/init.py

Environment:
    MILVUS_HOST  (default: localhost)
    MILVUS_PORT  (default: 19530)
"""

from __future__ import annotations

import logging
import os
import sys
import time

from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusException,
    connections,
    utility,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("kavalx.milvus_init")

# ── Configuration ──────────────────────────────────────────
MILVUS_HOST: str = os.getenv("MILVUS_HOST", "localhost")
MILVUS_PORT: str = os.getenv("MILVUS_PORT", "19530")
EMBEDDING_DIM: int = 768
MAX_CONNECT_RETRIES: int = 10
RETRY_DELAY_SECONDS: float = 3.0


def connect_to_milvus() -> None:
    """Establish connection to Milvus with retry logic."""
    for attempt in range(1, MAX_CONNECT_RETRIES + 1):
        try:
            connections.connect(
                alias="default",
                host=MILVUS_HOST,
                port=MILVUS_PORT,
            )
            logger.info(
                "Connected to Milvus at %s:%s (attempt %d)",
                MILVUS_HOST,
                MILVUS_PORT,
                attempt,
            )
            return
        except MilvusException as exc:
            logger.warning(
                "Connection attempt %d/%d failed: %s",
                attempt,
                MAX_CONNECT_RETRIES,
                exc,
            )
            if attempt == MAX_CONNECT_RETRIES:
                raise
            time.sleep(RETRY_DELAY_SECONDS)


def create_apk_embeddings_collection() -> Collection:
    """Create the apk_embeddings collection with IVF_FLAT index.

    Schema:
        id            INT64   – auto-generated primary key
        apk_sha256    VARCHAR – SHA-256 hex digest of the APK
        embedding     FLOAT_VECTOR(768) – APK feature embedding
        malware_family VARCHAR – predicted malware family label
        first_seen    INT64   – Unix epoch timestamp of first submission
    """
    collection_name = "apk_embeddings"

    if utility.has_collection(collection_name):
        logger.info("Collection '%s' already exists, skipping creation.", collection_name)
        return Collection(collection_name)

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True,
            description="Auto-generated primary key",
        ),
        FieldSchema(
            name="apk_sha256",
            dtype=DataType.VARCHAR,
            max_length=64,
            description="SHA-256 hex digest of the APK binary",
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIM,
            description="768-dim APK feature embedding",
        ),
        FieldSchema(
            name="malware_family",
            dtype=DataType.VARCHAR,
            max_length=50,
            description="Predicted malware family label",
        ),
        FieldSchema(
            name="first_seen",
            dtype=DataType.INT64,
            description="Unix epoch timestamp of first submission",
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="APK embeddings for malware similarity search",
    )

    collection = Collection(
        name=collection_name,
        schema=schema,
        consistency_level="Bounded",
    )

    # IVF_FLAT index on the embedding field
    index_params = {
        "index_type": "IVF_FLAT",
        "metric_type": "COSINE",
        "params": {"nlist": 1024},
    }
    collection.create_index(
        field_name="embedding",
        index_params=index_params,
        index_name="idx_apk_embedding_ivf_flat",
    )

    logger.info(
        "Created collection '%s' with IVF_FLAT index (nlist=1024, COSINE).",
        collection_name,
    )
    return collection


def create_fraud_patterns_collection() -> Collection:
    """Create the fraud_patterns collection with HNSW index.

    Schema:
        id           INT64   – auto-generated primary key
        pattern_desc VARCHAR – human-readable fraud pattern description
        embedding    FLOAT_VECTOR(768) – pattern embedding
        source       VARCHAR – data source identifier
        severity     INT8    – severity level (0-255)
    """
    collection_name = "fraud_patterns"

    if utility.has_collection(collection_name):
        logger.info("Collection '%s' already exists, skipping creation.", collection_name)
        return Collection(collection_name)

    fields = [
        FieldSchema(
            name="id",
            dtype=DataType.INT64,
            is_primary=True,
            auto_id=True,
            description="Auto-generated primary key",
        ),
        FieldSchema(
            name="pattern_desc",
            dtype=DataType.VARCHAR,
            max_length=500,
            description="Human-readable fraud pattern description",
        ),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=EMBEDDING_DIM,
            description="768-dim fraud pattern embedding",
        ),
        FieldSchema(
            name="source",
            dtype=DataType.VARCHAR,
            max_length=50,
            description="Data source identifier (e.g. RBI-bulletin, OSINT, MISP)",
        ),
        FieldSchema(
            name="severity",
            dtype=DataType.INT8,
            description="Severity level: 0=info, 1=low, 2=medium, 3=high, 4=critical",
        ),
    ]

    schema = CollectionSchema(
        fields=fields,
        description="Known fraud pattern embeddings for semantic similarity matching",
    )

    collection = Collection(
        name=collection_name,
        schema=schema,
        consistency_level="Bounded",
    )

    # HNSW index on the embedding field
    index_params = {
        "index_type": "HNSW",
        "metric_type": "COSINE",
        "params": {"M": 16, "efConstruction": 200},
    }
    collection.create_index(
        field_name="embedding",
        index_params=index_params,
        index_name="idx_fraud_pattern_embedding_hnsw",
    )

    logger.info(
        "Created collection '%s' with HNSW index (M=16, efConstruction=200, COSINE).",
        collection_name,
    )
    return collection


def main() -> None:
    """Entry point: connect to Milvus and initialize all collections."""
    logger.info("Starting Milvus schema initialization...")

    connect_to_milvus()

    apk_col = create_apk_embeddings_collection()
    fraud_col = create_fraud_patterns_collection()

    # Load collections into memory for immediate availability
    apk_col.load()
    fraud_col.load()

    logger.info("All Milvus collections created and loaded successfully.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        logger.exception("Milvus initialization failed.")
        sys.exit(1)
