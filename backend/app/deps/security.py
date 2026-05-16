# app/deps/security.py
"""
Dependências de segurança do FastAPI.

- Extrai e valida JWT do header Authorization.
- Retorna o usuário atual (username) para uso nas rotas.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from app.auth.jwt_service import decode_token

# HTTPBearer lê: Authorization: Bearer <token>
# auto_error=False => deixa a gente controlar o erro e mensagem
bearer = HTTPBearer(auto_error=False)


def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> str:
    """
    Valida autenticação via JWT e retorna o username (claim "sub").

    Fluxo:
    1) Lê Authorization Bearer
    2) Decodifica JWT (verifica assinatura + expiração)
    3) Retorna payload["sub"]

    Erros:
    - 401 se não autenticado, inválido ou expirado
    """
    if creds is None or not creds.credentials:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = creds.credentials

    try:
        payload = decode_token(token)
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return str(username)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
