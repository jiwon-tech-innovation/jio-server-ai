import os
from pydantic_settings import BaseSettings
from functools import lru_cache
from dotenv import load_dotenv

load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "JIAA Intelligence Worker"
    API_V1_STR: str = "/api/v1"
    
    AWS_ACCESS_KEY_ID: str = os.getenv("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY: str = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    AWS_REGION: str = os.getenv("AWS_REGION", "us-east-1")
    BEDROCK_REGION: str = os.getenv("BEDROCK_REGION", "us-west-2") # Cross-Region for Bedrock
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", os.getenv("AWS_REGION", "us-east-1"))

    # Long-Term Memory (PostgreSQL)
    PG_HOST: str = os.getenv("PG_HOST", os.getenv("pg_host", "localhost"))
    PG_PORT: str = os.getenv("PG_PORT", os.getenv("pg_port", "5432"))
    PG_USER: str = os.getenv("PG_USER", os.getenv("pg_user", "postgres"))
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", os.getenv("pg_password", "password"))
    PG_DB: str = os.getenv("PG_DB", os.getenv("pg_db", "jiaa_memory"))

    # Sensor Fusion (InfluxDB)
    INFLUXDB_URL: str = os.getenv("INFLUXDB_URL", "http://influxdb:8086")
    INFLUXDB_ORG: str = os.getenv("INFLUXDB_ORG", "jiaa")
    INFLUXDB_BUCKET: str = os.getenv("INFLUXDB_BUCKET", "sensor_data")
    INFLUXDB_TOKEN: str = os.getenv("INFLUXDB_TOKEN", "my-token")

    # Cache (Redis)
    REDIS_HOST: str = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT: str = os.getenv("REDIS_PORT", "6379")
    REDIS_PASSWORD: str = os.getenv("REDIS_PASSWORD", "")

    # Kafka (Message Broker)
    KAFKA_BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")
    KAFKA_TOPIC_AI_INTENT: str = os.getenv("KAFKA_TOPIC_AI_INTENT", "jiaa.ai.intent")

    class Config:
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
