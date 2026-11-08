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


def parse_json(raw: str) -> dict:
    """Parse an AI reply into a dict.

    Tolerates ```json fences and any non-JSON prose around the first JSON value
    (the model sometimes prepends a short explanation). Raises ValueError if no
    valid JSON object/array can be found.
    """
    raw = (raw or "").strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        raw = raw[4:] if raw.startswith("json") else raw
        raw = raw.strip()
    if not raw:
        raise ValueError("Empty response: no JSON found")

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # Fallback: decode only the first complete JSON value, ignoring trailing text.
    start = min(
        (i for i in (raw.find("{"), raw.find("[")) if i != -1),
        default=-1,
    )
    if start != -1:
        try:
            obj, _ = json.JSONDecoder().raw_decode(raw[start:])
            return obj
        except Exception:
            pass

    raise ValueError("Could not parse JSON from model response")