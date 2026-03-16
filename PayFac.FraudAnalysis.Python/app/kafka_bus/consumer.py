"""Kafka consumer for receiving agent events.

Provides both synchronous polling and async event-driven consumption
patterns for agents to receive events from other agents.
"""

import asyncio
import json
import logging
from typing import Any, Callable, Coroutine, Optional

from confluent_kafka import Consumer, KafkaError, KafkaException

from app.config import get_settings
from app.kafka_bus.events import AgentEvent

logger = logging.getLogger(__name__)

# Type alias for event handlers
EventHandler = Callable[[AgentEvent], Coroutine[Any, Any, None]]


class KafkaConsumer:
    """
    Kafka consumer for agent event reception.

    Features:
      - Subscribe to multiple topics based on agent role
      - Async event handler registration
      - Automatic deserialization to AgentEvent
      - Graceful shutdown with commit
    """

    def __init__(
        self,
        group_id: Optional[str] = None,
        bootstrap_servers: Optional[str] = None,
    ):
        settings = get_settings()
        self._config = {
            "bootstrap.servers": bootstrap_servers or settings.kafka_bootstrap_servers,
            "security.protocol": settings.kafka_security_protocol,
            "group.id": group_id or settings.kafka_group_id,
            "auto.offset.reset": "latest",
            "enable.auto.commit": False,
            "max.poll.interval.ms": 300000,
        }
        if settings.kafka_sasl_username:
            self._config["sasl.mechanism"] = settings.kafka_sasl_mechanism
            self._config["sasl.username"] = settings.kafka_sasl_username
            self._config["sasl.password"] = settings.kafka_sasl_password
        self._consumer: Optional[Consumer] = None
        self._handlers: dict[str, list[EventHandler]] = {}
        self._running = False

    def connect(self, topics: list[str]) -> None:
        """Initialize consumer and subscribe to topics."""
        self._consumer = Consumer(self._config)
        self._consumer.subscribe(topics)
        logger.info("Kafka consumer subscribed to: %s", topics)

    def close(self) -> None:
        """Close consumer gracefully."""
        self._running = False
        if self._consumer:
            self._consumer.close()
            self._consumer = None

    def register_handler(self, event_type: str, handler: EventHandler) -> None:
        """
        Register an async handler for a specific event type.

        Multiple handlers can be registered for the same event type.
        """
        if event_type not in self._handlers:
            self._handlers[event_type] = []
        self._handlers[event_type].append(handler)
        logger.debug("Registered handler for event type: %s", event_type)

    async def start_consuming(self) -> None:
        """
        Start the consume loop (runs indefinitely until stopped).

        This is the main event loop for agent event processing.
        Call this in an asyncio task.
        """
        if not self._consumer:
            raise RuntimeError("Consumer not connected. Call connect() first.")

        self._running = True
        logger.info("Starting Kafka consume loop")

        while self._running:
            try:
                msg = self._consumer.poll(timeout=1.0)

                if msg is None:
                    await asyncio.sleep(0.1)
                    continue

                if msg.error():
                    if msg.error().code() == KafkaError._PARTITION_EOF:
                        continue
                    logger.error("Consumer error: %s", msg.error())
                    continue

                # Deserialize the event
                try:
                    event_data = json.loads(msg.value().decode("utf-8"))
                    event = AgentEvent(**event_data)
                except (json.JSONDecodeError, ValueError) as e:
                    logger.error("Failed to deserialize event: %s", e)
                    self._consumer.commit(msg)
                    continue

                # Route to registered handlers
                await self._dispatch_event(event)

                # Commit offset after successful processing
                self._consumer.commit(msg)

            except KafkaException as e:
                logger.error("Kafka exception: %s", e)
                await asyncio.sleep(1)
            except Exception as e:
                logger.error("Unexpected error in consume loop: %s", e)
                await asyncio.sleep(1)

    async def _dispatch_event(self, event: AgentEvent) -> None:
        """Dispatch an event to all registered handlers."""
        event_type = event.event_type
        handlers = self._handlers.get(event_type, [])

        # Also check for wildcard handlers
        wildcard_handlers = self._handlers.get("*", [])

        all_handlers = handlers + wildcard_handlers

        if not all_handlers:
            logger.debug("No handlers for event type: %s", event_type)
            return

        for handler in all_handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(
                    "Handler error for event %s: %s",
                    event.event_id, e,
                    exc_info=True,
                )

    def stop(self) -> None:
        """Signal the consume loop to stop."""
        self._running = False
