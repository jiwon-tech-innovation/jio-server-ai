import boto3
from langchain_aws import ChatBedrock
from app.core.config import get_settings

settings = get_settings()

# Model IDs
HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
SONNET_MODEL_ID = "anthropic.claude-3-5-sonnet-20240620-v1:0"

def get_bedrock_client():
    """
    Returns a boto3 client for bedrock-runtime.
    """
    return boto3.client(
        service_name="bedrock-runtime",
        region_name=settings.BEDROCK_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )

def get_llm(model_id: str, temperature: float = 0.0):
    """
    Returns a LangChain ChatBedrock instance.
    """
    client = get_bedrock_client()
    return ChatBedrock(
        client=client,
        model_id=model_id,
        model_kwargs={"temperature": temperature},
        region_name=settings.BEDROCK_REGION
    )
