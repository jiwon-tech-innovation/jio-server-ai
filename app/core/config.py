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
    AWS_S3_REGION: str = os.getenv("AWS_S3_REGION", os.getenv("AWS_REGION", "us-east-1"))

    # Long-Term Memory (PostgreSQL)
    PG_HOST: str = os.getenv("PG_HOST", "localhost")
    PG_PORT: str = os.getenv("PG_PORT", "5432")
    PG_USER: str = os.getenv("PG_USER", "postgres")
    PG_PASSWORD: str = os.getenv("PG_PASSWORD", "password")
    PG_DB: str = os.getenv("PG_DB", "jiaa_memory")

    class Config:
        case_sensitive = True

@lru_cache()
def get_settings():
    return Settings()
