import boto3
import os
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import Redis, Chroma
from app.core.config import get_settings

settings = get_settings()

def get_embeddings():
    """
    Returns Bedrock Embeddings (Titan Text v1).
    """
    client = boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )
    return BedrockEmbeddings(
        client=client,
        model_id="amazon.titan-embed-text-v2:0"
    )

def get_vector_store():
    """
    Returns the Redis VectorStore.
    """
    # Construct Redis URL
    redis_password = f":{settings.REDIS_PASSWORD}@" if settings.REDIS_PASSWORD else ""
    redis_url = f"redis://{redis_password}{settings.REDIS_HOST}:{settings.REDIS_PORT}"

    return Redis(
        redis_url=redis_url,
        index_name="jiaa_memory",
        embedding=get_embeddings()
    )

def get_long_term_store():
    """
    Returns the Persistent Long-Term Memory (LTM).
    For Local Testing: Uses ChromaDB.
    For Production: Uses PostgreSQL (PGVector).
    """
    # Toggle this flag to switch backends
    USE_CHROMA_LTM = True 

    if USE_CHROMA_LTM:
        print("INFO: Using ChromaDB for Long-Term Memory (Local Mode).")
        persist_directory = os.path.join(os.getcwd(), "chroma_ltm_db")
        return Chroma(
            collection_name="jiaa_long_term_memory",
            embedding_function=get_embeddings(),
            persist_directory=persist_directory
        )

    # --- PGVector Implementation (Production) ---
    # Connection String: postgresql://user:password@host:port/dbname
    connection_string = f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
    
    try:
        from langchain_community.vectorstores import PGVector
        return PGVector(
            connection_string=connection_string,
            embedding_function=get_embeddings(),
            collection_name="jiaa_long_term_memory",
        )
    except Exception as e:
        print(f"ERROR: Failed to initialize PGVector: {e}")
        return None
