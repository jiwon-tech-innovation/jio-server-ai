import json
import asyncio
from aiokafka import AIOKafkaProducer
from app.core.config import get_settings

settings = get_settings()

class KafkaProducerWrapper:
    _producer: AIOKafkaProducer = None

    @classmethod
    async def get_producer(cls) -> AIOKafkaProducer:
        if cls._producer is None:
            print(f"[Kafka] Initializing producer to {settings.KAFKA_BOOTSTRAP_SERVERS}...")
            try:
                cls._producer = AIOKafkaProducer(
                    bootstrap_servers=settings.KAFKA_BOOTSTRAP_SERVERS
                )
                await cls._producer.start()
                print("[Kafka] Producer started.")
            except Exception as e:
                print(f"[Kafka] Connection Failed: {e}")
                cls._producer = None
        return cls._producer

    @classmethod
    async def stop(cls):
        if cls._producer:
            await cls._producer.stop()
            cls._producer = None
            print("[Kafka] Producer stopped.")

    @classmethod
    async def send_event(cls, topic: str, event_type: str, payload: dict):
        """
        Fire-and-forget send. Logs error if fails, but doesn't block.
        """
        producer = await cls.get_producer()
        if not producer:
            print(f"[Kafka] Skip sending '{event_type}' (No producer)")
            return

        try:
            message = {
                "event_type": event_type,
                "payload": payload,
                "timestamp": asyncio.get_event_loop().time() # simple monotonic
            }
            value_json = json.dumps(message).encode("utf-8")
            await producer.send_and_wait(topic, value_json)
            # print(f"[Kafka] Sent '{event_type}' to {topic}")
        except Exception as e:
            print(f"[Kafka] Send Error: {e}")

kafka_producer = KafkaProducerWrapper()
