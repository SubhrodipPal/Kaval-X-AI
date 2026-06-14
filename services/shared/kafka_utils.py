"""
Kavalx Kafka Producer / Consumer Utilities
============================================

Thin wrappers around ``confluent-kafka`` providing:
  - ``KavalxProducer``: async-friendly producer with JSON serialization
  - ``KavalxConsumer``: consumer with automatic deserialization and
    configurable commit strategy

Usage:
    from services.shared.kafka_utils import KavalxProducer, KavalxConsumer

    producer = KavalxProducer()
    producer.send("kaval.txn.raw", event.model_dump())

    consumer = KavalxConsumer(
        topics=["kaval.txn.scored"],
        group_id="amadp-consumer",
    )
    for msg in consumer.consume_loop():
        process(msg)
"""

from __future__ import annotations

import json
import logging
import signal
import time
from typing import Any, Callable, Dict, List, Optional

from confluent_kafka import (
    Consumer,
    KafkaError,
    KafkaException,
    Message,
    Producer,
)
from confluent_kafka.admin import AdminClient, NewTopic

from services.shared.config import get_settings

logger = logging.getLogger(__name__)


# ── Serialization ──────────────────────────────────────────


def _json_serializer(data: Any) -> bytes:
    """Serialize a Python object to UTF-8 JSON bytes."""
    return json.dumps(data, default=str, ensure_ascii=False).encode("utf-8")


def _json_deserializer(raw: bytes) -> Any:
    """Deserialize UTF-8 JSON bytes to a Python object."""
    return json.loads(raw.decode("utf-8"))


# ── Producer ───────────────────────────────────────────────


class KavalxProducer:
    """High-level Kafka producer with JSON serialization and delivery reports.

    Args:
        extra_config: Additional ``confluent-kafka`` producer config overrides.
    """

    def __init__(self, extra_config: Optional[Dict[str, Any]] = None) -> None:
        settings = get_settings()
        config: Dict[str, Any] = {
            "bootstrap.servers": settings.kafka_brokers,
            "client.id": "kavalx-producer",
            "acks": "all",
            "retries": 5,
            "retry.backoff.ms": 300,
            "linger.ms": 10,
            "compression.type": "lz4",
            "enable.idempotence": True,
        }
        if extra_config:
            config.update(extra_config)

        self._producer = Producer(config)
        logger.info("KavalxProducer initialized (brokers=%s)", settings.kafka_brokers)

    @staticmethod
    def _delivery_callback(err: Optional[KafkaError], msg: Message) -> None:
        """Log delivery result for each message."""
        if err is not None:
            logger.error(
                "Message delivery failed: topic=%s err=%s",
                msg.topic(),
                err,
            )
        else:
            logger.debug(
                "Message delivered: topic=%s partition=%d offset=%d",
                msg.topic(),
                msg.partition(),
                msg.offset(),
            )

    def send(
        self,
        topic: str,
        value: Any,
        key: Optional[str] = None,
        headers: Optional[Dict[str, str]] = None,
        on_delivery: Optional[Callable] = None,
    ) -> None:
        """Produce a single message.

        Args:
            topic: Kafka topic name.
            value: Python object to serialize as JSON.
            key: Optional message key (string).
            headers: Optional message headers.
            on_delivery: Custom delivery callback; defaults to internal logger.
        """
        kafka_headers = (
            [(k, v.encode("utf-8")) for k, v in headers.items()] if headers else None
        )
        self._producer.produce(
            topic=topic,
            value=_json_serializer(value),
            key=key.encode("utf-8") if key else None,
            headers=kafka_headers,
            callback=on_delivery or self._delivery_callback,
        )
        self._producer.poll(0)

    def flush(self, timeout: float = 10.0) -> int:
        """Flush outstanding messages.

        Returns:
            Number of messages still in the queue (should be 0).
        """
        remaining = self._producer.flush(timeout)
        if remaining > 0:
            logger.warning("%d messages still in producer queue after flush", remaining)
        return remaining

    def close(self) -> None:
        """Flush and release resources."""
        self.flush()
        logger.info("KavalxProducer closed.")


# ── Consumer ───────────────────────────────────────────────


class KavalxConsumer:
    """High-level Kafka consumer with JSON deserialization.

    Args:
        topics: List of topic names to subscribe to.
        group_id: Consumer group identifier.
        auto_commit: Whether to enable auto-commit (default True).
        poll_timeout: Seconds to wait per poll() call.
        extra_config: Additional ``confluent-kafka`` consumer config.
    """

    def __init__(
        self,
        topics: List[str],
        group_id: str,
        auto_commit: bool = True,
        poll_timeout: float = 1.0,
        extra_config: Optional[Dict[str, Any]] = None,
    ) -> None:
        settings = get_settings()
        config: Dict[str, Any] = {
            "bootstrap.servers": settings.kafka_brokers,
            "group.id": group_id,
            "client.id": f"kavalx-{group_id}",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": auto_commit,
            "session.timeout.ms": 30000,
            "max.poll.interval.ms": 300000,
        }
        if extra_config:
            config.update(extra_config)

        self._consumer = Consumer(config)
        self._consumer.subscribe(topics)
        self._poll_timeout = poll_timeout
        self._running = True

        # Graceful shutdown on SIGINT/SIGTERM
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

        logger.info(
            "KavalxConsumer initialized (group=%s, topics=%s)",
            group_id,
            topics,
        )

    def _signal_handler(self, signum: int, frame: Any) -> None:
        logger.info("Received signal %d, shutting down consumer...", signum)
        self._running = False

    def consume_loop(self) -> Any:
        """Yield deserialized messages until shutdown.

        Yields:
            Deserialized Python objects from each consumed message.
        """
        try:
            while self._running:
                msg = self._consumer.poll(self._poll_timeout)
                if msg is None:
                    continue

                err = msg.error()
                if err:
                    if err.code() == KafkaError._PARTITION_EOF:
                        logger.debug(
                            "Reached end of partition: topic=%s partition=%d",
                            msg.topic(),
                            msg.partition(),
                        )
                        continue
                    raise KafkaException(err)

                try:
                    value = _json_deserializer(msg.value())
                    yield value
                except json.JSONDecodeError:
                    logger.error(
                        "Failed to deserialize message: topic=%s offset=%d",
                        msg.topic(),
                        msg.offset(),
                    )
                    continue
        finally:
            self.close()

    def commit(self) -> None:
        """Manually commit current offsets (when auto_commit=False)."""
        self._consumer.commit(asynchronous=False)

    def close(self) -> None:
        """Close the consumer and leave the group."""
        self._consumer.close()
        logger.info("KavalxConsumer closed.")


# ── Admin Helpers ──────────────────────────────────────────


def ensure_topics_exist(
    topic_configs: List[Dict[str, Any]],
) -> None:
    """Create Kafka topics if they do not already exist.

    Args:
        topic_configs: List of dicts with keys ``name``, ``num_partitions``,
            ``replication_factor``, and optional ``config``.

    Example:
        ensure_topics_exist([
            {"name": "kaval.txn.raw", "num_partitions": 12,
             "replication_factor": 1, "config": {"retention.ms": "86400000"}},
        ])
    """
    settings = get_settings()
    admin = AdminClient({"bootstrap.servers": settings.kafka_brokers})

    existing = set(admin.list_topics(timeout=10).topics.keys())
    new_topics = []

    for tc in topic_configs:
        name = tc["name"]
        if name in existing:
            logger.info("Topic '%s' already exists, skipping.", name)
            continue
        new_topics.append(
            NewTopic(
                topic=name,
                num_partitions=tc.get("num_partitions", 12),
                replication_factor=tc.get("replication_factor", 1),
                config=tc.get("config", {}),
            )
        )

    if not new_topics:
        logger.info("All requested topics already exist.")
        return

    futures = admin.create_topics(new_topics)
    for topic_name, future in futures.items():
        try:
            future.result()
            logger.info("Created topic '%s'.", topic_name)
        except KafkaException as exc:
            logger.error("Failed to create topic '%s': %s", topic_name, exc)
            raise
