"""Kafka producer for publishing agent events.

Handles serialization and delivery of AgentEvent messages to Kafka topics.
Topics are organized by event category for efficient consumer routing.
"""

import json
import logging
from typing import Optional

from confluent_kafka import Producer
from confluent_kafka.admin import AdminClient, NewTopic

from app.config import get_settings
from app.kafka_bus.events import AgentEvent, EventType

logger = logging.getLogger(__name__)

# Topic mapping — events are routed to category-specific topics
TOPIC_MAP = {
    EventType.ANALYSIS_REQUESTED: "fraud.analysis.requests",
    EventType.ANALYSIS_STARTED: "fraud.analysis.lifecycle",
    EventType.ANALYSIS_COMPLETED: "fraud.analysis.lifecycle",
    EventType.ANALYSIS_FAILED: "fraud.analysis.lifecycle",
    EventType.FRAUD_DETECTED: "fraud.detection.results",
    EventType.FRAUD_CLEARED: "fraud.detection.results",
    EventType.FRAUD_ESCALATED: "fraud.detection.results",
    EventType.COMPLIANCE_CHECK_STARTED: "fraud.compliance.results",
    EventType.COMPLIANCE_VIOLATION_FOUND: "fraud.compliance.results",
    EventType.COMPLIANCE_CHECK_PASSED: "fraud.compliance.results",
    EventType.RISK_SCORE_CALCULATED: "fraud.risk.scores",
    EventType.RISK_LEVEL_CHANGED: "fraud.risk.scores",
    EventType.INVESTIGATION_OPENED: "fraud.investigations",
    EventType.INVESTIGATION_UPDATED: "fraud.investigations",
    EventType.INVESTIGATION_CLOSED: "fraud.investigations",
    EventType.AGENT_HANDOFF: "fraud.agent.coordination",
    EventType.AGENT_RESULT_PUBLISHED: "fraud.agent.coordination",
    EventType.CONTEXT_ENRICHMENT_NEEDED: "fraud.agent.coordination",
    EventType.PATTERN_LEARNED: "fraud.memory.events",
    EventType.EPISODE_RECORDED: "fraud.memory.events",
}

# All unique topics
ALL_TOPICS = list(set(TOPIC_MAP.values()))


class KafkaProducer:
    """
    Async-friendly Kafka producer for agent event publishing.

    Features:
      - Automatic topic routing based on event type
      - Message key partitioning by correlation_id (keeps related events together)
      - Delivery confirmation callbacks
      - Topic auto-creation on startup
    """

    def __init__(self, bootstrap_servers: Optional[str] = None):
        settings = get_settings()
        self._config = {
            "bootstrap.servers": bootstrap_servers or settings.kafka_bootstrap_servers,
            "security.protocol": settings.kafka_security_protocol,
            "client.id": "fraud-analysis-producer",
            "acks": "all",
            "retries": 3,
            "retry.backoff.ms": 500,
        }
        if settings.kafka_sasl_username:
            self._config["sasl.mechanism"] = settings.kafka_sasl_mechanism
            self._config["sasl.username"] = settings.kafka_sasl_username
            self._config["sasl.password"] = settings.kafka_sasl_password
        self._producer: Optional[Producer] = None

    def connect(self) -> None:
        """Initialize the Kafka producer."""
        self._producer = Producer(self._config)
        logger.info("Kafka producer connected")

    def close(self) -> None:
        """Flush and close the producer."""
        if self._producer:
            self._producer.flush(timeout=10)
            self._producer = None

    def ensure_topics_exist(self) -> None:
        """Create all required topics if they don't exist."""
        admin_config = {
            "bootstrap.servers": self._config["bootstrap.servers"],
            "security.protocol": self._config["security.protocol"],
        }
        if "sasl.username" in self._config:
            admin_config["sasl.mechanism"] = self._config["sasl.mechanism"]
            admin_config["sasl.username"] = self._config["sasl.username"]
            admin_config["sasl.password"] = self._config["sasl.password"]
        admin = AdminClient(admin_config)
        existing = admin.list_topics(timeout=10).topics.keys()

        new_topics = []
        for topic in ALL_TOPICS:
            if topic not in existing:
                new_topics.append(
                    NewTopic(topic, num_partitions=3, replication_factor=1)
                )

        if new_topics:
            futures = admin.create_topics(new_topics)
            for topic_name, future in futures.items():
                try:
                    future.result()
                    logger.info("Created Kafka topic: %s", topic_name)
                except Exception as e:
                    logger.warning("Topic creation failed for %s: %s", topic_name, e)

    def publish(self, event: AgentEvent) -> None:
        """
        Publish an agent event to the appropriate Kafka topic.

        The event is automatically routed to the correct topic based on
        its event_type. The correlation_id is used as the message key
        to ensure related events land on the same partition.
        """
        if not self._producer:
            self.connect()

        topic = TOPIC_MAP.get(
            EventType(event.event_type), "fraud.agent.coordination"
        )

        message_value = event.model_dump_json()
        message_key = event.correlation_id

        self._producer.produce(
            topic=topic,
            key=message_key,
            value=message_value,
            callback=self._delivery_callback,
        )
        self._producer.poll(0)  # Trigger delivery reports

        logger.debug(
            "Published event: type=%s, topic=%s, correlation=%s",
            event.event_type, topic, event.correlation_id,
        )

    def flush(self) -> None:
        """Ensure all buffered messages are delivered."""
        if self._producer:
            self._producer.flush(timeout=10)

    @staticmethod
    def _delivery_callback(err, msg):
        """Callback for message delivery confirmation."""
        if err:
            logger.error("Message delivery failed: %s", err)
        else:
            logger.debug(
                "Message delivered: topic=%s, partition=%d, offset=%d",
                msg.topic(), msg.partition(), msg.offset(),
            )
