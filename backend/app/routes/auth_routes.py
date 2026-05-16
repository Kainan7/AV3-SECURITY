# app/routes/auth_routes.py
"""
Rotas de autenticação.

O que este módulo faz?
- Recebe credenciais de usuário e senha.
- Valida as credenciais usando o modo configurado no ambiente:
  - mock: autenticação local para demonstração acadêmica.
  - ldap: autenticação via LDAP/AD, caso configurado.
- Emite eventos de auditoria (LOGIN_SUCCESS / LOGIN_FAIL).
- Retorna um JWT para o frontend usar nas próximas requisições.

Por que existe?
- Centraliza autenticação em um único endpoint.
- Mantém o padrão de segurança: o frontend não guarda sessão no servidor, apenas token.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from app.deps.audit_bus import get_audit_bus
from app.audit.threads import BarramentoAuditoria
from app.audit.emissao import emitir_evento

from app.auth.ldap_auth import authenticate_user
from app.auth.jwt_service import create_access_token

router = APIRouter(prefix="/auth", tags=["Auth"])


# -----------------------------
# Schemas (request/response)
# -----------------------------
class LoginRequest(BaseModel):
    """Payload recebido do frontend na tentativa de login."""
    usuario: str
    senha: str


class TokenResponse(BaseModel):
    """Resposta padronizada: o frontend salva o access_token."""
    access_token: str


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    bus: BarramentoAuditoria = Depends(get_audit_bus),
):
    """
    Autentica usuário e devolve JWT.

    Fluxo:
    1) Valida credenciais conforme AUTH_MODE configurado.
    2) Se falhar -> 401 + evento LOGIN_FAIL.
    3) Se sucesso -> emite LOGIN_SUCCESS + gera JWT.

    Segurança:
    - Nunca registra senha em log.
    - Mensagens de erro não revelam detalhes sensíveis.
    """

    ok = authenticate_user(payload.usuario, payload.senha)

    if not ok:
        emitir_evento(
            bus,
            nivel="ERROR",
            usuario=payload.usuario,
            origem="AUTH",
            acao="LOGIN_FAIL",
            mensagem="Falha ao autenticar usuário.",
            sucesso=False,
        )
        raise HTTPException(status_code=401, detail="Invalid credentials")

    emitir_evento(
        bus,
        nivel="INFO",
        usuario=payload.usuario,
        origem="AUTH",
        acao="LOGIN_SUCCESS",
        mensagem="Usuário autenticado com sucesso.",
        sucesso=True,
    )

    token = create_access_token(subject=payload.usuario)
    return {"access_token": token}