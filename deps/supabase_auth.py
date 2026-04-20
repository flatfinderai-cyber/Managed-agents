# © 2024–2026 Lila Alexandra Olufemi Inglis Abegunrin. All Rights Reserved.
"""
Supabase Auth JWT verification for FastAPI.
Uses the project's JWT secret (Dashboard → Settings → API → JWT Settings → JWT Secret).
"""

from __future__ import annotations

import os
from typing import Annotated, Optional

import jwt
from fastapi import Depends, Header, HTTPException

_ALGORITHMS = ("HS256",)


def _jwt_secret() -> str:
    secret = (os.environ.get("SUPABASE_JWT_SECRET") or "").strip()
    if not secret:
        raise HTTPException(
            status_code=503,
            detail="Server misconfiguration: set SUPABASE_JWT_SECRET (Supabase project JWT secret).",
        )
    return secret


def decode_supabase_access_token(token: str) -> dict:
    """Decode and validate a Supabase access_token (Bearer)."""
    try:
        return jwt.decode(
            token,
            _jwt_secret(),
            algorithms=list(_ALGORITHMS),
            audience="authenticated",
            options={"require": ["exp", "sub"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise HTTPException(status_code=401, detail="Token expired.") from exc
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid token.") from exc


async def bearer_user_id(
    authorization: Annotated[Optional[str], Header()] = None,
) -> str:
    """
    Require `Authorization: Bearer <access_token>` and return auth.users id (`sub`).
    """
    if not authorization or authorization[:7].lower() != "bearer ":
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header (expected Bearer token).",
        )
    token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Empty Bearer token.")
    payload = decode_supabase_access_token(token)
    sub = payload.get("sub")
    if not sub or not isinstance(sub, str):
        raise HTTPException(status_code=401, detail="Token missing subject.")
    return sub


def assert_same_user(path_user_id: str, token_user_id: str) -> None:
    if path_user_id != token_user_id:
        raise HTTPException(
            status_code=403,
            detail="You may only access your own account resources.",
        )


CurrentUserId = Annotated[str, Depends(bearer_user_id)]
