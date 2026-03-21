import httpx
from functools import lru_cache
from jose import jwt
from jose.exceptions import JWTError, ExpiredSignatureError
from fastapi import HTTPException

from src.config import settings


@lru_cache()
def get_jwks():
    resp = httpx.get(settings.JWKS_URL)
    resp.raise_for_status()
    return resp.json()["keys"]


def get_public_key(kid):
    for key in get_jwks():
        if key["kid"] == kid:
            return key
    raise HTTPException(status_code=401, detail="Invalid token header")


def verify_cognito_jwt(token: str):
    if token.startswith("Bearer "):
        token = token.split(" ")[1]

    try:
        headers = jwt.get_unverified_header(token)
        key = get_public_key(headers["kid"])

        payload = jwt.decode(
            token,
            key,
            algorithms=["RS256"],
            audience=settings.COGNITO_APP_CLIENT_ID,
            issuer=settings.ISSUER,
        )

        return payload

    except ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")

    except JWTError as e:
        raise HTTPException(status_code=401, detail=f"Invalid JWT: {str(e)}")
