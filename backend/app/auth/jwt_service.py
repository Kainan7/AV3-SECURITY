# app/auth/jwt_service.py
"""
Responsabilidade deste módulo
- Gerar JWT (token de acesso) para autenticação stateless.
- Decodificar/validar JWT recebido nas requisições.

Onde muda o "tempo de sessão"?
- Em JWT_EXPIRE_MINUTES (no app.config).
- O token expira quando "exp" (expiration) é atingido.
"""

from datetime import datetime, timedelta, timezone
from typing import Any, Dict

from jose import jwt, JWTError

from app.config import JWT_SECRET_KEY, JWT_EXPIRE_MINUTES

# Algoritmo HMAC (chave simétrica)
ALGORITHM = "HS256"


def create_access_token(subject: str) -> str:
    """
    Cria um token JWT com:
      - sub: "subject" do token (no seu caso, username)
      - iat: issued-at (quando foi emitido)
      - exp: expires-at (quando expira)

    Observação:
    - O tempo de expiração vem de JWT_EXPIRE_MINUTES (config).
    - Se JWT_EXPIRE_MINUTES = 120 => token dura 2 horas.
    """
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=JWT_EXPIRE_MINUTES)

    payload: Dict[str, Any] = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }

    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    """
    Valida e decodifica o JWT.

    Regras:
    - Verifica assinatura usando JWT_SECRET_KEY
    - Verifica expiração automaticamente (claim exp)
    - Lança JWTError se:
        • token inválido
        • token expirado
        • assinatura incorreta
        • payload malformado
    """
    return jwt.decode(token, JWT_SECRET_KEY, algorithms=[ALGORITHM])
