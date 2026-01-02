import boto3
import os
from langchain_aws import BedrockEmbeddings
from langchain_community.vectorstores import Chroma
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
        model_id="amazon.titan-embed-text-v1"
    )

def get_vector_store():
    """
    Returns the Persistent Chroma VectorStore.
    """
    persist_directory = os.path.join(os.getcwd(), "chroma_db")
    
    return Chroma(
        collection_name="jiaa_memory",
        embedding_function=get_embeddings(),
        persist_directory=persist_directory
    )

def get_long_term_store():
    """
    Returns the Persistent PostgreSQL VectorStore (PGVector).
    """
    # Connection String: postgresql://user:password@host:port/dbname
    connection_string = f"postgresql://{settings.PG_USER}:{settings.PG_PASSWORD}@{settings.PG_HOST}:{settings.PG_PORT}/{settings.PG_DB}"
    
    # Check if we should even try connecting (simple validation)
    if not settings.PG_HOST or settings.PG_HOST == "localhost":
        print("WARNING: PG_HOST is localhost. LTM might fail if DB is not local.")

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
