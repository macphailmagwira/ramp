"""
JWT verification for AWS Cognito tokens.

This module provides JWT verification functionality for AWS Cognito access tokens,
including signature verification with AWS public keys and claims extraction.
"""

import time

import requests
from fastapi import HTTPException
from jose import jwt as jose_jwt
from jose.backends import RSAKey


class CognitoJWTVerifier:
    """
    JWT verifier for AWS Cognito tokens.

    Handles token signature verification using AWS Cognito public keys,
    claims validation, and token expiration checking.
    """

    def __init__(self, region: str, user_pool_id: str, client_id: str):
        """
        Initialize the JWT verifier.

        Args:
            region: AWS region where the Cognito User Pool is located
            user_pool_id: The Cognito User Pool ID
            client_id: The Cognito User Pool Client ID
        """
        self.region = region
        self.user_pool_id = user_pool_id
        self.client_id = client_id
        self.issuer = (
            f"https://cognito-idp.{self.region}.amazonaws.com/{self.user_pool_id}"
        )
        self.jwks_url = f"{self.issuer}/.well-known/jwks.json"
        self._jwks = None
        self._jwks_last_update = 0

    def _get_jwks(self) -> dict:
        """
        Fetch the JSON Web Key Set (JWKS) from Cognito.

        Returns:
            The JWKS dictionary containing public keys

        Raises:
            HTTPException: If unable to fetch JWKS
        """
        current_time = time.time()
        # Cache JWKS for 1 hour
        if self._jwks is None or current_time - self._jwks_last_update > 3600:
            try:
                response = requests.get(self.jwks_url, timeout=10)
                response.raise_for_status()
                self._jwks = response.json()
                self._jwks_last_update = current_time
            except Exception as e:
                raise HTTPException(
                    status_code=500, detail=f"Failed to fetch JWKS: {str(e)}"
                )
        return self._jwks

    def _get_signing_key(self, token: str) -> str:
        """
        Get the signing key for the given JWT token.

        Args:
            token: The JWT token

        Returns:
            The signing key as PEM string

        Raises:
            HTTPException: If signing key cannot be found or is invalid
        """
        try:
            # Decode token header to get key ID
            header = jose_jwt.get_unverified_header(token)
            kid = header.get("kid")

            if not kid:
                raise HTTPException(status_code=401, detail="Token missing key ID")

            # Get JWKS and find matching key
            jwks = self._get_jwks()
            key_data = None

            for key in jwks.get("keys", []):
                if key.get("kid") == kid:
                    key_data = key
                    break

            if not key_data:
                raise HTTPException(status_code=401, detail="Signing key not found")

            # Convert JWK to PEM format
            rsa_key = RSAKey(key_data, algorithm="RS256")
            return rsa_key.to_pem()

        except jose_jwt.JWTError as e:
            raise HTTPException(
                status_code=401, detail=f"Invalid token header: {str(e)}"
            )
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Key retrieval error: {str(e)}"
            )

    def verify_token(self, token: str) -> dict:
        """
        Verify and decode a Cognito JWT token.

        Args:
            token: The JWT token to verify

        Returns:
            The decoded token payload containing user claims

        Raises:
            HTTPException: If token is invalid, expired, or verification fails
        """
        try:
            # Get signing key
            signing_key = self._get_signing_key(token)

            # Verify and decode the token
            decoded = jose_jwt.decode(
                token,
                signing_key,
                algorithms=["RS256"],
                audience=self.client_id,
                issuer=self.issuer,
                options={
                    "verify_exp": True,
                    "verify_aud": True,
                    "verify_iss": True,
                },
            )

            # Verify token_use claim
            token_use = decoded.get("token_use")
            if token_use != "access":
                raise HTTPException(
                    status_code=401,
                    detail=f"Invalid token type. Expected 'access', got '{token_use}'",
                )

            return decoded

        except jose_jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token has expired")
        except jose_jwt.JWTClaimsError as e:
            raise HTTPException(
                status_code=401, detail=f"Invalid token claims: {str(e)}"
            )
        except jose_jwt.JWTError as e:
            raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
        except Exception as e:
            raise HTTPException(
                status_code=500, detail=f"Token verification error: {str(e)}"
            )

    def extract_user_info(self, decoded_token: dict) -> dict:
        """
        Extract user information from decoded token.

        Args:
            decoded_token: The decoded JWT token payload

        Returns:
            Dictionary containing user ID, email, groups, and role
        """
        # Extract groups and map to role
        groups = decoded_token.get("cognito:groups", [])

        # Role mapping based on Cognito groups
        role = "operator"  # default role
        if "admin" in groups:
            role = "admin"
        elif "supervisor" in groups:
            role = "supervisor"

        return {
            "id": decoded_token["sub"],
            "email": decoded_token.get("email"),
            "username": decoded_token.get("username"),
            "groups": groups,
            "role": role,
            "token_use": decoded_token.get("token_use"),
            "exp": decoded_token.get("exp"),
            "iat": decoded_token.get("iat"),
        }
