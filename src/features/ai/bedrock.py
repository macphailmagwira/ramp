import json
import boto3
from botocore.config import Config
from src.config import settings


def get_bedrock_client():
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        config=Config(
            read_timeout=300,      # 5 minutes
            connect_timeout=10,
            retries={"max_attempts": 0},  # disable boto3 auto-retry, we handle it
        ),
    )


def invoke_qwen(prompt: str, system: str, max_tokens: int = 4000) -> str:
    client = get_bedrock_client()
    body = json.dumps({
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": max_tokens,
    })
    response = client.invoke_model(
        modelId="qwen.qwen3-next-80b-a3b",
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    result = json.loads(response["body"].read())
    return result["choices"][0]["message"]["content"]