# app/auth/ldap_auth.py
"""
Responsabilidade deste módulo
- Validar usuário/senha contra LDAP/AD ou autenticação mock em ambiente acadêmico.
- Não cria sessão, não gera token: apenas autentica credenciais.

Estratégia usada
1) Se AUTH_MODE="mock", valida credenciais locais de demonstração.
2) Se AUTH_MODE="ldap", tenta bind usando UPN (SIMPLE): username@dominio.
3) Se falhar, tenta bind usando NTLM: NETBIOS\\username.

Retorna
- True se conseguiu autenticar
- False caso contrário
"""

import logging

from ldap3 import Server, Connection, SIMPLE, NTLM

from app.config import (
    AUTH_MODE,
    LDAP_SERVER,
    LDAP_PORT,
    LDAP_DOMAIN,
    MOCK_USERS,
)

logger = logging.getLogger(__name__)


def _authenticate_mock(username: str, password: str) -> bool:
    """
    Autenticação local para ambiente acadêmico/demonstração.

    MOCK_USERS deve vir da configuração no formato:
    {
        "admin.demo": "admin123",
        "operator.demo": "operator123"
    }

    Observação:
    - Não usar este modo em produção.
    - Serve apenas para apresentação local sem dependência de AD real.
    """
    expected_password = MOCK_USERS.get(username)
    if not expected_password:
        logger.warning("[AUTH_MOCK] Usuário não encontrado: %s", username)
        return False

    if password != expected_password:
        logger.warning("[AUTH_MOCK] Senha inválida para usuário: %s", username)
        return False

    logger.info("[AUTH_MOCK] Login válido para usuário: %s", username)
    return True


def _authenticate_ldap(username: str, password: str) -> bool:
    """
    Autentica no AD/LDAP via bind.

    Segurança:
    - Não registra senha em log.
    - Logs são controláveis por nível.
    """
    logger.info("[LDAP] Tentando autenticar usuário=%s no servidor=%s:%s", username, LDAP_SERVER, LDAP_PORT)

    server = Server(LDAP_SERVER, port=LDAP_PORT)

    # -------------------------------------------------
    # 1) Tentativa UPN (SIMPLE)
    # Exemplo genérico: usuario@demo.local
    # -------------------------------------------------
    upn = f"{username}@{LDAP_DOMAIN}"
    try:
        logger.debug("[LDAP] Tentativa UPN (SIMPLE): %s", upn)
        conn = Connection(
            server,
            user=upn,
            password=password,
            authentication=SIMPLE,
            auto_bind=True,
        )
        conn.unbind()
        logger.info("[LDAP] Autenticação UPN concluída com sucesso")
        return True
    except Exception as e:
        logger.warning("[LDAP] Autenticação UPN falhou -> %s: %s", type(e).__name__, e)

    # -------------------------------------------------
    # 2) Tentativa NTLM
    # Exemplo genérico: DEMO\\usuario
    # -------------------------------------------------
    netbios = LDAP_DOMAIN.split(".")[0].upper()
    ntlm_user = f"{netbios}\\{username}"
    try:
        logger.debug("[LDAP] Tentativa NTLM: %s", ntlm_user)
        conn = Connection(
            server,
            user=ntlm_user,
            password=password,
            authentication=NTLM,
            auto_bind=True,
        )
        conn.unbind()
        logger.info("[LDAP] Autenticação NTLM concluída com sucesso")
        return True
    except Exception as e:
        logger.error("[LDAP] Autenticação NTLM falhou -> %s: %s", type(e).__name__, e)
        return False


def authenticate_user(username: str, password: str) -> bool:
    """
    Ponto único de autenticação usado pelas rotas.

    AUTH_MODE:
    - "mock": usa usuários locais de demonstração.
    - "ldap": usa LDAP/AD configurado no ambiente.
    """
    if not username or not password:
        logger.warning("[AUTH] Username ou password vazio")
        return False

    mode = (AUTH_MODE or "mock").lower().strip()

    if mode == "mock":
        return _authenticate_mock(username, password)

    if mode == "ldap":
        return _authenticate_ldap(username, password)

    logger.error("[AUTH] AUTH_MODE inválido: %s", AUTH_MODE)
    return False