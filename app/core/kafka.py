import asyncio
import json
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings

settings = get_settings()

class KafkaProducerWrapper:
    def __init__(self):
        self.producer = None

    async def start(self):
        """Initializes the Kafka producer."""
        if self.producer is None:
            print(f"[Kafka] Connecting to {settings.KAFKA_BOOTSTRAP_SERVERS}...")
            try:
                self.producer = AIOKafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS
                )
                await self.producer.start()
                print("[Kafka] Producer started successfully.")
            except Exception as e:
                print(f"[Kafka] Failed to start producer: {e}")
                self.producer = None

    async def stop(self):
        """Stops the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            print("[Kafka] Producer stopped.")
            self.producer = None

    async def send_message(self, topic: str, message: dict):
        """
        Sends a JSON message to a Kafka topic.
        Non-blocking (fire and forget), but logs errors.
        """
        if self.producer is None:
            print("[Kafka] ⚠️ Producer is not initialized. Skipping message send.")
            return

        try:
            value_json = json.dumps(message).encode("utf-8")
            await self.producer.send_and_wait(topic, value_json)
            print(f"[Kafka] 📤 Sent message to '{topic}': {message}")
        except Exception as e:
            print(f"[Kafka] ❌ Failed to send message: {e}")

# Global Instance
kafka_producer = KafkaProducerWrapper()
